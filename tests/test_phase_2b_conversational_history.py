"""
tests/test_phase_2b_conversational_history.py
Focused automated test suite for Phase 2B:
- Backend-persisted dialogue history in SQLite.
- Safe trip context preservation (no null-overwrite on tourism/weather/itinerary queries).
- GET /api/chat/history/{session_id} API endpoint verification.
- Two-turn exact message count verification (no duplicates).
- Session isolation for messages and state.
- Unknown session retrieval handling.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    elif hasattr(sys.stdout, "buffer") and not sys.stdout.buffer.closed:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

from fastapi.testclient import TestClient

import db
from backend.main import app
from agents import orchestrator, session_store


class TestPhase2BConversationalHistory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_phase_2b.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        db.ensure_live_data()
        self.client = TestClient(app)

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_two_chat_turns_produce_exact_two_user_and_two_assistant_messages(self):
        """Verify that exactly 2 chat turns generate 2 user messages and 2 assistant messages without duplicates."""
        # Turn 1
        resp1 = self.client.post("/api/chat", json={
            "message": "I want to plan a yatra to Vaishno Devi",
        })
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        sid = data1["session_id"]
        self.assertIsNotNone(sid)

        # Check history after turn 1
        hist1 = self.client.get(f"/api/chat/history/{sid}").json()
        self.assertEqual(hist1["session_id"], sid)
        self.assertEqual(len(hist1["messages"]), 2)
        self.assertEqual(hist1["messages"][0]["role"], "user")
        self.assertEqual(hist1["messages"][0]["content"], "I want to plan a yatra to Vaishno Devi")
        self.assertEqual(hist1["messages"][1]["role"], "assistant")
        self.assertEqual(hist1["messages"][1]["content"], data1["reply"])

        # Turn 2
        resp2 = self.client.post("/api/chat", json={
            "message": "We are 2 people travelling from Delhi for 3 days with budget 15000",
            "session_id": sid,
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()

        # Check history after turn 2
        hist2 = self.client.get(f"/api/chat/history/{sid}").json()
        self.assertEqual(len(hist2["messages"]), 4)
        self.assertEqual(hist2["messages"][0]["role"], "user")
        self.assertEqual(hist2["messages"][1]["role"], "assistant")
        self.assertEqual(hist2["messages"][2]["role"], "user")
        self.assertEqual(hist2["messages"][2]["content"], "We are 2 people travelling from Delhi for 3 days with budget 15000")
        self.assertEqual(hist2["messages"][3]["role"], "assistant")
        self.assertEqual(hist2["messages"][3]["content"], data2["reply"])

    def test_tourism_query_does_not_overwrite_active_trip_requirements(self):
        """
        Verify the context-overwrite fix:
        Asking a tourism query in an active trip session preserves origin, pax, duration, and budget.
        """
        # Step 1: Create trip plan
        resp1 = self.client.post("/api/chat", json={
            "message": "Plan a 4-day trip from Delhi for 2 travellers with budget ₹20,000",
        })
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        sid = data1["session_id"]
        self.assertEqual(data1["request"]["origin"], "Delhi")
        self.assertEqual(data1["request"]["duration_days"], 4)
        self.assertEqual(data1["request"]["pax"], 2)

        # Step 2: Tourism inquiry (e.g. Aarti timings)
        resp2 = self.client.post("/api/chat", json={
            "message": "What are the Aarti timings?",
            "session_id": sid,
            "current_request": data1["request"],
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()

        # The response MUST NOT return request: null!
        self.assertIsNotNone(data2.get("request"))
        self.assertEqual(data2["request"]["origin"], "Delhi")
        self.assertEqual(data2["request"]["duration_days"], 4)
        self.assertEqual(data2["request"]["pax"], 2)
        self.assertEqual(data2["request"]["total_budget"], 20000.0)

        # Step 3: Check SQLite session store requirements directly
        session_row = session_store.get_session(sid, db_path=self.temp_db_path)
        self.assertIsNotNone(session_row)
        reqs = session_row["state"]["requirements"]
        self.assertEqual(reqs["origin"], "Delhi")
        self.assertEqual(reqs["duration_days"], 4)
        self.assertEqual(reqs["pax"], 2)

        # Step 4: Subsequent trip replanning turn works seamlessly
        resp3 = self.client.post("/api/chat", json={
            "message": "Change travel mode to flight",
            "session_id": sid,
            "current_request": data2["request"],
        })
        self.assertEqual(resp3.status_code, 200)
        data3 = resp3.json()
        self.assertEqual(data3["request"]["origin"], "Delhi")
        self.assertEqual(data3["request"]["mode"], "flight")
        self.assertEqual(data3["request"]["pax"], 2)

    def test_unknown_session_history_endpoint(self):
        """Unknown session IDs should return an empty messages list without creating a new session row."""
        unknown_id = "completely-unknown-session-9999"
        resp = self.client.get(f"/api/chat/history/{unknown_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["session_id"], unknown_id)
        self.assertEqual(data["messages"], [])

        # Verify no session row was created as a side effect
        session_row = session_store.get_session(unknown_id, db_path=self.temp_db_path)
        self.assertIsNone(session_row)

    def test_message_history_session_isolation(self):
        """Ensure messages in Session A never appear in Session B."""
        respA = self.client.post("/api/chat", json={"message": "Pilgrim A starting from Mumbai"})
        sidA = respA.json()["session_id"]

        respB = self.client.post("/api/chat", json={"message": "Pilgrim B starting from Kolkata"})
        sidB = respB.json()["session_id"]

        self.assertNotEqual(sidA, sidB)

        histA = self.client.get(f"/api/chat/history/{sidA}").json()["messages"]
        histB = self.client.get(f"/api/chat/history/{sidB}").json()["messages"]

        self.assertEqual(len(histA), 2)
        self.assertEqual(len(histB), 2)

        # Verify content isolation
        self.assertIn("Mumbai", histA[0]["content"])
        self.assertNotIn("Kolkata", histA[0]["content"])

        self.assertIn("Kolkata", histB[0]["content"])
        self.assertNotIn("Mumbai", histB[0]["content"])

    def test_multiple_sequential_tourism_queries_preserve_trip_requirements(self):
        """Sequential tourism queries must retain active trip state across all turns without loss."""
        # 1. Establish trip
        resp1 = self.client.post("/api/chat", json={
            "message": "Travelling from Delhi for 4 days with 2 travellers and a budget of ₹25,000",
        })
        sid = resp1.json()["session_id"]
        trip_req = resp1.json()["request"]

        # 2. Query 1: Aarti timings
        resp2 = self.client.post("/api/chat", json={
            "message": "What are the Aarti timings?",
            "session_id": sid,
            "current_request": trip_req,
        })
        self.assertEqual(resp2.json()["request"]["origin"], "Delhi")
        self.assertEqual(resp2.json()["request"]["pax"], 2)

        # 3. Query 2: Tell me about Bhairavnath
        resp3 = self.client.post("/api/chat", json={
            "message": "Tell me about Bhairavnath",
            "session_id": sid,
            "current_request": resp2.json()["request"],
        })
        self.assertEqual(resp3.json()["request"]["origin"], "Delhi")
        self.assertEqual(resp3.json()["request"]["pax"], 2)

        # 4. Query 3: Weather inquiry
        resp4 = self.client.post("/api/chat", json={
            "message": "How is the weather in Katra?",
            "session_id": sid,
            "current_request": resp3.json()["request"],
        })
        self.assertEqual(resp4.json()["request"]["origin"], "Delhi")
        self.assertEqual(resp4.json()["request"]["pax"], 2)
        self.assertEqual(resp4.json()["request"]["total_budget"], 25000.0)

        # Check total messages in history: 1 plan + 3 info = 4 user + 4 assistant = 8 messages
        hist = self.client.get(f"/api/chat/history/{sid}").json()
        self.assertEqual(len(hist["messages"]), 8)

    def test_history_records_plan_revision_and_metadata(self):
        """Assistant messages record plan_version metadata during replanning."""
        resp1 = self.client.post("/api/chat", json={
            "message": "Plan a 3-day trip from Delhi for 1 person with budget 10000",
        })
        sid = resp1.json()["session_id"]
        self.assertEqual(resp1.json()["plan_version"], 1)

        # Replan
        resp2 = self.client.post("/api/chat", json={
            "message": "Change it to flight",
            "session_id": sid,
        })
        self.assertEqual(resp2.json()["plan_version"], 2)

        hist = self.client.get(f"/api/chat/history/{sid}").json()["messages"]
        self.assertEqual(len(hist), 4)

        # Assistant turn 1 has plan_version: 1
        self.assertEqual(hist[1]["metadata"].get("plan_version"), 1)
        # Assistant turn 2 has plan_version: 2
        self.assertEqual(hist[3]["metadata"].get("plan_version"), 2)


if __name__ == "__main__":
    unittest.main()

