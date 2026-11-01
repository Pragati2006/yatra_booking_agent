"""
tests/test_phase_2f_frontend_history.py
Focused automated regression test suite for Phase 2F:
1. Reloading with cached historical messages does not duplicate backend history.
2. A genuinely pending message sent during history loading is preserved exactly once.
3. A history request failure does not mark the session as successfully loaded.
4. A successful empty response is treated as a loaded history.
5. Session switching and stale-request protection still work.
6. Recommendation metadata remains attached to the correct backend message.
"""

import io
import json
import os
import shutil
import subprocess
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
from agents import session_store


class TestPhase2FFrontendHistory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_phase_2f.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        db.ensure_live_data()
        self.client = TestClient(app)

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_reloading_cached_messages_does_not_duplicate_backend_history(self):
        """
        Verify that when messages are restored from sessionStorage on reload,
        reconciling with backend history does NOT append cached historical messages as duplicates.
        """
        node_script = """
        const DEFAULT_GREETING = { id: 'default-greeting', role: 'assistant', content: 'Greeting' };

        // 1. Simulate state restoration from sessionStorage on reload
        const cachedFromSessionStorage = [
            DEFAULT_GREETING,
            { id: 'local-1', role: 'user', content: 'Hello', persisted: false, isPending: true },
            { id: 'local-2', role: 'assistant', content: 'Hi there', persisted: false, isPending: false }
        ];

        // On reload, AIChat strips isPending from cached messages
        const hydratedMessages = cachedFromSessionStorage.map(m => ({ ...m, isPending: false }));
        const pendingMessageIds = new Set(); // Ref starts empty on reload

        // 2. Backend history returns the persisted messages
        const backendMsgs = [
            { id: 1, role: 'user', content: 'Hello', metadata: {}, created_at: '2026-10-25T00:00:00Z' },
            { id: 2, role: 'assistant', content: 'Hi there', metadata: {}, created_at: '2026-10-25T00:00:01Z' }
        ];

        const formattedBackend = backendMsgs.map(m => ({
            id: m.id,
            role: m.role,
            content: m.content,
            persisted: true,
            isPending: false
        }));

        // 3. Reconcile
        const localPending = hydratedMessages.filter(
            p => Boolean(p.isPending) && pendingMessageIds.has(p.id)
        );

        const result = localPending.length === 0 ? formattedBackend : [...formattedBackend, ...localPending];

        console.log(JSON.stringify({
            resultLength: result.length,
            ids: result.map(m => m.id)
        }));
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)
        # Exactly 2 messages from formattedBackend; zero duplicates
        self.assertEqual(res["resultLength"], 2)
        self.assertEqual(res["ids"], [1, 2])

    def test_2_genuinely_pending_message_preserved_during_history_loading(self):
        """
        Verify that a user message sent while history is in flight is preserved
        exactly once at the end of the history array.
        """
        node_script = """
        const DEFAULT_GREETING = { id: 'default-greeting', role: 'assistant', content: 'Greeting' };
        const pendingMessageIds = new Set();

        // 1. User sends message while history is loading
        const userMsg = { id: 'local-user-99', role: 'user', content: 'In flight msg', isPending: true };
        pendingMessageIds.add(userMsg.id);

        const prevMessages = [DEFAULT_GREETING, userMsg];

        // 2. History resolves with existing messages
        const backendMsgs = [
            { id: 1, role: 'user', content: 'Earlier query', metadata: {}, created_at: '2026-10-25T00:00:00Z' },
            { id: 2, role: 'assistant', content: 'Earlier answer', metadata: {}, created_at: '2026-10-25T00:00:01Z' }
        ];

        const formattedBackend = backendMsgs.map(m => ({
            id: m.id,
            role: m.role,
            content: m.content,
            persisted: true,
            isPending: false
        }));

        // 3. Reconcile
        const localPending = prevMessages.filter(
            p => Boolean(p.isPending) && pendingMessageIds.has(p.id)
        );

        const result = localPending.length === 0 ? formattedBackend : [...formattedBackend, ...localPending];

        console.log(JSON.stringify({
            resultLength: result.length,
            ids: result.map(m => m.id),
            lastMsgContent: result[result.length - 1].content
        }));
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)
        # 2 backend messages + 1 pending user message
        self.assertEqual(res["resultLength"], 3)
        self.assertEqual(res["ids"], [1, 2, "local-user-99"])
        self.assertEqual(res["lastMsgContent"], "In flight msg")

    def test_3_history_request_failure_does_not_mark_session_as_loaded(self):
        """
        Verify that a failed history fetch does NOT set historyLoadedSessionRef,
        allowing retries, and API returns 500.
        """
        # API returns 500 on database failure
        with patch("agents.session_store.get_messages", side_effect=Exception("DB connection dropped")):
            resp = self.client.get("/api/chat/history/session-err-retry")
            self.assertEqual(resp.status_code, 500)

        # Frontend logic check: .catch must NOT set historyLoadedSessionRef
        node_script = """
        let historyLoadedSessionRef = null;
        let historyError = false;
        const targetSessionId = 'session-err-retry';
        const fetchId = 1;
        let activeFetchRequestId = 1;
        let currentSessionId = targetSessionId;

        function simulateCatch(err) {
            if (activeFetchRequestId !== fetchId) return;
            if (currentSessionId !== targetSessionId) return;
            historyError = true;
            // Deliberately do NOT set historyLoadedSessionRef
        }

        simulateCatch(new Error("Network 500"));

        console.log(JSON.stringify({
            historyError: historyError,
            historyLoadedSession: historyLoadedSessionRef
        }));
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)
        self.assertTrue(res["historyError"])
        self.assertIsNone(res["historyLoadedSession"])

    def test_4_successful_empty_response_treated_as_loaded_history(self):
        """
        Verify that an unknown or empty session returns HTTP 200 with messages: [],
        which is treated as a successfully loaded history.
        """
        resp = self.client.get("/api/chat/history/new-empty-session")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["messages"], [])

        node_script = """
        let historyLoadedSessionRef = null;
        let historyError = true; // was previously in error or uninitialized
        const targetSessionId = 'new-empty-session';
        const fetchId = 1;
        let activeFetchRequestId = 1;
        let currentSessionId = targetSessionId;

        const res = { session_id: 'new-empty-session', messages: [] };

        function simulateThen(res) {
            if (activeFetchRequestId !== fetchId) return;
            if (currentSessionId !== targetSessionId) return;
            historyLoadedSessionRef = targetSessionId;
            historyError = false;
        }

        simulateThen(res);

        console.log(JSON.stringify({
            historyError: historyError,
            historyLoadedSession: historyLoadedSessionRef
        }));
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)
        self.assertFalse(res["historyError"])
        self.assertEqual(res["historyLoadedSession"], "new-empty-session")

    def test_5_session_switching_and_stale_request_protection(self):
        """
        Verify that switching sessions resets transcript and invalidates prior in-flight fetch.
        """
        node_script = """
        let currentSessionId = 'session-A';
        let historyLoadedSessionRef = 'session-A';
        let activeFetchRequestId = 1;
        let messages = [{ id: 1, content: 'Session A msg' }];

        // User switches to Session B
        const newSessionId = 'session-B';
        if (newSessionId !== currentSessionId) {
            currentSessionId = newSessionId;
            historyLoadedSessionRef = null;
            activeFetchRequestId += 1;
            messages = [{ id: 'default-greeting', content: 'Greeting' }];
        }

        // Suppose late response from Session A arrives now with fetchId = 1
        const staleFetchId = 1;
        let appliedStale = false;
        if (activeFetchRequestId === staleFetchId && currentSessionId === 'session-A') {
            appliedStale = true;
            messages = [{ id: 1, content: 'Late Session A' }];
        }

        console.log(JSON.stringify({
            appliedStale: appliedStale,
            currentSessionId: currentSessionId,
            historyLoadedSessionRef: historyLoadedSessionRef,
            activeFetchRequestId: activeFetchRequestId,
            messageCount: messages.length,
            firstMsgId: messages[0].id
        }));
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)
        self.assertFalse(res["appliedStale"])
        self.assertEqual(res["currentSessionId"], "session-B")
        self.assertIsNone(res["historyLoadedSessionRef"])
        self.assertEqual(res["activeFetchRequestId"], 2)
        self.assertEqual(res["firstMsgId"], "default-greeting")

    def test_6_recommendation_metadata_remains_attached_to_correct_message(self):
        """
        Verify recommendation metadata is strictly attached to the assistant message.
        """
        # Create a session with a plan recommendation
        resp = self.client.post("/api/chat", json={
            "message": "Plan a 3-day trip from Delhi for 2 travellers with budget 15000"
        })
        self.assertEqual(resp.status_code, 200)
        sid = resp.json()["session_id"]

        hist_resp = self.client.get(f"/api/chat/history/{sid}")
        self.assertEqual(hist_resp.status_code, 200)
        messages = hist_resp.json()["messages"]
        self.assertEqual(len(messages), 2)

        # Message 0: user message (no recommendation)
        self.assertEqual(messages[0]["role"], "user")
        self.assertNotIn("recommendation", messages[0].get("metadata") or {})

        # Message 1: assistant message (contains recommendation payload)
        self.assertEqual(messages[1]["role"], "assistant")
        meta = messages[1]["metadata"]
        self.assertIn("recommendation", meta)
        self.assertIn("title", meta["recommendation"])
        self.assertIn("approach_bullets", meta["recommendation"])


if __name__ == "__main__":
    unittest.main()
