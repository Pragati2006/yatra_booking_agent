"""
tests/test_orchestrator.py
Phase 6.2 — Persistent Conversational Trip Orchestrator Tests.

Validates:
1. Session creation and reuse across multiple chat messages.
2. Updating requirements without losing earlier information.
3. Asking for missing mandatory fields with concise natural-language prompts.
4. Proceeding when required information is available.
5. Tool coordination and consolidated plan output.
6. Budget evaluation with missing or estimated prices.
7. Budget recalculation after changing transport, travellers, hotel, or budget.
8. Conversational itinerary edits, where supported.
9. Unknown or malformed session identifiers.
10. Existing authorization gate remaining intact.
11. Existing API compatibility.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

# Ensure UTF-8 output on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    elif hasattr(sys.stdout, "buffer") and not sys.stdout.buffer.closed:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

import db
from agents import budget_engine, coordinator, orchestrator, session_store


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for isolated SQLite session testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_sessions.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        # Ensure prototype datasets are loaded
        db.ensure_live_data()

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        # Clean up temporary test database directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Session creation and reuse across multiple messages
    # -------------------------------------------------------------------------
    def test_session_creation_and_reuse_across_messages(self):
        """Tests persistent session creation and multi-turn state accumulation."""
        # Turn 1: User gives partial information without session_id
        res1 = orchestrator.orchestrate_conversational_turn("I want to plan a yatra")
        self.assertIsNotNone(res1.get("session_id"))
        sid = res1["session_id"]
        self.assertEqual(res1["status"], "NEEDS_INFO")
        self.assertIn("origin", res1["missing_fields"])

        # Turn 2: User provides origin, passing session_id
        res2 = orchestrator.orchestrate_conversational_turn(
            "We are travelling from Delhi",
            session_id=sid,
        )
        self.assertEqual(res2["session_id"], sid)
        # Origin must now be saved in session
        req2 = res2["request"]
        self.assertEqual(req2.get("origin"), "Delhi")

        # Turn 3: User provides duration and travellers
        res3 = orchestrator.orchestrate_conversational_turn(
            "For 4 days with 2 pilgrims",
            session_id=sid,
        )
        self.assertEqual(res3["session_id"], sid)
        self.assertEqual(res3["status"], "PLAN_READY")
        self.assertEqual(res3["request"]["origin"], "Delhi")  # preserved from Turn 2
        self.assertEqual(res3["request"]["duration_days"], 4)
        self.assertEqual(res3["request"]["pax"], 2)

        # Verify persistent SQLite session record
        saved_session = session_store.get_session(sid)
        self.assertIsNotNone(saved_session)
        state = saved_session["state"]
        self.assertEqual(state["requirements"]["origin"], "Delhi")
        self.assertEqual(state["requirements"]["pax"], 2)
        self.assertIsNotNone(state.get("selected_options"))
        self.assertIsNotNone(state.get("budget_evaluation"))

    # -------------------------------------------------------------------------
    # 2. Updating requirements without losing earlier information
    # -------------------------------------------------------------------------
    def test_update_requirements_without_losing_earlier_info(self):
        """Tests that follow-up changes update only the targeted field and retain others."""
        # Establish base session
        init_req = {"origin": "Delhi", "duration_days": 4, "pax": 2, "mode": "train"}
        session = session_store.create_session(initial_state={"requirements": init_req})
        sid = session["session_id"]

        # Turn 1: Add a budget
        res1 = orchestrator.orchestrate_conversational_turn("My budget is ₹20,000", session_id=sid)
        self.assertEqual(res1["request"]["total_budget"], 20000.0)
        self.assertEqual(res1["request"]["origin"], "Delhi")  # retained
        self.assertEqual(res1["request"]["duration_days"], 4)  # retained
        self.assertEqual(res1["request"]["pax"], 2)  # retained

        # Turn 2: Change travel mode to flight
        res2 = orchestrator.orchestrate_conversational_turn("Switch to flight", session_id=sid)
        self.assertEqual(res2["request"]["mode"], "flight")
        self.assertEqual(res2["request"]["total_budget"], 20000.0)  # retained
        self.assertEqual(res2["request"]["origin"], "Delhi")  # retained
        self.assertEqual(res2["request"]["pax"], 2)  # retained

    # -------------------------------------------------------------------------
    # 3. Asking for missing mandatory fields
    # -------------------------------------------------------------------------
    def test_ask_missing_mandatory_fields(self):
        """Tests that concise follow-ups are asked for missing mandatory fields."""
        # Case A: Missing origin only
        req_no_origin = {"duration_days": 4, "pax": 2, "_pax_explicit": True}
        missing_a = orchestrator.detect_missing_mandatory_fields(req_no_origin)
        self.assertEqual(missing_a, ["origin"])
        q_a = orchestrator.generate_missing_info_question(missing_a, req_no_origin)
        self.assertIn("Which city will you be traveling from", q_a)
        self.assertNotIn("how many pilgrims", q_a)

        # Case B: Missing duration/dates only
        req_no_dur = {"origin": "Delhi", "pax": 2, "_pax_explicit": True}
        missing_b = orchestrator.detect_missing_mandatory_fields(req_no_dur)
        self.assertEqual(missing_b, ["duration_or_dates"])
        q_b = orchestrator.generate_missing_info_question(missing_b, req_no_dur)
        self.assertIn("travel dates or trip duration", q_b)

        # Case C: Missing all fields
        missing_c = orchestrator.detect_missing_mandatory_fields({})
        self.assertIn("origin", missing_c)
        self.assertIn("duration_or_dates", missing_c)
        self.assertIn("pax", missing_c)
        q_c = orchestrator.generate_missing_info_question(missing_c, {})
        self.assertIn("which city", q_c)
        self.assertIn("how many pilgrims", q_c)
        self.assertIn("duration", q_c)

    # -------------------------------------------------------------------------
    # 4. Proceeding when required information is available
    # -------------------------------------------------------------------------
    def test_proceed_when_required_info_available(self):
        """Tests that full planning proceeds when origin, dates/duration, and pax are present."""
        res = orchestrator.orchestrate_conversational_turn(
            "I am travelling from Delhi for 4 days with 2 travellers"
        )
        self.assertEqual(res["status"], "PLAN_READY")
        self.assertIsNotNone(res["plan"])
        self.assertTrue(len(res["plan"]["options"]) > 0)
        self.assertIsNotNone(res["selected_options"])
        self.assertIsNotNone(res["budget_evaluation"])
        self.assertIsNotNone(res["itinerary"])
        self.assertEqual(len(res["itinerary"]), 4)

    # -------------------------------------------------------------------------
    # 5. Tool coordination and consolidated plan output
    # -------------------------------------------------------------------------
    def test_tool_coordination_and_consolidated_output(self):
        """Tests that transport, darshan, accommodation, sightseeing, and budget are coordinated."""
        req = {"origin": "Delhi", "duration_days": 4, "pax": 2, "category": "Normal Darshan"}
        plan_res = orchestrator.coordinate_plan(req)

        self.assertEqual(plan_res["status"], "PLAN_READY")
        # Check transport coordination
        selected_tr = plan_res["selected_options"]["transport"]
        self.assertIn("operator", selected_tr)
        self.assertEqual(selected_tr["origin"], "Delhi")

        # Check darshan slot coordination
        selected_slot = plan_res["selected_options"]["darshan_slot"]
        self.assertIn("slot_date", selected_slot)

        # Check hotel coordination
        selected_hotel = plan_res["selected_options"]["accommodation"]
        self.assertIsNotNone(selected_hotel)
        self.assertIn("price_per_night", selected_hotel)

        # Check sightseeing coordination
        sightseeing = plan_res["selected_options"]["sightseeing"]
        self.assertTrue(len(sightseeing) > 0)

        # Check concise consolidated reply formatting
        reply = plan_res["reply"]
        self.assertIn("Jai Mata Di", reply)
        self.assertIn("Delhi → Katra", reply)
        self.assertIn("Estimated total", reply)

    # -------------------------------------------------------------------------
    # 6. Budget evaluation with missing or estimated prices
    # -------------------------------------------------------------------------
    def test_budget_evaluation_missing_and_estimated_costs(self):
        """Tests deterministic separation of verified, estimated, and excluded costs."""
        req = {"origin": "Delhi", "duration_days": 4, "pax": 2}
        plan_res = orchestrator.coordinate_plan(req)
        b_eval = plan_res["budget_evaluation"]

        # Verified costs must exist
        self.assertIn("verified_costs", b_eval)
        verified = b_eval["verified_costs"]
        self.assertGreater(verified["total_verified"], 0.0)

        # Estimated costs must exist and be segregated
        self.assertIn("estimated_costs", b_eval)
        estimated = b_eval["estimated_costs"]
        self.assertGreater(estimated["total_estimated"], 0.0)
        self.assertIn("local_road_transfer", estimated["breakdown"])
        self.assertIn("meals_and_refreshments", estimated["breakdown"])

        # Excluded expenses must be listed and not added to total
        self.assertIn("excluded_expenses", b_eval)
        self.assertTrue(len(b_eval["excluded_expenses"]) > 0)

    # -------------------------------------------------------------------------
    # 7. Budget recalculation after changing transport, travellers, hotel, or budget
    # -------------------------------------------------------------------------
    def test_budget_recalculation_after_changes(self):
        """Tests dynamic recalculation of budget when constraints change."""
        # Initial plan: 2 travellers from Delhi
        res1 = orchestrator.orchestrate_conversational_turn(
            "I am travelling from Delhi for 4 days with 2 travellers"
        )
        sid = res1["session_id"]
        total_2_pax = res1["budget_evaluation"]["grand_total"]

        # Change travellers to 4: "We are travelling with four people."
        res2 = orchestrator.orchestrate_conversational_turn(
            "We are travelling with four people.",
            session_id=sid,
        )
        total_4_pax = res2["budget_evaluation"]["grand_total"]
        self.assertGreater(total_4_pax, total_2_pax)
        self.assertEqual(res2["budget_evaluation"]["rooms_needed"], 2)

        # Change hotel to cheaper hotel
        res3 = orchestrator.orchestrate_conversational_turn(
            "Find a cheaper hotel",
            session_id=sid,
        )
        self.assertEqual(res3["request"]["accommodation_preference"], "Budget")

        # Set explicit target budget and test feasibility check
        res4 = orchestrator.orchestrate_conversational_turn(
            "My budget is ₹30,000",
            session_id=sid,
        )
        self.assertEqual(res4["budget_evaluation"]["total_budget"], 30000.0)
        self.assertIsNotNone(res4["budget_evaluation"]["within_budget"])

        # Feasibility query without new number
        res5 = orchestrator.orchestrate_conversational_turn(
            "Can we fit this into our budget?",
            session_id=sid,
        )
        self.assertIn("budget", res5["reply"].lower())

    # -------------------------------------------------------------------------
    # 8. Conversational itinerary edits
    # -------------------------------------------------------------------------
    def test_conversational_itinerary_edits(self):
        """Tests natural-language itinerary modifications via coordinator."""
        res_plan = orchestrator.orchestrate_conversational_turn(
            "I am travelling from Delhi for 4 days with 2 travellers"
        )
        sid = res_plan["session_id"]

        # Turn 2: Move an activity
        res_move = orchestrator.orchestrate_conversational_turn(
            "Move Patnitop to Day 3",
            session_id=sid,
        )
        self.assertEqual(res_move["intent"], "ITINERARY")
        self.assertIsNotNone(res_move["itinerary"])

    # -------------------------------------------------------------------------
    # 9. Unknown or malformed session identifiers
    # -------------------------------------------------------------------------
    def test_unknown_or_malformed_session_identifiers(self):
        """Tests that unknown or malformed session IDs are handled gracefully."""
        # Non-existent session ID -> creates new session safely
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan my yatra from Delhi for 4 days with 2 travellers",
            session_id="non-existent-uuid-99999",
        )
        self.assertIsNotNone(res1["session_id"])
        self.assertNotEqual(res1["session_id"], "non-existent-uuid-99999")
        self.assertEqual(res1["status"], "PLAN_READY")

        # None or empty string session ID -> creates new session
        res2 = orchestrator.orchestrate_conversational_turn(
            "Plan my yatra from Delhi for 4 days with 2 travellers",
            session_id="",
        )
        self.assertIsNotNone(res2["session_id"])
        self.assertEqual(res2["status"], "PLAN_READY")

    # -------------------------------------------------------------------------
    # 10. Existing authorization gate remaining intact
    # -------------------------------------------------------------------------
    def test_authorization_gate_intact(self):
        """Tests that RPA is protected behind the human authorization gate."""
        res_plan = orchestrator.orchestrate_conversational_turn(
            "I am travelling from Delhi for 4 days with 2 travellers"
        )
        sid = res_plan["session_id"]

        # Step 1: Booking request without confirmation -> Gate must hold
        res_gate = orchestrator.orchestrate_conversational_turn(
            "Book option 1",
            session_id=sid,
        )
        self.assertEqual(res_gate["intent"], "BOOKING")
        self.assertEqual(res_gate["status"], "authorization_required")
        self.assertEqual(res_gate["tool_execution"]["status"], "pending_human_confirmation")
        self.assertNotIn("rpa_info", res_gate)

        # Step 2: Explicit confirmation -> RPA executes
        res_confirm = orchestrator.orchestrate_conversational_turn(
            "Yes, proceed",
            session_id=sid,
        )
        self.assertEqual(res_confirm["intent"], "BOOKING")
        self.assertEqual(res_confirm["status"], "success")
        self.assertEqual(res_confirm["tool_execution"]["status"], "success")
        self.assertIn("rpa_info", res_confirm)
        self.assertIn("booking_id", res_confirm)

    def test_authorization_invalidated_on_plan_change(self):
        """
        Tests Step 3:
        1. Generate a plan.
        2. Ask for explicit confirmation.
        3. Verify that mock RPA can run only after required authorization.
        4. Change a material detail (travel date, transport option, hotel, pax, or budget).
        5. Verify that the old approval cannot authorize the changed plan.
        6. Require the user to review and confirm the revised plan before RPA runs again.
        """
        # Step 1: Generate plan (Revision 1)
        res_plan = orchestrator.orchestrate_conversational_turn(
            "Plan my yatra from Delhi for 4 days with 2 travellers"
        )
        sid = res_plan["session_id"]
        self.assertEqual(res_plan["plan_version"], 1)

        # Step 2: Unconfirmed booking request -> Gate blocks
        res_unauth = orchestrator.orchestrate_conversational_turn(
            "Book option 1",
            session_id=sid,
        )
        self.assertEqual(res_unauth["status"], "authorization_required")
        self.assertNotIn("rpa_info", res_unauth)

        # Step 3: Explicit confirmation -> Authorization granted for Revision 1 and mock RPA executes
        res_confirm1 = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res_confirm1["status"], "success")
        self.assertEqual(res_confirm1["plan_version"], 1)
        self.assertIn("booking_id", res_confirm1)
        saved_s1 = session_store.get_session(sid)
        self.assertEqual(saved_s1["state"]["authorized_plan_version"], 1)
        self.assertTrue(saved_s1["state"]["authorization"]["granted"])

        # Step 4: Change a material detail (e.g. switch to train or change pax to 4)
        res_change = orchestrator.orchestrate_conversational_turn(
            "We are travelling with 4 people",
            session_id=sid,
        )
        self.assertEqual(res_change["plan_version"], 2)
        self.assertEqual(res_change["status"], "PLAN_REVISED")
        self.assertIn("Revision #2", res_change["reply"])
        saved_s2 = session_store.get_session(sid)
        self.assertIsNone(saved_s2["state"]["authorized_plan_version"])
        self.assertFalse(saved_s2["state"]["authorization"]["granted"])
        self.assertEqual(saved_s2["state"]["authorization"]["revoked_reason"], "plan_modified")

        # Step 5: Verify that old approval cannot authorize changed plan
        res_attempt = orchestrator.orchestrate_conversational_turn(
            "Book option 1",
            session_id=sid,
        )
        self.assertEqual(res_attempt["status"], "authorization_required")
        self.assertIn("Revision #2", res_attempt["reply"])
        self.assertNotIn("rpa_info", res_attempt)

        # Step 6: Require user to review and confirm revised plan before RPA runs again
        res_confirm2 = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res_confirm2["status"], "success")
        self.assertEqual(res_confirm2["plan_version"], 2)
        self.assertIn("booking_id", res_confirm2)
        saved_s3 = session_store.get_session(sid)
        self.assertEqual(saved_s3["state"]["authorized_plan_version"], 2)
        self.assertTrue(saved_s3["state"]["authorization"]["granted"])

    # -------------------------------------------------------------------------
    # 11. Existing API compatibility
    # -------------------------------------------------------------------------
    def test_existing_api_compatibility(self):
        """Tests that coordinator.route_message retains backward-compatible schemas."""
        # Tourism query
        res_tourism = coordinator.route_message("Tell me about Bhairavnath.")
        self.assertEqual(res_tourism["intent"], "TOURISM")
        self.assertIsNone(res_tourism["request"])
        self.assertIn("Bhairavnath", res_tourism["reply"])
        self.assertIsNotNone(res_tourism.get("session_id"))

        # Trip planning query
        res_trip = coordinator.route_message("I am travelling from Delhi for 5 days with my family.")
        self.assertEqual(res_trip["intent"], "TRIP_PLANNING")
        self.assertEqual(res_trip["plan"]["status"], "PLAN_READY")
        self.assertIsNotNone(res_trip["request"])
        self.assertIsNotNone(res_trip["itinerary"])
        self.assertEqual(len(res_trip["itinerary"]), 5)
        self.assertIsNotNone(res_trip.get("session_id"))


if __name__ == "__main__":
    unittest.main()
