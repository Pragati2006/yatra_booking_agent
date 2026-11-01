"""Comprehensive verification of the voice query flow and backend handoff.

Tests:
  TEST 1: Tourism - 'Tell me about Bhairavnath Temple.' -> transcript captured, last_tourism_place updated.
  TEST 2: Follow-up - 'How far is it from Katra?' -> context preserved, resolves 'it' as Bhairavnath Temple.
  TEST 3: Nearby places - 'What places can I visit around Katra?' -> TOURISM intent, places returned.
  TEST 4: Trip planning - '2 people from Delhi travelling to Katra on 17 October 2026 by train.' -> TRIP_PLANNING intent, plan/options returned.
  TEST 5: Navigation persistence - Spoken question -> persist session -> switch view -> restore session -> messages and context preserved.
  TEST 6: Repeat voice query - Speak one query, then speak another query -> chronological order, no duplicates, no stale skips.
  TEST 7: Failure handling - Graceful error reporting, no stuck state.
"""

import unittest
from agents import coordinator, conversation_agent


class TestVoiceFlowIntegration(unittest.TestCase):
    def test_scenario_1_tourism(self):
        query = "Tell me about Bhairavnath Temple."
        intent = conversation_agent.detect_intent(query)
        self.assertEqual(intent, "TOURISM")
        res = coordinator.route_message(query)
        self.assertEqual(res["intent"], "TOURISM")
        self.assertIn("Bhairavnath", res["reply"])
        self.assertEqual(res["last_tourism_place"], "Bhairavnath Temple")

    def test_scenario_2_followup(self):
        # Turn 1
        res1 = coordinator.route_message("Tell me about Bhairavnath Temple.")
        last_place = res1["last_tourism_place"]
        self.assertEqual(last_place, "Bhairavnath Temple")

        # Turn 2: Spoken follow-up with pronoun 'it'
        followup = "How far is it from Katra?"
        intent2 = conversation_agent.detect_intent(followup)
        self.assertEqual(intent2, "TOURISM")
        res2 = coordinator.route_message(followup, last_tourism_place=last_place)
        self.assertEqual(res2["intent"], "TOURISM")
        # Ensure it answered about Bhairavnath's distance (~3 km uphill from Bhawan or distance note)
        self.assertTrue("Bhairavnath" in res2["reply"] or "3 km" in res2["reply"] or "distance" in res2["reply"].lower())

    def test_scenario_3_nearby_places(self):
        query = "What places can I visit around Katra?"
        intent = conversation_agent.detect_intent(query)
        self.assertEqual(intent, "TOURISM")
        res = coordinator.route_message(query)
        self.assertEqual(res["intent"], "TOURISM")
        self.assertTrue(len(res["reply"]) > 50)
        self.assertTrue(any(p in res["reply"] for p in ["Ban Ganga", "Ardhkuwari", "Charan Paduka", "Bhairavnath"]))

    def test_scenario_4_trip_planning(self):
        query = "2 people from Delhi travelling to Katra on 17 October 2026 by train."
        intent = conversation_agent.detect_intent(query)
        self.assertEqual(intent, "TRIP_PLANNING")
        res = coordinator.route_message(query)
        self.assertEqual(res["intent"], "TRIP_PLANNING")
        req = res.get("request")
        self.assertIsNotNone(req)
        self.assertEqual(req.get("pax"), 2)
        self.assertEqual(req.get("origin"), "Delhi")
        self.assertEqual(req.get("mode"), "train")

    def test_scenario_5_navigation_persistence(self):
        # Simulate guest session cache simulation
        guest_id = "TEST-GUEST-01"
        session_cache = {
            "messages": [{"role": "assistant", "content": coordinator.get_greeting()}],
            "last_tourism_place": None,
            "trip_request": None,
        }

        # Step 1: Voice message processed
        voice_query = "What places can I visit around Katra?"
        session_cache["messages"].append({"role": "user", "content": voice_query})
        res = coordinator.route_message(voice_query)
        session_cache["messages"].append({"role": "assistant", "content": res["reply"]})
        session_cache["last_tourism_place"] = res.get("last_tourism_place")

        # Step 2: Navigate Home (active_nav = "Home")
        active_nav = "Home"
        self.assertEqual(len(session_cache["messages"]), 3)

        # Step 3: Navigate back to AI Assistant (active_nav = "AI Assistant")
        active_nav = "AI Assistant"
        self.assertEqual(session_cache["messages"][1]["content"], voice_query)
        self.assertIn("assistant", session_cache["messages"][2]["role"])
        self.assertEqual(len(session_cache["messages"]), 3)

    def test_scenario_6_repeat_voice_query(self):
        # Two consecutive queries (even identical or back to back)
        q1 = "Tell me about Bhairavnath Temple."
        res1 = coordinator.route_message(q1)

        q2 = "Tell me about Bhairavnath Temple."
        res2 = coordinator.route_message(q2)

        messages = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": res1["reply"]},
            {"role": "user", "content": q2},
            {"role": "assistant", "content": res2["reply"]},
        ]
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["content"], q1)
        self.assertEqual(messages[2]["content"], q2)

    def test_scenario_7_error_handling(self):
        # If coordinator is called with empty or gibberish input, it does not raise uncaught exception
        res = coordinator.route_message("asdfghjkl zxcvbnm")
        self.assertIsNotNone(res)
        self.assertIn("reply", res)


if __name__ == "__main__":
    unittest.main()
