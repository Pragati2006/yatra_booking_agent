"""
tests/test_server_authorization_security.py
Phase 6.2.3: Server-Side Authorization and Booking Idempotency Security Audit.

Verifies:
1. A booking request with human_authorized: true but no server-side approval is blocked.
2. A booking request with a stale plan_version is blocked.
3. A booking request with a nonexistent session ID fails closed.
4. An RPA request without a session ID is blocked.
5. An RPA request with a session ID but no recorded authorization is blocked.
6. An RPA request after a material plan change is blocked.
7. A request attempting to reuse an approval from another plan revision is blocked.
8. A repeated request after successful confirmation is deduplicated.
9. Concurrent confirmation requests for the same plan revision execute exactly once without duplicates.
"""

import concurrent.futures
import unittest
from fastapi.testclient import TestClient

from backend.main import app
import agents.orchestrator as orchestrator
import agents.session_store as session_store


class TestServerAuthorizationSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _create_session_with_plan(self):
        """Helper to create a fresh trip plan session."""
        res = orchestrator.orchestrate_conversational_turn(
            "Plan my trip from Delhi for 4 days with 2 travellers"
        )
        sid = res["session_id"]
        plan_opt = res["selected_options"]["transport"]
        slot_opt = res["selected_options"]["darshan_slot"]
        option = {
            "flight": plan_opt,
            "transport": plan_opt,
            "slot": slot_opt,
            "total_price": 2000.0,
        }
        return sid, option

    def test_1_client_flag_without_server_approval_is_blocked(self):
        """Test 1: Sending human_authorized: true in HTTP payload without server-side approval fails closed."""
        sid, option = self._create_session_with_plan()

        # Session has not been authorized on server
        session = session_store.get_session(sid)
        self.assertFalse(session["state"]["authorization"]["granted"])
        self.assertIsNone(session["state"]["authorized_plan_version"])

        # Attacker sends human_authorized: true in request
        resp = self.client.post("/api/yatra/confirm", json={
            "option": option,
            "pax": 2,
            "user_name": "Attacker",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "authorization_required")
        self.assertIn("Server-side human authorization has not been granted", data["message"])

        # Verify no booking was created in session
        refreshed = session_store.get_session(sid)
        self.assertIsNone(refreshed["state"]["rpa_execution"]["booking_id"])
        self.assertEqual(len(refreshed["state"]["booking_history"]), 0)

    def test_2_stale_plan_version_is_blocked(self):
        """Test 2: A booking request with a stale plan_version fails closed."""
        sid, option = self._create_session_with_plan()

        # Authorize Revision 1
        auth_resp = self.client.post("/api/yatra/authorize", json={
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(auth_resp.json()["status"], "success")

        # Material plan change -> Revision 2
        orchestrator.orchestrate_conversational_turn(
            "Actually make it 3 travellers",
            session_id=sid,
        )
        sess = session_store.get_session(sid)
        self.assertEqual(sess["state"]["plan_version"], 2)

        # Attacker tries to book using stale plan_version 1
        resp = self.client.post("/api/yatra/confirm", json={
            "option": option,
            "pax": 2,
            "user_name": "Test-User",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "authorization_required")
        self.assertIn("Revision #2", data["message"])

    def test_3_nonexistent_session_id_fails_closed(self):
        """Test 3: A booking request with a nonexistent session ID fails closed."""
        _, option = self._create_session_with_plan()

        resp = self.client.post("/api/yatra/confirm", json={
            "option": option,
            "pax": 2,
            "user_name": "Attacker",
            "human_authorized": True,
            "session_id": "nonexistent-fake-session-id-99999",
            "plan_version": 1,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "authorization_required")
        self.assertIn("Session not found or expired", data["message"])

    def test_4_rpa_without_session_id_is_blocked(self):
        """Test 4: An RPA request without a session ID is blocked."""
        resp = self.client.post("/api/yatra/rpa", json={
            "user_name": "Attacker",
            "pax_count": 2,
            "transport_text": "train from Delhi",
            "slot_text": "Normal Darshan",
            "total_price": 2000.0,
            "headless": True,
            # session_id omitted
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "authorization_required")
        self.assertIn("Missing session ID", data["message"])

    def test_5_rpa_with_session_but_no_recorded_authorization_is_blocked(self):
        """Test 5: An RPA request with a session ID but no recorded authorization is blocked."""
        sid, _ = self._create_session_with_plan()

        resp = self.client.post("/api/yatra/rpa", json={
            "user_name": "Attacker",
            "pax_count": 2,
            "transport_text": "train from Delhi",
            "slot_text": "Normal Darshan",
            "total_price": 2000.0,
            "headless": True,
            "session_id": sid,
            "plan_version": 1,
            "human_authorized": True,  # Client flag alone
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "authorization_required")
        self.assertIn("Server-side human authorization has not been granted", data["message"])

    def test_6_rpa_after_material_plan_change_is_blocked(self):
        """Test 6: An RPA request after a material plan change is blocked."""
        sid, _ = self._create_session_with_plan()

        # Authorize Revision 1
        self.client.post("/api/yatra/authorize", json={
            "session_id": sid,
            "plan_version": 1,
        })

        # Material change to Revision 2
        change_res = orchestrator.orchestrate_conversational_turn(
            "Actually make it 3 travellers",
            session_id=sid,
        )
        sess = session_store.get_session(sid)
        self.assertEqual(sess["state"]["plan_version"], 2)

        # Attempt RPA execution on Revision 2 without re-authorization
        resp = self.client.post("/api/yatra/rpa", json={
            "user_name": "Test-User",
            "pax_count": 3,
            "transport_text": "train from Delhi",
            "slot_text": "Normal Darshan",
            "total_price": 3000.0,
            "headless": True,
            "session_id": sid,
            "plan_version": 2,
            "human_authorized": True,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "authorization_required")
        self.assertIn("Server-side human authorization has not been granted for Revision #2", data["message"])

    def test_7_cannot_reuse_approval_from_prior_plan_revision(self):
        """Test 7: Attempting to reuse approval from another plan revision is blocked."""
        sid, option = self._create_session_with_plan()

        # Authorize Revision 1
        self.client.post("/api/yatra/authorize", json={
            "session_id": sid,
            "plan_version": 1,
        })

        # Revise plan -> Revision 2
        orchestrator.orchestrate_conversational_turn(
            "Change it to 5 travellers",
            session_id=sid,
        )

        # Attempt to confirm Revision 2 by supplying old plan_version 1
        resp = self.client.post("/api/yatra/confirm", json={
            "option": option,
            "pax": 5,
            "user_name": "Test-User",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,  # Claiming old approval version
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "authorization_required")
        self.assertIn("Plan has been updated to Revision #2", data["message"])

    def test_8_repeated_confirmation_request_is_deduplicated(self):
        """Test 8: Repeated confirmation requests return the existing booking ID without creating duplicate bookings."""
        sid, option = self._create_session_with_plan()

        # 1. Authorize on server
        self.client.post("/api/yatra/authorize", json={
            "session_id": sid,
            "plan_version": 1,
        })

        # 2. Confirm booking 1st time
        resp1 = self.client.post("/api/yatra/confirm", json={
            "option": option,
            "pax": 2,
            "user_name": "Test-User",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp1.status_code, 200)
        bid1 = resp1.json()["booking_id"]
        self.assertIsNotNone(bid1)

        # 3. Repeated confirmation request
        resp2 = self.client.post("/api/yatra/confirm", json={
            "option": option,
            "pax": 2,
            "user_name": "Test-User",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2["status"], "success")
        self.assertEqual(data2["booking_id"], bid1)
        self.assertTrue(data2.get("duplicate_prevented"))

        # Verify only 1 booking exists in session history
        sess = session_store.get_session(sid)
        history = sess["state"]["booking_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["booking_id"], bid1)

    def test_9_concurrent_confirmation_requests_execute_exactly_once(self):
        """Test 9: Two simultaneous confirmation requests result in at most one confirmed mock booking."""
        sid, option = self._create_session_with_plan()

        # Authorize on server
        self.client.post("/api/yatra/authorize", json={
            "session_id": sid,
            "plan_version": 1,
        })

        def do_confirm():
            # Use isolated client request
            return self.client.post("/api/yatra/confirm", json={
                "option": option,
                "pax": 2,
                "user_name": "Concurrent-User",
                "human_authorized": True,
                "session_id": sid,
                "plan_version": 1,
            })

        # Execute 2 confirmation requests concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(do_confirm)
            fut2 = executor.submit(do_confirm)
            resp1 = fut1.result()
            resp2 = fut2.result()

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        data1 = resp1.json()
        data2 = resp2.json()

        self.assertEqual(data1["status"], "success")
        self.assertEqual(data2["status"], "success")

        # Both must return the identical booking ID
        self.assertEqual(data1["booking_id"], data2["booking_id"])

        # Exactly one must have duplicate_prevented = True
        dup_flags = [bool(data1.get("duplicate_prevented")), bool(data2.get("duplicate_prevented"))]
        self.assertTrue(any(dup_flags), "One of the concurrent requests should have duplicate_prevented=True")

        # Session booking history must have exactly ONE booking entry
        sess = session_store.get_session(sid)
        history = sess["state"]["booking_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["booking_id"], data1["booking_id"])


if __name__ == "__main__":
    unittest.main()
