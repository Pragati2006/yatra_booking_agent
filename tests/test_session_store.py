"""
tests/test_session_store.py
Automated tests for agents.session_store.
Verifies session creation, retrieval, updates, isolation, corruption handling, and persistence across db restarts.
All tests run against isolated temporary databases and never mutate live data.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest

from agents import session_store


class TestSessionStore(unittest.TestCase):

    def setUp(self):
        # Create an isolated temporary directory for test databases
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_sessions.db")

    def tearDown(self):
        # Clean up temporary database files
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_session_creation_and_retrieval(self):
        """Test creating a new session with automatic UUID and retrieving it."""
        session = session_store.create_session(
            initial_state={"requirements": {"origin": "Delhi", "pax": 3}},
            db_path=self.db_path,
        )

        sid = session["session_id"]
        self.assertTrue(len(sid) >= 16)
        self.assertEqual(session["status"], "INIT")
        self.assertEqual(session["state"]["requirements"]["origin"], "Delhi")
        self.assertEqual(session["state"]["requirements"]["pax"], 3)

        # Retrieve and verify exact fields
        retrieved = session_store.get_session(sid, db_path=self.db_path)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["session_id"], sid)
        self.assertEqual(retrieved["state"]["requirements"]["origin"], "Delhi")
        self.assertEqual(retrieved["state"]["requirements"]["pax"], 3)
        self.assertEqual(retrieved["state"]["requirements"]["destination"], "Katra")

    def test_explicit_session_id(self):
        """Test creating a session with an explicitly specified session ID."""
        custom_id = "test-custom-session-1234"
        session = session_store.create_session(
            session_id=custom_id,
            status="ACTIVE",
            db_path=self.db_path,
        )
        self.assertEqual(session["session_id"], custom_id)
        self.assertEqual(session["status"], "ACTIVE")

        retrieved = session_store.get_session(custom_id, db_path=self.db_path)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["session_id"], custom_id)

    def test_updating_without_losing_unrelated_fields(self):
        """Test updating state merges properly without wiping out other fields."""
        session = session_store.create_session(
            initial_state={
                "requirements": {"origin": "Mumbai", "pax": 4, "total_budget": 25000},
                "selected_options": {"transport": {"mode": "train"}},
            },
            db_path=self.db_path,
        )
        sid = session["session_id"]

        # Update only duration_days inside requirements, and accommodation in selected_options
        updated = session_store.update_session(
            session_id=sid,
            updates={
                "requirements": {"duration_days": 5},
                "selected_options": {"accommodation": {"name": "Trikuta Residency"}},
            },
            status="PLAN_READY",
            db_path=self.db_path,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "PLAN_READY")
        # Verify updated fields
        self.assertEqual(updated["state"]["requirements"]["duration_days"], 5)
        self.assertEqual(updated["state"]["selected_options"]["accommodation"]["name"], "Trikuta Residency")
        # Verify preserved fields
        self.assertEqual(updated["state"]["requirements"]["origin"], "Mumbai")
        self.assertEqual(updated["state"]["requirements"]["pax"], 4)
        self.assertEqual(updated["state"]["requirements"]["total_budget"], 25000)
        self.assertEqual(updated["state"]["selected_options"]["transport"]["mode"], "train")

    def test_persistence_after_closing_and_reopening(self):
        """Test that data survives opening fresh connections (simulating process restarts)."""
        session = session_store.create_session(
            initial_state={"requirements": {"origin": "Kolkata"}},
            db_path=self.db_path,
        )
        sid = session["session_id"]

        # Reopen with fresh call
        retrieved = session_store.get_session(sid, db_path=self.db_path)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["state"]["requirements"]["origin"], "Kolkata")

    def test_unknown_session_identifier(self):
        """Test that querying non-existent session IDs returns None safely."""
        self.assertIsNone(session_store.get_session("non-existent-id", db_path=self.db_path))
        self.assertIsNone(session_store.get_session("", db_path=self.db_path))
        self.assertIsNone(session_store.get_session(None, db_path=self.db_path))
        self.assertIsNone(session_store.update_session("non-existent-id", {"pax": 2}, db_path=self.db_path))

    def test_session_isolation(self):
        """Test that multiple sessions are completely isolated from one another."""
        s1 = session_store.create_session(
            initial_state={"requirements": {"origin": "Delhi", "pax": 2}},
            db_path=self.db_path,
        )
        s2 = session_store.create_session(
            initial_state={"requirements": {"origin": "Bangalore", "pax": 5}},
            db_path=self.db_path,
        )

        self.assertNotEqual(s1["session_id"], s2["session_id"])

        # Update s1
        session_store.update_session(s1["session_id"], {"requirements": {"origin": "Jaipur"}}, db_path=self.db_path)

        # Check s1 and s2
        res1 = session_store.get_session(s1["session_id"], db_path=self.db_path)
        res2 = session_store.get_session(s2["session_id"], db_path=self.db_path)

        self.assertEqual(res1["state"]["requirements"]["origin"], "Jaipur")
        self.assertEqual(res2["state"]["requirements"]["origin"], "Bangalore")
        self.assertEqual(res2["state"]["requirements"]["pax"], 5)

    def test_malformed_state_handling(self):
        """Test that corrupt JSON in the database is caught and handled safely."""
        session_store.init_db(self.db_path)

        # Inject invalid JSON directly into the table
        corrupt_id = "corrupted-session-row"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (session_id, status, created_at, updated_at, state_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (corrupt_id, "ERROR", "2026-10-18T00:00:00Z", "2026-10-18T00:00:00Z", "{invalid-json-data"),
            )
            conn.commit()

        # get_session should not raise an unhandled exception
        session = session_store.get_session(corrupt_id, db_path=self.db_path)
        self.assertIsNotNone(session)
        self.assertTrue(session.get("_corrupted", False))
        self.assertEqual(session["status"], "CORRUPTED")

    def test_delete_and_list_sessions(self):
        """Test listing and deleting sessions."""
        s1 = session_store.create_session(db_path=self.db_path)
        s2 = session_store.create_session(db_path=self.db_path)

        sessions = session_store.list_sessions(db_path=self.db_path)
        self.assertEqual(len(sessions), 2)

        # Delete s1
        deleted = session_store.delete_session(s1["session_id"], db_path=self.db_path)
        self.assertTrue(deleted)

        sessions_after = session_store.list_sessions(db_path=self.db_path)
        self.assertEqual(len(sessions_after), 1)
        self.assertEqual(sessions_after[0]["session_id"], s2["session_id"])

    def test_message_persistence_and_ordering(self):
        """Test persisting multiple messages and verifying chronological order."""
        sid = "test-msg-session-1"
        session_store.create_session(session_id=sid, db_path=self.db_path)

        id1 = session_store.add_message(sid, "user", "Hello yatra agent", metadata={"intent": "GREETING"}, db_path=self.db_path)
        id2 = session_store.add_message(sid, "assistant", "🙏 Jai Mata Di! Welcome.", metadata={"plan_version": 1}, db_path=self.db_path)
        id3 = session_store.add_message(sid, "user", "Plan trip from Delhi", metadata={"intent": "TRIP_PLANNING"}, db_path=self.db_path)

        self.assertIsNotNone(id1)
        self.assertIsNotNone(id2)
        self.assertIsNotNone(id3)
        self.assertTrue(id1 < id2 < id3)

        msgs = session_store.get_messages(sid, db_path=self.db_path)
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "Hello yatra agent")
        self.assertEqual(msgs[0]["metadata"], {"intent": "GREETING"})

        self.assertEqual(msgs[1]["role"], "assistant")
        self.assertEqual(msgs[1]["content"], "🙏 Jai Mata Di! Welcome.")
        self.assertEqual(msgs[1]["metadata"], {"plan_version": 1})

        self.assertEqual(msgs[2]["role"], "user")
        self.assertEqual(msgs[2]["content"], "Plan trip from Delhi")

    def test_message_session_isolation(self):
        """Test that messages are strictly isolated between sessions."""
        s1 = "session-iso-1"
        s2 = "session-iso-2"

        session_store.add_message(s1, "user", "Message for session 1", db_path=self.db_path)
        session_store.add_message(s2, "user", "Message for session 2", db_path=self.db_path)

        msgs1 = session_store.get_messages(s1, db_path=self.db_path)
        msgs2 = session_store.get_messages(s2, db_path=self.db_path)

        self.assertEqual(len(msgs1), 1)
        self.assertEqual(msgs1[0]["content"], "Message for session 1")

        self.assertEqual(len(msgs2), 1)
        self.assertEqual(msgs2[0]["content"], "Message for session 2")

    def test_unknown_session_messages(self):
        """Test retrieving messages for non-existent session returns empty list safely."""
        msgs = session_store.get_messages("non-existent-session-id", db_path=self.db_path)
        self.assertEqual(msgs, [])
        self.assertEqual(session_store.get_messages(None, db_path=self.db_path), [])
        self.assertEqual(session_store.get_messages("", db_path=self.db_path), [])

    def test_clear_messages_and_cascade_delete(self):
        """Test clear_messages and delete_session removes messages."""
        sid = "session-to-clear"
        session_store.create_session(session_id=sid, db_path=self.db_path)
        session_store.add_message(sid, "user", "Msg 1", db_path=self.db_path)
        session_store.add_message(sid, "assistant", "Msg 2", db_path=self.db_path)

        self.assertEqual(len(session_store.get_messages(sid, db_path=self.db_path)), 2)

        # Clear messages
        cleared = session_store.clear_messages(sid, db_path=self.db_path)
        self.assertTrue(cleared)
        self.assertEqual(session_store.get_messages(sid, db_path=self.db_path), [])

        # Session record still exists
        self.assertIsNotNone(session_store.get_session(sid, db_path=self.db_path))

        # Add message again, then delete session -> should cascade delete messages
        session_store.add_message(sid, "user", "Msg 3", db_path=self.db_path)
        session_store.delete_session(sid, db_path=self.db_path)
        self.assertIsNone(session_store.get_session(sid, db_path=self.db_path))
        self.assertEqual(session_store.get_messages(sid, db_path=self.db_path), [])


if __name__ == "__main__":
    unittest.main()

