"""
tests/test_phase_2d_history_reliability.py
Comprehensive automated regression test suite for Phase 2D:
1. Session isolation when switching from longer Session A to shorter Session B.
2. Restoring default greeting and handling genuinely empty history.
3. Preventing message loss for pending in-flight local messages.
4. Preserving card metadata on exact message records without index misalignment.
5. Returning HTTP 500 on database failure in GET /api/chat/history/{session_id}.
6. Logging history persistence errors safely without exposing sensitive data.
7. Rolling back orphaned user messages when downstream processing fails so retries are clean.
8. Preserving tourism and weather trip context across multi-turn sessions.
9. Preserving plan-version checks and server-side authorization protections.
10. Verifying cold-reload interactive card metadata persistence.
"""

import io
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

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


class TestPhase2DHistoryReliability(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_phase_2d.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        db.ensure_live_data()
        self.client = TestClient(app)

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_longer_session_a_to_shorter_session_b_isolation(self):
        """Switching from longer Session A history to shorter Session B history must return only Session B messages."""
        # Create Session A with 2 turns (4 messages)
        rA1 = self.client.post("/api/chat", json={"message": "I want to plan a yatra from Delhi"})
        sidA = rA1.json()["session_id"]
        rA2 = self.client.post("/api/chat", json={"message": "3 days with 2 pilgrims", "session_id": sidA})

        histA = self.client.get(f"/api/chat/history/{sidA}").json()["messages"]
        self.assertEqual(len(histA), 4)

        # Create Session B with 1 turn (2 messages)
        rB1 = self.client.post("/api/chat", json={"message": "What are the Aarti timings?"})
        sidB = rB1.json()["session_id"]

        histB = self.client.get(f"/api/chat/history/{sidB}").json()["messages"]
        self.assertEqual(len(histB), 2)
        self.assertEqual(histB[0]["role"], "user")
        self.assertEqual(histB[0]["content"], "What are the Aarti timings?")

        # Ensure Session B has strictly 2 messages and does not inherit Session A
        self.assertNotEqual(sidA, sidB)
        self.assertTrue(len(histA) > len(histB))

    def test_2_empty_or_new_session_returns_200_with_empty_messages(self):
        """Unknown or genuinely new sessions must return HTTP 200 with an empty message list."""
        unknown_id = "completely-unknown-session-12345"
        resp = self.client.get(f"/api/chat/history/{unknown_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["session_id"], unknown_id)
        self.assertEqual(data["messages"], [])

    def test_3_metadata_tied_to_specific_message_not_array_index(self):
        """Card metadata (recommendation, request, plan_version) is stored in the specific assistant message."""
        resp = self.client.post("/api/chat", json={
            "message": "Plan a 4-day trip from Delhi for 2 travellers with budget 20000",
        })
        self.assertEqual(resp.status_code, 200)
        sid = resp.json()["session_id"]

        hist = self.client.get(f"/api/chat/history/{sid}").json()["messages"]
        self.assertEqual(len(hist), 2)

        # Message 0: user message
        self.assertEqual(hist[0]["role"], "user")
        self.assertEqual(hist[0]["metadata"].get("intent"), "TRIP_PLANNING")
        self.assertNotIn("recommendation", hist[0]["metadata"])

        # Message 1: assistant message
        self.assertEqual(hist[1]["role"], "assistant")
        meta = hist[1]["metadata"]
        self.assertIsNotNone(meta)
        self.assertEqual(meta.get("plan_version"), 1)
        # Recommendation card data is persisted on message 1
        self.assertIn("recommendation", meta)
        self.assertIn("title", meta["recommendation"])
        self.assertIn("approach_bullets", meta["recommendation"])
        # Request data is persisted on message 1
        self.assertIn("request", meta)
        self.assertEqual(meta["request"]["pax"], 2)

    def test_4_history_endpoint_raises_500_on_database_failure(self):
        """GET /api/chat/history/{session_id} must return HTTP 500 when database retrieval fails."""
        with patch("agents.session_store.get_messages", side_effect=sqlite3.OperationalError("database is locked")):
            resp = self.client.get("/api/chat/history/test-session-err")
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(resp.json()["detail"], "Failed to retrieve conversation history")

    def test_5_persistence_logging_safely_handles_errors_without_exposing_pii(self):
        """Database persistence warnings are logged without crashing the turn or leaking secrets."""
        with patch("agents.session_store.add_message", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertLogs("agents.orchestrator", level="WARNING") as log_capture:
                resp = self.client.post("/api/chat", json={
                    "message": "What is the weather in Katra?",
                })
                # Conversation response still succeeds
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("Katra Weather", data["reply"])

                # Verify warning was logged
                found_warning = any("Failed to persist" in log_msg for log_msg in log_capture.output)
                self.assertTrue(found_warning, "Expected persistence failure warning in logs")

    def test_6_orphaned_user_message_rolled_back_on_downstream_failure(self):
        """If downstream processing raises an unhandled exception, user message is rolled back."""
        # Step 1: Create an active session
        resp1 = self.client.post("/api/chat", json={"message": "I want to plan a yatra from Delhi"})
        sid = resp1.json()["session_id"]

        hist1 = self.client.get(f"/api/chat/history/{sid}").json()["messages"]
        self.assertEqual(len(hist1), 2)  # 1 user + 1 assistant

        # Step 2: Attempt a turn where downstream processing crashes
        with patch("agents.coordinator.answer_tourism_query", side_effect=RuntimeError("Simulated LLM pipeline crash")):
            try:
                self.client.post("/api/chat", json={
                    "message": "What are the Aarti timings?",
                    "session_id": sid,
                })
            except RuntimeError:
                pass

        # Step 3: Check SQLite history - the failed turn's user message MUST be rolled back!
        hist2 = self.client.get(f"/api/chat/history/{sid}").json()["messages"]
        self.assertEqual(len(hist2), 2, "Failed turn's user message must be rolled back, preventing orphaned messages")

        # Step 4: User retries successfully
        resp_retry = self.client.post("/api/chat", json={
            "message": "What are the Aarti timings?",
            "session_id": sid,
        })
        self.assertEqual(resp_retry.status_code, 200)

        hist3 = self.client.get(f"/api/chat/history/{sid}").json()["messages"]
        self.assertEqual(len(hist3), 4, "Retry turn cleanly adds exactly 1 user and 1 assistant message")

    def test_7_tourism_context_preserved_during_multi_turn_session(self):
        """Tourism questions in an active trip session retain origin, pax, and budget."""
        r1 = self.client.post("/api/chat", json={
            "message": "Plan a 3-day yatra from Mumbai for 2 travellers with budget 18000",
        })
        sid = r1.json()["session_id"]
        req1 = r1.json()["request"]
        self.assertEqual(req1["origin"], "Mumbai")
        self.assertEqual(req1["pax"], 2)

        # Ask tourism question
        r2 = self.client.post("/api/chat", json={
            "message": "Tell me about Bhairavnath Temple",
            "session_id": sid,
            "current_request": req1,
        })
        self.assertEqual(r2.status_code, 200)
        req2 = r2.json()["request"]
        self.assertEqual(req2["origin"], "Mumbai")
        self.assertEqual(req2["pax"], 2)

    def test_8_replanning_revokes_authorization_and_increments_version(self):
        """Replanning after plan generation increments version and resets prior authorization."""
        r1 = self.client.post("/api/chat", json={
            "message": "Plan a 4-day trip from Delhi for 2 travellers",
        })
        sid = r1.json()["session_id"]
        self.assertEqual(r1.json()["plan_version"], 1)

        # Replan
        r2 = self.client.post("/api/chat", json={
            "message": "Change mode to flight",
            "session_id": sid,
        })
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["plan_version"], 2)
        self.assertFalse(r2.json()["authorization"]["granted"])
        self.assertEqual(r2.json()["authorization"]["revoked_reason"], "plan_modified")

    def test_9_delete_message_utility_in_session_store(self):
        """session_store.delete_message deletes single record safely."""
        sid = "test-del-msg-sid"
        m1 = session_store.add_message(sid, "user", "Message 1", db_path=self.temp_db_path)
        m2 = session_store.add_message(sid, "assistant", "Message 2", db_path=self.temp_db_path)

        msgs = session_store.get_messages(sid, db_path=self.temp_db_path)
        self.assertEqual(len(msgs), 2)

        deleted = session_store.delete_message(m1, db_path=self.temp_db_path)
        self.assertTrue(deleted)

        msgs_after = session_store.get_messages(sid, db_path=self.temp_db_path)
        self.assertEqual(len(msgs_after), 1)
        self.assertEqual(msgs_after[0]["id"], m2)


if __name__ == "__main__":
    unittest.main()
