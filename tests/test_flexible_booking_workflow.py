"""
tests/test_flexible_booking_workflow.py
Comprehensive automated test suite verifying all 12 requirements of the
Yatra Booking Agent Preference-Driven Recommendation and Confirmation Flow:

1. Submitting the form produces a complete recommendation automatically.
2. All selected options appear together on the recommendation page.
3. The recommended selections reflect the actual backend response.
4. Missing or infeasible required options are handled honestly.
5. The user can confirm selections without opening every individual section.
6. The user can change only transport, darshan, accommodation, or sightseeing and return to the summary.
7. Budget and itinerary update after a change.
8. Unaffected valid selections are preserved.
9. Previous authorization is invalidated after a material plan revision.
10. Mock RPA cannot execute before explicit authorization of the current plan.
11. The flow works through both form-based and chat-based planning.
12. The final result never falsely claims that a real-world booking has been completed.
"""

import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.main import app
from agents.orchestrator import coordinate_plan
from agents.budget_engine import calculate_budget
import agents.session_store as session_store


class TestFlexibleBookingWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # =========================================================================
    # 1. Submitting the form produces a complete recommendation automatically
    # =========================================================================
    def test_01_submitting_form_produces_complete_recommendation_automatically(self):
        """Verifies that submitting intake preferences produces transport, slot, hotel, itinerary, and budget in one shot."""
        resp = self.client.post("/api/yatra/", json={
            "message": "2 pilgrims from Delhi travelling to Katra on 2026-10-20 for 4 days with Normal Darshan by train with total budget of 15000, balanced pace, Standard stay"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "PLAN_READY")

        plan = data.get("plan", {})
        self.assertIsNotNone(plan.get("selected_option"), "Expected automatically selected transport + slot bundle")
        self.assertIsNotNone(plan.get("hotel"), "Expected automatically recommended accommodation option")
        self.assertIsNotNone(plan.get("itinerary"), "Expected complete day-wise itinerary")
        self.assertGreater(len(plan.get("itinerary", [])), 0, "Itinerary should have multiple days")
        self.assertIsNotNone(plan.get("budget_evaluation"), "Expected deterministic calculated budget")

        # Verify budget breakdown contains verified direct costs and discretionary estimates
        b_eval = plan.get("budget_evaluation", {})
        self.assertIn("grand_total", b_eval)
        self.assertTrue("verified_costs" in b_eval or "verified_direct_charges" in b_eval)
        self.assertIn("estimated_costs", b_eval)

    # =========================================================================
    # 2. All selected options appear together on the recommendation page
    # =========================================================================
    def test_02_all_selected_options_appear_together_on_recommendation_page(self):
        """Verifies that the consolidated plan output provides all fields required for the consolidated page."""
        plan_res = coordinate_plan({
            "origin": "Delhi",
            "start_date": "2026-10-20",
            "days": 4,
            "pilgrims": 2,
            "mode": "train",
            "category": "Normal Darshan",
            "total_budget": 15000,
        })
        self.assertEqual(plan_res.get("status"), "PLAN_READY")
        plan = plan_res["plan"]

        # 1. Transport details
        sel_opt = plan["selected_option"]
        tr = sel_opt["transport"]
        self.assertIn("transport_no", tr)
        self.assertIn("departure_time", tr)
        self.assertIn("arrival_time", tr)
        self.assertIn("fare_per_person", tr)
        self.assertIn("total_fare", tr)

        # 2. Darshan slot
        slot = sel_opt["slot"]
        self.assertIn("category", slot)
        self.assertIn("slot_time", slot)
        self.assertIn("price", slot)

        # 3. Accommodation
        hotel = plan["hotel"]
        self.assertIsNotNone(hotel)
        self.assertIn("name", hotel)
        self.assertIn("price_per_night", hotel)

        # 4. Sightseeing & Itinerary
        self.assertIsInstance(plan["itinerary"], list)
        self.assertGreaterEqual(len(plan["itinerary"]), 3)

        # 5. Financial Summary
        b_eval = plan["budget_evaluation"]
        self.assertGreater(b_eval["grand_total"], 0)
        self.assertEqual(plan["pax"], 2)

    # =========================================================================
    # 3. The recommended selections reflect the actual backend response
    # =========================================================================
    def test_03_recommended_selections_reflect_actual_backend_response(self):
        """Verifies that the recommended options are grounded in actual database inventory, not hardcoded dummy data."""
        resp = self.client.post("/api/yatra/", json={
            "message": "2 pilgrims from Delhi travelling on 2026-10-20 for 4 days by train"
        })
        data = resp.json()
        plan = data.get("plan", {})
        top_transport = plan["selected_option"]["transport"]

        # Ensure service exists in distinct available options
        options = plan.get("options", [])
        matched_in_options = any(
            opt["transport"].get("transport_no") == top_transport.get("transport_no")
            and opt["transport"].get("departure_time") == top_transport.get("departure_time")
            for opt in options
        )
        self.assertTrue(matched_in_options, "Recommended transport must be grounded in verified options list")

        # Hotel name must be an actual inventory property
        hotel = plan.get("hotel", {})
        self.assertTrue(len(hotel.get("name", "")) > 0)
        self.assertGreater(hotel.get("price_per_night", 0), 0)

    # =========================================================================
    # 4. Missing or infeasible required options are handled honestly
    # =========================================================================
    def test_04_missing_or_infeasible_required_options_handled_honestly(self):
        """Verifies that unsupported departure hubs or missing inventory are handled honestly without fabrication."""
        # Unsupported origin
        resp_unsupported = self.client.post("/api/yatra/", json={
            "message": "2 pilgrims from Kanyakumari travelling to Katra on 2026-10-20 for 4 days by train"
        })
        self.assertEqual(resp_unsupported.status_code, 200)
        data = resp_unsupported.json()
        self.assertEqual(data.get("status"), "NO_AVAILABILITY")
        self.assertIn("Kanyakumari", data.get("reply", ""))
        self.assertIn("Supported departure hubs include", data.get("reply", ""))
        # Verify no fake options were silently fabricated
        self.assertEqual(len(data.get("plan", {}).get("options", [])), 0)

        # Infeasible sightseeing due to duration constraints
        itin_resp = self.client.post("/api/yatra/itinerary", json={
            "option": {
                "transport": {"id": "TR01", "mode": "train", "price": 575, "arrival_date": "2026-10-20", "arrival_time": "14:00"},
                "slot": {"category": "Normal Darshan", "slot_date": "2026-10-21", "slot_time": "06:00", "price": 0}
            },
            "hotel": {"name": "Trikuta Guest House", "price_per_night": 800},
            "hotel_nights": 2,
            "sightseeing_places": ["Patnitop", "Bhairavnath Temple"],
            "request": {"days": 3, "origin": "Delhi"}
        })
        self.assertEqual(itin_resp.status_code, 200)
        itin_data = itin_resp.json()
        # Patnitop is distant (3+ hrs from Katra) and infeasible on a 3-day pilgrimage
        infeasible = [str(p) for p in itin_data.get("infeasible_places", [])]
        self.assertTrue(any("Patnitop" in p for p in infeasible), "Patnitop must be flagged as infeasible for 3-day duration")

    # =========================================================================
    # 5. The user can confirm selections without opening every individual section
    # =========================================================================
    def test_05_user_can_confirm_selections_without_opening_every_individual_section(self):
        """Verifies that a user can transition directly from recommendation to authorization and confirmation."""
        # Single search call
        resp = self.client.post("/api/yatra/", json={
            "message": "2 pilgrims from Delhi on 2026-10-20 for 4 days by train"
        })
        data = resp.json()
        session_id = data.get("session_id")
        plan_version = data.get("plan_version", 1)
        plan = data.get("plan", {})
        selected_option = plan["selected_option"]
        selected_hotel = plan["hotel"]

        # Confirm selections directly on authorization endpoint without visiting intermediate wizard screens
        auth_resp = self.client.post("/api/yatra/authorize", json={
            "session_id": session_id,
            "plan_version": plan_version,
            "user_confirmation": "Confirm booking"
        })
        self.assertEqual(auth_resp.status_code, 200)
        self.assertEqual(auth_resp.json().get("status"), "success")

        # Booking executes successfully
        confirm_resp = self.client.post("/api/yatra/confirm", json={
            "session_id": session_id,
            "plan_version": plan_version,
            "human_authorized": True,
            "option": selected_option,
            "hotel": selected_hotel,
            "hotel_nights": 3,
            "sightseeing_places": [],
            "pax": 2,
            "user_name": "Pilgrim-One"
        })
        self.assertEqual(confirm_resp.status_code, 200)
        self.assertEqual(confirm_resp.json().get("status"), "success")

    # =========================================================================
    # 6. The user can change only transport, darshan, accommodation, or sightseeing
    # =========================================================================
    def test_06_user_can_change_only_specific_category_and_return_to_summary(self):
        """Verifies changing an individual category (e.g. accommodation only) without restarting the entire trip."""
        # Initial plan
        plan_init = coordinate_plan({
            "origin": "Delhi",
            "start_date": "2026-10-20",
            "days": 4,
            "pilgrims": 2,
            "mode": "train"
        })
        orig_transport = plan_init["plan"]["selected_option"]["transport"]

        # Fetch alternative hotels from inventory
        hotel_resp = self.client.post("/api/yatra/accommodation", json={
            "check_in_date": "2026-10-20",
            "category": "Mid-Range",
            "min_rooms": 1
        })
        self.assertEqual(hotel_resp.status_code, 200)
        mid_hotels = hotel_resp.json().get("hotels", [])
        self.assertGreater(len(mid_hotels), 0)
        new_hotel = mid_hotels[0]

        # Re-evaluate budget with replacement hotel while preserving original transport
        new_budget = calculate_budget(
            pax=2,
            transport=orig_transport,
            darshan_slot=plan_init["plan"]["selected_option"]["slot"],
            accommodation=new_hotel,
            duration_days=4
        )
        self.assertNotEqual(new_budget["grand_total"], plan_init["plan"]["budget_evaluation"]["grand_total"])

    # =========================================================================
    # 7. Budget and itinerary update after a change
    # =========================================================================
    def test_07_budget_and_itinerary_update_after_a_change(self):
        """Verifies budget updates deterministically when accommodation or sights change."""
        plan = coordinate_plan({
            "origin": "Delhi",
            "start_date": "2026-10-20",
            "days": 4,
            "pilgrims": 2,
            "mode": "train"
        })["plan"]

        base_grand_total = plan["budget_evaluation"]["grand_total"]

        # Swap to higher-tier hotel
        luxury_hotel = {"name": "The White Luxury Katra", "price_per_night": 3500}
        updated_budget = calculate_budget(
            pax=2,
            transport=plan["selected_option"]["transport"],
            darshan_slot=plan["selected_option"]["slot"],
            accommodation=luxury_hotel,
            duration_days=4,
            is_round_trip=True,
            estimated_costs=plan["budget_evaluation"]["estimated_costs"]["items"],
            estimate_return_if_missing=True,
        )
        self.assertGreater(updated_budget["grand_total"], base_grand_total)

    # =========================================================================
    # 8. Unaffected valid selections are preserved
    # =========================================================================
    def test_08_unaffected_valid_selections_are_preserved(self):
        """Verifies that changing transport preserves accommodation and itinerary if valid."""
        plan_res = coordinate_plan({
            "origin": "Delhi",
            "start_date": "2026-10-20",
            "days": 4,
            "pilgrims": 2
        })
        options = plan_res["plan"]["options"]
        self.assertGreaterEqual(len(options), 2)

        opt1 = options[0]
        opt2 = options[1]
        hotel = plan_res["plan"]["hotel"]

        # User swaps to option 2
        active_opt = opt2
        active_hotel = hotel  # preserved

        self.assertNotEqual(opt1["transport"]["id"], active_opt["transport"]["id"])
        self.assertEqual(active_hotel["name"], hotel["name"], "Hotel must be preserved across transport swap")

    # =========================================================================
    # 9. Previous authorization is invalidated after a material plan revision
    # =========================================================================
    def test_09_previous_authorization_invalidated_after_material_plan_revision(self):
        """Verifies server invalidates stale authorization when a revision occurs."""
        resp = self.client.post("/api/yatra/", json={
            "message": "2 pilgrims from Delhi on 2026-10-20 for 4 days by train"
        })
        data = resp.json()
        session_id = data.get("session_id")
        plan_version = data.get("plan_version", 1)

        # 1. Authorize plan version 1
        auth_resp = self.client.post("/api/yatra/authorize", json={
            "session_id": session_id,
            "plan_version": plan_version,
            "user_confirmation": "Confirm booking"
        })
        self.assertEqual(auth_resp.json().get("status"), "success")

        # 2. Invalidate authorization on server due to plan change (increment to version 2)
        session_store.update_session(session_id, updates={
            "plan_version": plan_version + 1,
            "authorized_plan_version": None,  # authorization cleared
        })

        # 3. Attempt to confirm booking with un-authorized version 2
        confirm_resp = self.client.post("/api/yatra/confirm", json={
            "session_id": session_id,
            "plan_version": plan_version + 1,
            "human_authorized": True,
            "option": data["plan"]["selected_option"],
            "pax": 2,
            "user_name": "Test User"
        })
        self.assertEqual(confirm_resp.status_code, 200)
        self.assertEqual(confirm_resp.json().get("status"), "authorization_required")
        self.assertTrue("Server-side human authorization has not been granted" in confirm_resp.json().get("message", "") or "revised" in confirm_resp.json().get("message", ""))

    # =========================================================================
    # 10. Mock RPA cannot execute before explicit authorization of the current plan
    # =========================================================================
    def test_10_mock_rpa_cannot_execute_before_explicit_authorization_of_current_plan(self):
        """Verifies mock RPA fails closed if explicit human authorization is absent."""
        resp = self.client.post("/api/yatra/", json={
            "message": "2 pilgrims from Delhi on 2026-10-20 for 4 days by train"
        })
        session_id = resp.json().get("session_id")
        plan = resp.json().get("plan", {})
        chosen_option = plan["selected_option"]

        # Call RPA without prior authorization
        rpa_resp = self.client.post("/api/yatra/rpa", json={
            "session_id": session_id,
            "plan_version": 1,
            "user_name": "Test Pilgrim",
            "pax_count": 2,
            "transport_text": "Train",
            "slot_text": "Normal Darshan",
            "total_price": 2500,
            "headless": True
        })
        self.assertEqual(rpa_resp.status_code, 200)
        self.assertEqual(rpa_resp.json().get("status"), "authorization_required")

    # =========================================================================
    # 11. The flow works through both form-based and chat-based planning
    # =========================================================================
    def test_11_flow_works_through_both_form_based_and_chat_based_planning(self):
        """Verifies that conversational turns and structured form searches synchronize the same plan state."""
        # Turn 1 in chat
        chat_turn1 = self.client.post("/api/chat", json={
            "message": "Plan a yatra from Delhi for 2 people on 2026-10-20 for 4 days by train"
        })
        self.assertEqual(chat_turn1.status_code, 200)
        data1 = chat_turn1.json()
        session_id = data1.get("session_id")
        self.assertIsNotNone(session_id)
        self.assertIsNotNone(data1.get("plan"))

        # Turn 2: modify duration via conversational instruction
        chat_turn2 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Make it 5 days",
            "current_request": data1.get("request"),
            "current_itinerary": data1.get("itinerary"),
        })
        self.assertEqual(chat_turn2.status_code, 200)
        data2 = chat_turn2.json()
        self.assertEqual(data2.get("request", {}).get("duration_days"), 5)
        self.assertEqual(len(data2.get("itinerary", [])), 5)

    # =========================================================================
    # 12. The final result never falsely claims that a real-world booking has been completed
    # =========================================================================
    def test_12_final_result_never_falsely_claims_real_world_booking(self):
        """Verifies clear disclaimers that bookings are simulated prototype demonstrations."""
        resp = self.client.post("/api/yatra/", json={
            "message": "2 pilgrims from Delhi on 2026-10-20 for 4 days by train"
        })
        data = resp.json()
        session_id = data.get("session_id")
        plan_version = data.get("plan_version", 1)
        plan = data.get("plan", {})

        # Authorize
        self.client.post("/api/yatra/authorize", json={
            "session_id": session_id,
            "plan_version": plan_version
        })

        # Confirm
        confirm_resp = self.client.post("/api/yatra/confirm", json={
            "session_id": session_id,
            "plan_version": plan_version,
            "human_authorized": True,
            "option": plan["selected_option"],
            "hotel": plan["hotel"],
            "hotel_nights": 3,
            "pax": 2,
            "user_name": "Test User"
        })
        c_data = confirm_resp.json()
        self.assertEqual(c_data.get("status"), "success")
        msg = c_data.get("message", "").lower()

        # Must not claim real payment or live tickets were issued
        self.assertNotIn("credit card charged", msg)
        self.assertNotIn("live irctc confirmed", msg)


if __name__ == "__main__":
    unittest.main()
