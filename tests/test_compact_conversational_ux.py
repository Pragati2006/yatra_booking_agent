"""
tests/test_compact_conversational_ux.py
Validates the 10 User Experience Scenarios for Compact AI Responses,
Progressive Disclosure, and Natural Conversational Turns.
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
from agents import coordinator, orchestrator, session_store


class TestCompactConversationalUX(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_sessions.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        db.ensure_live_data()

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: New trip generation with concise, devotional reply
    # -------------------------------------------------------------------------
    def test_scenario_1_new_trip_generation(self):
        res = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 4 pilgrims"
        )
        self.assertEqual(res["status"], "PLAN_READY")
        self.assertEqual(res["intent"], "TRIP_PLANNING")
        sid = res["session_id"]
        self.assertIsNotNone(sid)

        reply = res["reply"]
        # Verify concise 4-5 line devotional summary
        self.assertIn("Jai Mata Di", reply)
        self.assertIn("Delhi → Katra", reply)
        self.assertIn("Normal Darshan", reply)
        self.assertIn("2 rooms", reply)
        self.assertIn("Estimated total", reply)
        self.assertIn("Would you like to explore your itinerary or modify anything?", reply)

        # Ensure no wall of text (lines <= 10, no 50-line bloat)
        lines = [line for line in reply.split("\n") if line.strip()]
        self.assertLessEqual(len(lines), 10)
        self.assertNotIn("VERIFIED BOOKING COSTS", reply)
        self.assertNotIn("ESTIMATED ON-TRIP EXPENSES", reply)

        # Underlying state and recommendations preserved
        self.assertIsNotNone(res.get("recommendation"))
        self.assertIsNotNone(res.get("selected_options"))
        self.assertIsNotNone(res.get("budget_evaluation"))
        self.assertIsNotNone(res.get("itinerary"))

    # -------------------------------------------------------------------------
    # Scenario 2: User changes traveller count
    # -------------------------------------------------------------------------
    def test_scenario_2_user_changes_traveller_count(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 4 pilgrims"
        )
        sid = res1["session_id"]

        # Modification: change pax to 2
        res2 = orchestrator.orchestrate_conversational_turn(
            "Change the number of travellers to 2",
            session_id=sid,
        )
        self.assertEqual(res2["status"], "PLAN_REVISED")
        self.assertEqual(res2["plan_version"], 2)
        reply = res2["reply"]
        self.assertIn("Done! I've updated your trip for 2 pilgrims", reply)
        self.assertIn("Revision #2", reply)
        self.assertIn("Everything else remains unchanged", reply)

        # State updated
        self.assertEqual(res2["request"]["pax"], 2)
        self.assertEqual(res2["budget_evaluation"]["rooms_needed"], 1)

    # -------------------------------------------------------------------------
    # Scenario 3: User changes transport
    # -------------------------------------------------------------------------
    def test_scenario_3_user_changes_transport(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 pilgrims by train"
        )
        sid = res1["session_id"]

        res2 = orchestrator.orchestrate_conversational_turn(
            "Change to flight",
            session_id=sid,
        )
        self.assertEqual(res2["status"], "PLAN_REVISED")
        self.assertEqual(res2["plan_version"], 2)
        reply = res2["reply"]
        self.assertIn("Done! I've updated your travel mode to Flight", reply)
        self.assertIn("Everything else remains unchanged", reply)
        self.assertEqual(res2["request"]["mode"], "flight")

    # -------------------------------------------------------------------------
    # Scenario 4: User changes accommodation
    # -------------------------------------------------------------------------
    def test_scenario_4_user_changes_accommodation(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 pilgrims"
        )
        sid = res1["session_id"]

        res2 = orchestrator.orchestrate_conversational_turn(
            "Find a cheaper hotel",
            session_id=sid,
        )
        self.assertEqual(res2["status"], "PLAN_REVISED")
        reply = res2["reply"]
        self.assertIn("stay preference to Budget", reply)
        self.assertEqual(res2["request"]["accommodation_preference"], "Budget")

    # -------------------------------------------------------------------------
    # Scenario 5: User changes budget
    # -------------------------------------------------------------------------
    def test_scenario_5_user_changes_budget(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 pilgrims"
        )
        sid = res1["session_id"]

        res2 = orchestrator.orchestrate_conversational_turn(
            "My budget is 25000",
            session_id=sid,
        )
        self.assertEqual(res2["status"], "PLAN_REVISED")
        reply = res2["reply"]
        self.assertIn("Your budget is now set to ₹25,000", reply)
        self.assertEqual(res2["budget_evaluation"]["total_budget"], 25000.0)
        self.assertIsNotNone(res2["budget_evaluation"]["within_budget"])

    # -------------------------------------------------------------------------
    # Scenario 6: User requests the full itinerary (Progressive disclosure)
    # -------------------------------------------------------------------------
    def test_scenario_6_user_requests_full_itinerary(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 pilgrims"
        )
        sid = res1["session_id"]

        res2 = orchestrator.orchestrate_conversational_turn(
            "Show full itinerary",
            session_id=sid,
        )
        self.assertEqual(res2["intent"], "ITINERARY")
        reply = res2["reply"]
        self.assertTrue("Day 01" in reply or "Day 1" in reply)
        self.assertTrue("Day 02" in reply or "Day 2" in reply)
        self.assertTrue("Day 03" in reply or "Day 3" in reply)
        self.assertTrue("Day 04" in reply or "Day 4" in reply)

    # -------------------------------------------------------------------------
    # Scenario 7: User requests detailed cost breakdown (Progressive disclosure)
    # -------------------------------------------------------------------------
    def test_scenario_7_user_requests_detailed_cost_breakdown(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 pilgrims"
        )
        sid = res1["session_id"]

        res2 = orchestrator.orchestrate_conversational_turn(
            "Show detailed cost breakdown",
            session_id=sid,
        )
        self.assertEqual(res2["intent"], "TRIP_PLANNING")
        reply = res2["reply"]
        self.assertIn("Detailed Cost Breakdown", reply)
        self.assertIn("Verified Direct Bookings", reply)
        self.assertIn("Estimated Expenses", reply)
        self.assertIn("Estimated Grand Total", reply)

    # -------------------------------------------------------------------------
    # Scenario 8: User asks a general tourism question
    # -------------------------------------------------------------------------
    def test_scenario_8_user_asks_general_tourism_question(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 pilgrims"
        )
        sid = res1["session_id"]

        res2 = orchestrator.orchestrate_conversational_turn(
            "Tell me about Bhairavnath Temple",
            session_id=sid,
        )
        self.assertEqual(res2["intent"], "TOURISM")
        reply = res2["reply"]
        self.assertIn("Bhairavnath", reply)
        # Active plan remains safe in session
        saved = session_store.get_session(sid)
        self.assertEqual(saved["state"]["requirements"]["origin"], "Delhi")
        self.assertIsNotNone(saved["state"]["selected_options"])

    # -------------------------------------------------------------------------
    # Scenario 9: Conversational missing info follow-up
    # -------------------------------------------------------------------------
    def test_scenario_9_conversational_missing_info_question(self):
        # User provides only pax
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a Vaishno Devi trip for four people"
        )
        self.assertEqual(res1["status"], "NEEDS_INFO")
        reply = res1["reply"]
        self.assertIn("Sure! I'll help you plan a comfortable Vaishno Devi trip for four", reply)
        self.assertIn("Which city will you be traveling from", reply)
        sid = res1["session_id"]

        # Follow-up with origin and duration
        res2 = orchestrator.orchestrate_conversational_turn(
            "From Delhi for 4 days",
            session_id=sid,
        )
        self.assertEqual(res2["status"], "PLAN_READY")
        self.assertEqual(res2["request"]["origin"], "Delhi")
        self.assertEqual(res2["request"]["pax"], 4)
        self.assertEqual(res2["request"]["duration_days"], 4)

    # -------------------------------------------------------------------------
    # Scenario 10: User requests booking authorization (HITL safety intact)
    # -------------------------------------------------------------------------
    def test_scenario_10_user_requests_booking_authorization(self):
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 pilgrims"
        )
        sid = res1["session_id"]

        # Unconfirmed request -> Gate blocks
        res2 = orchestrator.orchestrate_conversational_turn(
            "Book option 1",
            session_id=sid,
        )
        self.assertEqual(res2["intent"], "BOOKING")
        self.assertEqual(res2["status"], "authorization_required")
        self.assertNotIn("booking_id", res2)

        # Explicit human confirmation -> Booking executes
        res3 = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res3["intent"], "BOOKING")
        self.assertEqual(res3["status"], "success")
        self.assertIn("booking_id", res3)


if __name__ == "__main__":
    unittest.main()
