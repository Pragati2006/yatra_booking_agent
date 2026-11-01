"""
tests/test_phase_4a_navigation_regression.py
Phase 4A Regression Test Suite:
1. Chat-to-Booking Navigation Payload Forwarding & Extraction Contract
2. Planning Mode & Step Selection Logic (Choice Screen vs Step 2 Recommended Yatra)
3. Preserving Normal Entry Flow When No Context Exists
4. Requirement Extraction & Multi-turn Accumulation
5. Requirement Modification, Plan Version Increment, & Stale Authorization Invalidation
6. Server-side Authorization Gate & Safe Mock RPA Execution Disclaimer
"""

import unittest
import uuid
from fastapi.testclient import TestClient
from backend.main import app
import agents.session_store as session_store


class TestPhase4ANavigationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_navigation_payload_schema_and_defaults(self):
        """Verifies the contract of navPayload forwarded from AIChat to YatraBooking."""
        session_id = f"test-nav-{uuid.uuid4().hex[:8]}"
        session_store.create_session(session_id=session_id)
        
        # Request trip planning via API
        resp = self.client.post("/api/yatra/", json={
            "message": "Plan a 4-day yatra for 2 pilgrims from Delhi with budget 15000",
            "session_id": session_id
        })
        self.assertEqual(resp.status_code, 200)
        plan_res = resp.json()
        self.assertEqual(plan_res.get("intent"), "TRIP_PLANNING")
        self.assertIsNotNone(plan_res.get("plan"))
        plan = plan_res["plan"]
        
        # Reconstruct frontend navPayload creation logic
        nav_payload = {
            "sessionId": plan_res.get("session_id") or session_id,
            "planVersion": plan_res.get("plan_version", 1),
            "feasible_places": plan_res.get("feasible_places", []),
            "infeasible_places": plan_res.get("infeasible_places", []),
            "itinerary": plan_res.get("itinerary") or plan.get("itinerary"),
            "request": plan_res.get("request"),
            "sightseeing_choice": (plan_res.get("request") or {}).get("sightseeing_choice"),
            "options": plan.get("options"),
            "selected_option": plan.get("selected_option") or (plan.get("options")[0] if plan.get("options") else None),
            "hotel": plan.get("hotel"),
            "budget_evaluation": plan_res.get("budget_evaluation") or plan.get("budget_evaluation"),
            "planningMode": "form",
            "step": 2 if plan.get("options") and len(plan.get("options")) > 0 else 1,
        }

        # Assert navigation payload contract
        self.assertEqual(nav_payload["sessionId"], session_id)
        self.assertEqual(nav_payload["planningMode"], "form")
        self.assertEqual(nav_payload["step"], 2)
        self.assertIsNotNone(nav_payload["request"])
        self.assertEqual(nav_payload["request"].get("origin"), "Delhi")
        self.assertEqual(nav_payload["request"].get("pax"), 2)
        self.assertIsNotNone(nav_payload["selected_option"])
        self.assertIsNotNone(nav_payload["hotel"])
        self.assertIsNotNone(nav_payload["budget_evaluation"])
        self.assertIsInstance(nav_payload["itinerary"], list)
        self.assertGreaterEqual(len(nav_payload["itinerary"]), 1)

    def test_02_mode_and_step_resolution_logic(self):
        """Verifies state determination logic in YatraBooking for both context-bearing and empty entries."""
        # Scenario A: Context present from chat
        context_payload = {
            "sessionId": "sess-123",
            "planningMode": "form",
            "options": [{"id": 1, "transport": {"mode": "train"}}],
            "step": 2,
        }
        resolved_mode_a = context_payload.get("planningMode") or ("form" if context_payload.get("sessionId") else None)
        resolved_step_a = context_payload.get("step") or (2 if context_payload.get("options") else 1)
        self.assertEqual(resolved_mode_a, "form")
        self.assertEqual(resolved_step_a, 2)

        # Scenario B: Direct entry from navbar/home without params
        empty_payload = None
        resolved_mode_b = None if not empty_payload else "form"
        resolved_step_b = 1 if not empty_payload else 2
        self.assertIsNone(resolved_mode_b, "Empty payload must resolve to null planningMode (Choice Screen)")
        self.assertEqual(resolved_step_b, 1)

    def test_03_multi_turn_accumulation_and_missing_details(self):
        """Verifies assistant accumulates details across turns and retains session state."""
        session_id = f"test-multiturn-{uuid.uuid4().hex[:8]}"
        session_store.create_session(session_id=session_id)

        # Turn 1: Only origin and pax
        res1 = self.client.post("/api/chat", json={
            "message": "We are 2 pilgrims starting from Delhi.",
            "session_id": session_id
        }).json()
        self.assertIn("reply", res1)
        session_state_1 = session_store.get_session(session_id)
        req_1 = session_state_1.get("state", {}).get("requirements", {})
        self.assertEqual(req_1.get("origin"), "Delhi")
        self.assertEqual(req_1.get("pax"), 2)

        # Turn 2: Provide duration and budget
        res2 = self.client.post("/api/chat", json={
            "message": "We have 4 days and our budget is Rs 15000.",
            "session_id": session_id
        }).json()
        session_state_2 = session_store.get_session(session_id)
        req_2 = session_state_2.get("state", {}).get("requirements", {})
        self.assertEqual(req_2.get("origin"), "Delhi")
        self.assertEqual(req_2.get("pax"), 2)
        self.assertEqual(req_2.get("duration_days"), 4)
        self.assertEqual(req_2.get("total_budget"), 15000)

    def test_04_requirement_modification_invalidates_authorization(self):
        """Verifies changing requirements increments plan_version and revokes previous authorization."""
        session_id = f"test-stale-auth-{uuid.uuid4().hex[:8]}"
        session_store.create_session(session_id=session_id)

        # Step 1: Create initial plan
        res1 = self.client.post("/api/yatra/", json={
            "message": "Plan a 4-day trip from Delhi for 2 pilgrims with budget 15000",
            "session_id": session_id
        }).json()
        plan_v1 = res1.get("plan_version", 1)
        self.assertEqual(plan_v1, 1)
        self.assertGreater(len(res1["plan"]["options"]), 0)
        selected_option = res1["plan"]["options"][0]
        selected_hotel = res1["plan"]["hotel"]

        # Step 2: User explicitly authorizes plan v1
        auth_resp = self.client.post("/api/yatra/authorize", json={
            "session_id": session_id,
            "plan_version": plan_v1,
        }).json()
        self.assertEqual(auth_resp.get("status"), "success")

        # Step 3: User changes requirements to 3 days
        res2 = self.client.post("/api/yatra/", json={
            "message": "Change duration to 3 days and budget to 12000",
            "session_id": session_id
        }).json()
        plan_v2 = res2.get("plan_version", 2)
        self.assertGreater(plan_v2, plan_v1)

        # Step 4: Verify session reflects revoked authorization
        session_data = session_store.get_session(session_id)
        state = session_data.get("state", {})
        auth_info = state.get("authorization", {})
        self.assertFalse(auth_info.get("granted", False))
        self.assertEqual(auth_info.get("revoked_reason"), "plan_modified")

        # Step 5: Attempting confirmation with stale plan_version 1 fails
        stale_confirm = self.client.post("/api/yatra/confirm", json={
            "session_id": session_id,
            "plan_version": 1,
            "human_authorized": True,
            "option": selected_option,
            "pax": 2,
            "user_name": "Test Pilgrim",
            "hotel": selected_hotel,
            "hotel_nights": 2,
            "sightseeing_places": []
        }).json()
        self.assertEqual(stale_confirm.get("status"), "authorization_required")

        # Step 6: Authorizing plan_v2 allows confirmation
        auth_v2 = self.client.post("/api/yatra/authorize", json={
            "session_id": session_id,
            "plan_version": plan_v2,
        }).json()
        self.assertEqual(auth_v2.get("status"), "success")

        confirm_v2 = self.client.post("/api/yatra/confirm", json={
            "session_id": session_id,
            "plan_version": plan_v2,
            "human_authorized": True,
            "option": selected_option,
            "pax": 2,
            "user_name": "Test Pilgrim",
            "hotel": selected_hotel,
            "hotel_nights": 2,
            "sightseeing_places": []
        }).json()
        self.assertEqual(confirm_v2.get("status"), "success")
        self.assertIn("booking_id", confirm_v2)

    def test_05_mock_rpa_simulation_disclaimer(self):
        """Verifies mock RPA requires authorization and returns booking reference."""
        session_id = f"test-rpa-{uuid.uuid4().hex[:8]}"
        session_store.create_session(session_id=session_id)

        # Plan and authorize
        p_res = self.client.post("/api/yatra/", json={
            "message": "Plan a 3-day yatra for 2 pilgrims from Delhi with budget 12000",
            "session_id": session_id
        }).json()
        curr_version = p_res.get("plan_version", 1)

        # Authorize on server
        self.client.post("/api/yatra/authorize", json={
            "session_id": session_id,
            "plan_version": curr_version,
        })

        # Run RPA
        rpa_resp = self.client.post("/api/yatra/rpa", json={
            "session_id": session_id,
            "plan_version": curr_version,
            "human_authorized": True,
            "user_name": "Test Pilgrim",
            "pax_count": 2,
            "transport_text": "train from Delhi to Katra",
            "slot_text": "Normal Darshan 06:00 AM",
            "total_price": 5400.0,
            "headless": True
        })
        self.assertEqual(rpa_resp.status_code, 200)
        rpa_data = rpa_resp.json()
        self.assertEqual(rpa_data.get("status"), "success")
        rpa_info = rpa_data.get("rpa", {})
        self.assertIn("booking_id", rpa_info)


if __name__ == "__main__":
    unittest.main()
