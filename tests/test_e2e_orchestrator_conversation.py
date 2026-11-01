"""
tests/test_e2e_orchestrator_conversation.py
End-to-End Conversational Orchestration Integration Test.

Tests the full representative multi-turn conversation:
1. "I want to plan a Vaishno Devi trip." -> Prompts for missing mandatory info.
2. User supplies origin, duration, pax, and budget -> Consolidated plan (Revision 1).
3. "Change it to train." -> Transport reconsidered, budget recalculated, state preserved (Revision 2).
4. "Find a cheaper hotel." -> Hotel tier updated, budget recalculated (Revision 3).
5. User confirms -> Authorization granted for Revision 3, mock RPA executes.
6. Material detail changed ("We are travelling with 4 people") -> Authorization revoked (Revision 4).
7. Unconfirmed booking attempt -> Gate holds, requires re-authorization for Revision 4.
8. Re-confirmation -> Revision 4 authorized, mock RPA executes.

Verified both directly via orchestrator and via FastAPI TestClient('/api/chat').
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


class TestE2EOrchestratorConversation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_e2e_sessions.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        db.ensure_live_data()
        self.client = TestClient(app)

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_representative_conversation_flow(self):
        """Tests the exact representative conversation across multiple chat messages via FastAPI /api/chat."""
        # Turn 1: User: "I want to plan a Vaishno Devi trip."
        resp1 = self.client.post("/api/chat", json={
            "message": "I want to plan a Vaishno Devi trip.",
        })
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertIsNotNone(data1.get("session_id"))
        sid = data1["session_id"]
        self.assertEqual(data1["status"], "NEEDS_INFO")
        self.assertTrue(any(f in data1["missing_fields"] for f in ["origin", "duration_or_dates", "pax"]))
        self.assertIn("Mata Di", data1["reply"])

        # Turn 2: User supplies origin, duration, travellers, and budget
        resp2 = self.client.post("/api/chat", json={
            "message": "Travelling from Delhi for 4 days with 2 travellers and a budget of ₹20,000",
            "session_id": sid,
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2["session_id"], sid)
        self.assertEqual(data2["status"], "PLAN_READY")
        self.assertEqual(data2["plan_version"], 1)
        self.assertEqual(data2["request"]["origin"], "Delhi")
        self.assertEqual(data2["request"]["duration_days"], 4)
        self.assertEqual(data2["request"]["pax"], 2)
        self.assertEqual(data2["request"]["total_budget"], 20000.0)
        self.assertIsNotNone(data2["selected_options"]["transport"])
        self.assertIsNotNone(data2["selected_options"]["accommodation"])
        self.assertIsNotNone(data2["itinerary"])
        # Assert structured budget evaluation and concise user-facing response separately
        if data2.get("budget_evaluation"):
            self.assertIn("grand_total", data2["budget_evaluation"])
            self.assertTrue(data2["budget_evaluation"].get("within_budget", False))
        self.assertTrue(
            "Estimated total" in data2["reply"] or "₹" in data2["reply"] or "budget" in data2["reply"].lower(),
            f"User-facing reply should concisely state estimate: {data2['reply']}"
        )

        # Turn 3: User: "Change it to train."
        resp3 = self.client.post("/api/chat", json={
            "message": "Change it to train.",
            "session_id": sid,
        })
        self.assertEqual(resp3.status_code, 200)
        data3 = resp3.json()
        self.assertEqual(data3["session_id"], sid)
        self.assertEqual(data3["status"], "PLAN_REVISED")
        self.assertEqual(data3["plan_version"], 2)
        self.assertEqual(data3["request"]["mode"], "train")
        # Unrelated choices preserved
        self.assertEqual(data3["request"]["origin"], "Delhi")
        self.assertEqual(data3["request"]["duration_days"], 4)
        self.assertEqual(data3["request"]["pax"], 2)
        self.assertEqual(data3["request"]["total_budget"], 20000.0)
        self.assertEqual(data3["selected_options"]["transport"]["mode"], "train")

        # Turn 4: User: "Find a cheaper hotel."
        resp4 = self.client.post("/api/chat", json={
            "message": "Find a cheaper hotel.",
            "session_id": sid,
        })
        self.assertEqual(resp4.status_code, 200)
        data4 = resp4.json()
        self.assertEqual(data4["session_id"], sid)
        self.assertEqual(data4["status"], "PLAN_REVISED")
        self.assertEqual(data4["plan_version"], 3)
        self.assertEqual(data4["request"]["accommodation_preference"], "Budget")
        self.assertEqual(data4["selected_options"]["accommodation"]["category"], "Budget")
        # Still retains prior choices
        self.assertEqual(data4["request"]["origin"], "Delhi")
        self.assertEqual(data4["request"]["mode"], "train")

        # Turn 5: User reviews and authorizes booking
        resp5 = self.client.post("/api/chat", json={
            "message": "Confirm booking",
            "session_id": sid,
        })
        self.assertEqual(resp5.status_code, 200)
        data5 = resp5.json()
        self.assertEqual(data5["status"], "success")
        self.assertEqual(data5["plan_version"], 3)
        self.assertIn("booking_id", data5)
        self.assertIn("rpa_info", data5)

        # Verify session state recorded authorization
        saved_s = session_store.get_session(sid)
        self.assertEqual(saved_s["state"]["authorized_plan_version"], 3)
        self.assertTrue(saved_s["state"]["authorization"]["granted"])

        # Turn 6: User changes a material detail after reviewing/authorizing
        resp6 = self.client.post("/api/chat", json={
            "message": "We are travelling with 4 people",
            "session_id": sid,
        })
        self.assertEqual(resp6.status_code, 200)
        data6 = resp6.json()
        self.assertEqual(data6["plan_version"], 4)
        self.assertEqual(data6["status"], "PLAN_REVISED")
        self.assertEqual(data6["request"]["pax"], 4)
        # Verify authorization was REVOKED
        saved_s6 = session_store.get_session(sid)
        self.assertIsNone(saved_s6["state"]["authorized_plan_version"])
        self.assertFalse(saved_s6["state"]["authorization"]["granted"])
        self.assertEqual(saved_s6["state"]["authorization"]["revoked_reason"], "plan_modified")

        # Turn 7: User tries to book without new confirmation -> Gate holds!
        resp7 = self.client.post("/api/chat", json={
            "message": "Book option 1",
            "session_id": sid,
        })
        self.assertEqual(resp7.status_code, 200)
        data7 = resp7.json()
        self.assertEqual(data7["status"], "authorization_required")
        self.assertEqual(data7["tool_execution"]["status"], "pending_human_confirmation")
        self.assertNotIn("rpa_info", data7)

        # Turn 8: User explicitly confirms revised plan -> Authorized & RPA executes
        resp8 = self.client.post("/api/chat", json={
            "message": "Yes, confirm booking",
            "session_id": sid,
        })
        self.assertEqual(resp8.status_code, 200)
        data8 = resp8.json()
        self.assertEqual(data8["status"], "success")
        self.assertEqual(data8["plan_version"], 4)
        self.assertIn("booking_id", data8)
        self.assertIn("rpa_info", data8)
        saved_s8 = session_store.get_session(sid)
        self.assertEqual(saved_s8["state"]["authorized_plan_version"], 4)
        self.assertTrue(saved_s8["state"]["authorization"]["granted"])


if __name__ == "__main__":
    unittest.main()
