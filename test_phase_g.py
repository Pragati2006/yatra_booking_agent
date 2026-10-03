"""
test_phase_g.py
Phase G — End-to-End Integration, Demo Hardening & Final Verification.
Tests complete multi-turn scenarios, state isolation, edge cases, error fallbacks, and RPA safety.
"""

import sys
import io
import unittest

# Force UTF-8 for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents import coordinator, tools, itinerary_agent, recommendation_agent, rpa_agent, knowledge_agent, conversation_agent
import agent as legacy_agent
import weather


class TestPhaseG(unittest.TestCase):

    # ==================================================================
    # STEP 2 — END-TO-END SCENARIO TESTING
    # ==================================================================

    def test_scenario_1_tourism(self):
        """Scenario 1: Tourism conversational flow and state preservation."""
        # Turn 1: "Tell me about Bhairavnath."
        res1 = coordinator.route_message("Tell me about Bhairavnath.")
        self.assertEqual(res1["intent"], "TOURISM")
        self.assertIn("Bhairavnath", res1["reply"])
        self.assertIsNone(res1["request"])  # trip state remains untouched
        self.assertEqual(res1["last_tourism_place"], "Bhairavnath Temple")

        # Turn 2: "How far is it?"
        res2 = coordinator.route_message("How far is it?", last_tourism_place=res1["last_tourism_place"])
        self.assertEqual(res2["intent"], "TOURISM")
        self.assertIn("Bhairavnath", res2["reply"])
        self.assertIsNone(res2["request"])
        self.assertNotIn("Which city are you travelling from", res2["reply"])

    def test_scenario_2_trip_planning(self):
        """Scenario 2: Multi-field trip planning extraction and plan generation."""
        user_msg = "I am travelling from Delhi for 5 days with my family."
        res = coordinator.route_message(user_msg)

        self.assertEqual(res["intent"], "TRIP_PLANNING")
        req = res["request"]
        self.assertIsNotNone(req)
        self.assertEqual(req.get("origin"), "Delhi")
        self.assertEqual(req.get("duration_days"), 5)
        self.assertEqual(req.get("group_type"), "family")

        self.assertIsNotNone(res["plan"])
        self.assertEqual(res["plan"]["status"], "PLAN_READY")
        self.assertIsNotNone(res["recommendation"])
        self.assertIsNotNone(res["itinerary"])
        self.assertEqual(len(res["itinerary"]), 5)  # list of 5 day dicts

    def test_scenario_3_trip_edit(self):
        """Scenario 3: Conversational trip modifications and field synchronization."""
        # Initial request
        msg1 = "I am travelling from Delhi for 5 days with my family."
        res1 = coordinator.route_message(msg1)
        req1 = res1["request"]
        itin1 = res1["itinerary"]

        # Turn 2: "Make it relaxed."
        res2 = coordinator.route_message("Make it relaxed.", current_request=req1, current_itinerary=itin1)
        req2 = res2["request"]
        self.assertEqual(req2.get("travel_style"), "relaxed")
        self.assertEqual(req2.get("origin"), "Delhi")  # preserved
        self.assertEqual(req2.get("duration_days"), 5)  # preserved
        self.assertEqual(req2.get("group_type"), "family")  # preserved

        # Turn 3: "Actually make it 6 days."
        res3 = coordinator.route_message("Actually make it 6 days.", current_request=req2, current_itinerary=res2["itinerary"])
        req3 = res3["request"]
        itin3 = res3["itinerary"]
        self.assertEqual(req3.get("duration_days"), 6)
        self.assertEqual(req3.get("travel_style"), "relaxed")  # preserved
        self.assertEqual(req3.get("origin"), "Delhi")  # preserved
        self.assertEqual(len(itin3), 6)  # synchronized duration list length

    def test_scenario_4_itinerary_editing(self):
        """Scenario 4: Day-by-day itinerary modifications and persistence."""
        req = conversation_agent.understand_request("I am travelling from Delhi for 5 days")
        itin = itinerary_agent.generate_default_itinerary(req)

        # Turn 1: "Move Patnitop to Day 3."
        res1 = coordinator.route_message("Move Patnitop to Day 3.", current_request=req, current_itinerary=itin)
        self.assertEqual(res1["intent"], "ITINERARY")
        itin1 = res1["itinerary"]
        d3_activities = itin1[2]["activities"]
        self.assertTrue(any("Patnitop" in act for act in d3_activities))

        # Turn 2: "Add Bhairavnath to Day 2."
        res2 = coordinator.route_message("Add Bhairavnath to Day 2.", current_request=req, current_itinerary=itin1)
        self.assertEqual(res2["intent"], "ITINERARY")
        itin2 = res2["itinerary"]
        d2_activities = itin2[1]["activities"]
        self.assertTrue(any("Bhairavnath" in act for act in d2_activities))

        # Turn 3: "Show Day 2."
        res3 = coordinator.route_message("Show Day 2.", current_request=req, current_itinerary=itin2)
        self.assertEqual(res3["intent"], "ITINERARY")
        self.assertIn("Day 2", res3["reply"])
        self.assertIn("Bhairavnath", res3["reply"])

    def test_scenario_5_weather(self):
        """Scenario 5: Weather intent and state preservation."""
        req = conversation_agent.understand_request("I am travelling from Delhi for 5 days")
        res = coordinator.route_message("What is the weather like in Katra?", current_request=req)

        self.assertEqual(res["intent"], "WEATHER")
        self.assertIn("Katra Weather Guidance", res["reply"])
        self.assertEqual(res["request"], req)  # state preserved
        self.assertEqual(res["tool_execution"]["tool"], "check_weather_tool")

    def test_scenario_6_booking(self):
        """Scenario 6: Human-in-the-Loop gate and RPA booking execution."""
        res_plan = coordinator.route_message("I am travelling from Delhi for 5 days with 2 travellers")
        req = res_plan["request"]
        pending_options = {"options": res_plan["plan"]["options"]}

        # Step 6a: "Book option 1." -> Gate triggered, RPA NOT executed
        res1 = coordinator.route_message("Book option 1.", current_request=req, pending_options=pending_options)
        self.assertEqual(res1["intent"], "BOOKING")
        self.assertIn("Human Confirmation Required", res1["reply"])
        self.assertEqual(res1["tool_execution"]["status"], "pending_human_confirmation")
        self.assertNotIn("rpa_info", res1)

        # Step 6b: "Yes, proceed." -> Explicit confirmation -> RPA executed
        res2 = coordinator.route_message("Yes, proceed.", current_request=req, pending_options=pending_options)
        self.assertEqual(res2["intent"], "BOOKING")
        self.assertIn("Booking Executed & Confirmed", res2["reply"])
        self.assertEqual(res2["tool_execution"]["status"], "success")
        self.assertIn("rpa_info", res2)
        self.assertIsNotNone(res2["rpa_info"].get("booking_id"))

    # ==================================================================
    # STEP 3 — STATE ISOLATION
    # ==================================================================

    def test_state_isolation_across_transitions(self):
        """Test transitions across TOURISM -> TRIP_PLANNING -> ITINERARY -> WEATHER -> BOOKING."""
        # 1. Start with TOURISM
        res_t = coordinator.route_message("Tell me about Bhairavnath.")
        self.assertIsNone(res_t["request"])

        # 2. Transition to TRIP_PLANNING
        res_tp = coordinator.route_message("I want to travel from Delhi for 4 days.")
        req_active = res_tp["request"]
        itin_active = res_tp["itinerary"]
        self.assertEqual(req_active["origin"], "Delhi")

        # 3. Transition to TOURISM while active trip exists -> trip request preserved
        res_t2 = coordinator.route_message("What should I pack?", current_request=req_active)
        self.assertEqual(res_t2["intent"], "TOURISM")
        self.assertIsNone(res_t2["request"])  # caller maintains req_active

        # 4. Transition to ITINERARY -> modifies itin_active, preserves req_active
        res_it = coordinator.route_message("Add Patnitop to Day 3.", current_request=req_active, current_itinerary=itin_active)
        self.assertEqual(res_it["intent"], "ITINERARY")
        self.assertEqual(res_it["request"], req_active)

        # 5. Transition to WEATHER -> preserves req_active
        res_w = coordinator.route_message("How is Katra weather?", current_request=req_active)
        self.assertEqual(res_w["intent"], "WEATHER")
        self.assertEqual(res_w["request"], req_active)

        # 6. Transition to BOOKING -> gate shown, preserves req_active
        res_b = coordinator.route_message("Book this option", current_request=req_active, pending_options={"options": res_tp["plan"]["options"]})
        self.assertEqual(res_b["intent"], "BOOKING")
        self.assertEqual(res_b["request"], req_active)

    # ==================================================================
    # STEP 4 — EDGE CASES
    # ==================================================================

    def test_edge_cases(self):
        """Test 15 edge cases without app crashing."""
        req = conversation_agent.understand_request("I am travelling from Delhi for 4 days with 2 travellers")
        itin = itinerary_agent.generate_default_itinerary(req)

        # 1. Empty message
        res1 = coordinator.route_message("", current_request=req)
        self.assertIsNotNone(res1["reply"])

        # 2. Unknown place
        res2 = coordinator.answer_tourism_query("Tell me about Atlantis")
        self.assertIn("places around Katra", res2["reply"])

        # 3. Unknown origin
        res3 = coordinator.process_trip_message("I am travelling from Atlantis for 5 days")
        self.assertIsNotNone(res3["reply"])

        # 4. Unsupported route
        res4 = coordinator.process_trip_message("I am travelling from Guwahati for 5 days")
        self.assertEqual(res4["plan"]["status"], "NO_AVAILABILITY")

        # 5. Invalid day number
        cmd5 = itinerary_agent.parse_itinerary_command("Show Day 99", itinerary=itin)
        valid5, err5 = itinerary_agent.validate_itinerary_command(itin, cmd5)
        self.assertFalse(valid5)

        # 6. Ambiguous "change that"
        res6 = coordinator.process_trip_message("change that", current_request=req)
        self.assertEqual(res6["plan"]["status"], "NEEDS_INFO")

        # 7. Ambiguous "move that to Day 3" without place context
        res7 = coordinator.process_itinerary_message("move that to Day 3", current_request=req, current_itinerary=itin)
        self.assertIn("Which activity", res7["reply"])

        # 8. Booking without available option
        res8 = coordinator.process_booking_message("Book option 5", current_request=req, pending_options=None)
        self.assertEqual(res8["intent"], "BOOKING")

        # 9. Booking without explicit confirmation
        res9 = coordinator.process_booking_message("Book option 1", current_request=req, pending_options={"options": [{}]})
        self.assertEqual(res9["tool_execution"]["status"], "pending_human_confirmation")

        # 10. Tool failure fallback
        res10 = tools.check_weather_tool.invoke({"location": "InvalidLocationXYZ"})
        self.assertIn("summary", res10)

        # 11. Weather fallback
        res11 = weather.get_weather("2099-01-01")
        self.assertEqual(res11["source"], "seasonal_average")

        # 12. Repeated itinerary edit
        res12_1 = coordinator.process_itinerary_message("Move Patnitop to Day 3", current_request=req, current_itinerary=itin)
        res12_2 = coordinator.process_itinerary_message("Move Patnitop to Day 3", current_request=req, current_itinerary=res12_1["itinerary"])
        self.assertIsNotNone(res12_2["itinerary"])

        # 13. Duplicate itinerary activity
        res13 = coordinator.process_itinerary_message("Add Bhairavnath to Day 2", current_request=req, current_itinerary=itin)
        res13_dup = coordinator.process_itinerary_message("Add Bhairavnath to Day 2", current_request=req, current_itinerary=res13["itinerary"])
        self.assertIsNotNone(res13_dup["itinerary"])

        # 14. Tourism query during active trip
        res14 = coordinator.route_message("Tell me about Bhairavnath", current_request=req)
        self.assertEqual(res14["intent"], "TOURISM")
        self.assertIsNone(res14["request"])

        # 15. Trip edit after tourism conversation
        res15 = coordinator.route_message("Actually make it 6 days.", current_request=req)
        self.assertEqual(res15["intent"], "TRIP_PLANNING")
        self.assertEqual(res15["request"]["duration_days"], 6)

    # ==================================================================
    # STEP 5 — RPA SAFETY VERIFICATION
    # ==================================================================

    def test_rpa_safety_verification(self):
        """Explicitly verify RPA safety rules."""
        # Gate check without confirmation
        res_gate = coordinator.process_booking_message("I want to book option 1", current_request={"origin": "Delhi"})
        self.assertEqual(res_gate["tool_execution"]["status"], "pending_human_confirmation")
        self.assertNotIn("rpa_info", res_gate)

        # Execution against safe mock portal
        rpa_info = rpa_agent.execute_playwright_mock_booking("Test User", 2, "Train from Delhi", "VIP Darshan", 1500.0, headless=True)
        self.assertEqual(rpa_info["status"], "SUCCESS")
        self.assertIn("VD-RPA-", rpa_info["booking_id"])

    # ==================================================================
    # DYNAMIC ITINERARY DURATION REGRESSION TESTS
    # ==================================================================

    def test_itinerary_duration_sync(self):
        """Verify 3-day, 5-day, 6-day itineraries and 5 -> 6 day duration synchronization."""
        # 3-day trip -> exactly 3 itinerary days
        req3 = conversation_agent.understand_request("I am travelling from Delhi for 3 days")
        plan3 = coordinator.process_trip_message("I am travelling from Delhi for 3 days")
        opt3 = plan3["plan"]["options"][0]
        itin_built3 = itinerary_agent.build_itinerary(opt3, request=req3)
        self.assertEqual(len(plan3["itinerary"]), 3)
        self.assertEqual(len(itin_built3), 3)

        # 5-day trip -> exactly 5 itinerary days
        req5 = conversation_agent.understand_request("I am travelling from Delhi for 5 days")
        plan5 = coordinator.process_trip_message("I am travelling from Delhi for 5 days")
        opt5 = plan5["plan"]["options"][0]
        itin_built5 = itinerary_agent.build_itinerary(opt5, request=req5)
        self.assertEqual(len(plan5["itinerary"]), 5)
        self.assertEqual(len(itin_built5), 5)

        # 6-day trip -> exactly 6 itinerary days
        req6 = conversation_agent.understand_request("I am travelling from Delhi for 6 days")
        plan6 = coordinator.process_trip_message("I am travelling from Delhi for 6 days")
        opt6 = plan6["plan"]["options"][0]
        itin_built6 = itinerary_agent.build_itinerary(opt6, request=req6)
        self.assertEqual(len(plan6["itinerary"]), 6)
        self.assertEqual(len(itin_built6), 6)

        # Changing 5 days -> 6 days syncs itinerary length from 5 to 6 without losing activities
        res_sync = coordinator.route_message("Actually make it 6 days.", current_request=req5, current_itinerary=plan5["itinerary"])
        self.assertEqual(res_sync["request"]["duration_days"], 6)
        self.assertEqual(len(res_sync["itinerary"]), 6)


if __name__ == "__main__":
    unittest.main()
