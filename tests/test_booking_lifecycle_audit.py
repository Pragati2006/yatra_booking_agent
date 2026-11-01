"""
tests/test_booking_lifecycle_audit.py
Phase 6.2.2 — Booking Lifecycle and Authorization Audit Suite.

Tests:
1. Duplicate confirmation requests do not create duplicate bookings (idempotency).
2. Existing booking is accurately archived in booking_history when plan details change.
3. Session state does not falsely indicate an outdated plan was booked (rpa_execution reset for new revision).
4. Direct API /api/yatra/confirm enforces authorization, validates plan_version, and prevents duplicate bookings.
5. Direct API /api/yatra/rpa enforces authorization gate when session_id is supplied.
6. Full 9-step scenario from Section 3:
   - Generate plan (Rev 1).
   - Confirm via mock RPA.
   - Change pax or transport (Rev 2).
   - Invalidate previous approval.
   - Accurately represent previous booking without claiming cancellation.
   - Attempt unconfirmed booking -> blocked.
   - Reconfirm revised plan -> new booking associated with Rev 2.
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


class TestBookingLifecycleAudit(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_lifecycle_sessions.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        db.ensure_live_data()
        self.client = TestClient(app)

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_duplicate_confirmation_prevention_idempotency(self):
        """Tests that repeating 'Confirm booking' on the same plan version returns existing booking and does not re-run RPA."""
        # Step 1: Generate plan
        res_plan = orchestrator.orchestrate_conversational_turn(
            "Plan my trip from Delhi for 4 days with 2 travellers"
        )
        sid = res_plan["session_id"]
        self.assertEqual(res_plan["plan_version"], 1)

        # Step 2: Confirm booking
        res_confirm1 = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res_confirm1["status"], "success")
        bid1 = res_confirm1["booking_id"]
        self.assertIsNotNone(bid1)

        # Step 3: Repeated confirmation request without modifying plan
        res_confirm2 = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res_confirm2["status"], "success")
        self.assertEqual(res_confirm2["booking_id"], bid1)  # Exact same booking ID
        self.assertTrue(res_confirm2.get("duplicate_prevented"))
        self.assertIn("already confirmed", res_confirm2["reply"].lower())

    def test_existing_booking_representation_after_plan_change(self):
        """
        Executes the exact 9-step scenario from Section 3:
        1. Generate a trip plan.
        2. Confirm it through authorized mock RPA workflow.
        3. Change passenger count or transport mode.
        4. Verify that previous approval is invalidated.
        5. Verify that previous booking's status is represented accurately.
        6. Attempt to book revised plan without reconfirmation.
        7. Verify execution is blocked.
        8. Explicitly reconfirm revised plan.
        9. Verify new booking is associated with correct plan revision.
        """
        # Step 1: Generate plan (Revision 1)
        res_plan = orchestrator.orchestrate_conversational_turn(
            "Plan my yatra from Delhi for 4 days with 2 pilgrims"
        )
        sid = res_plan["session_id"]
        self.assertEqual(res_plan["plan_version"], 1)

        # Step 2: Confirm booking for Revision 1
        res_book1 = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res_book1["status"], "success")
        self.assertEqual(res_book1["plan_version"], 1)
        bid1 = res_book1["booking_id"]

        session_after_book1 = session_store.get_session(sid)
        self.assertEqual(session_after_book1["state"]["authorized_plan_version"], 1)
        self.assertTrue(session_after_book1["state"]["authorization"]["granted"])
        self.assertEqual(session_after_book1["state"]["rpa_execution"]["booking_id"], bid1)

        # Step 3: Change passenger count or transport mode
        res_change = orchestrator.orchestrate_conversational_turn(
            "We are travelling with 4 people",
            session_id=sid,
        )
        self.assertEqual(res_change["plan_version"], 2)
        self.assertEqual(res_change["status"], "PLAN_REVISED")

        # Step 4: Verify previous approval is invalidated
        session_after_change = session_store.get_session(sid)
        self.assertIsNone(session_after_change["state"]["authorized_plan_version"])
        self.assertFalse(session_after_change["state"]["authorization"]["granted"])
        self.assertEqual(session_after_change["state"]["authorization"]["revoked_reason"], "plan_modified")

        # Step 5: Verify previous booking's status is represented accurately
        # Session state must NOT falsely indicate Revision 2 was booked
        self.assertIsNone(session_after_change["state"]["rpa_execution"]["booking_id"])
        self.assertEqual(session_after_change["state"]["rpa_execution"]["status"], "PENDING_RECONFIRMATION")
        prev_b = session_after_change["state"]["rpa_execution"]["previous_booking"]
        self.assertIsNotNone(prev_b)
        self.assertEqual(prev_b["booking_id"], bid1)
        self.assertEqual(prev_b["plan_version"], 1)
        self.assertEqual(prev_b["status"], "CONFIRMED_PRIOR_REVISION")
        # Communicated limitation: prior booking remains on file; no fake cancellation claimed
        self.assertIn("remains on file", prev_b["note"].lower())
        self.assertIn(bid1, res_change["reply"])

        # Step 6 & 7: Attempt to book revised plan without reconfirmation -> blocked!
        res_unconfirmed_attempt = orchestrator.orchestrate_conversational_turn(
            "Book option 1",
            session_id=sid,
        )
        self.assertEqual(res_unconfirmed_attempt["status"], "authorization_required")
        self.assertEqual(res_unconfirmed_attempt["plan_version"], 2)
        self.assertNotIn("rpa_info", res_unconfirmed_attempt)
        self.assertIn("Revision #2", res_unconfirmed_attempt["reply"])

        # Step 8: Explicitly reconfirm revised plan
        res_reconfirm = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res_reconfirm["status"], "success")

        # Step 9: Verify new booking is associated with correct plan revision (Revision 2)
        self.assertEqual(res_reconfirm["plan_version"], 2)
        bid2 = res_reconfirm["booking_id"]
        self.assertIsNotNone(bid2)
        self.assertNotEqual(bid1, bid2)

        session_after_reconfirm = session_store.get_session(sid)
        self.assertEqual(session_after_reconfirm["state"]["authorized_plan_version"], 2)
        self.assertTrue(session_after_reconfirm["state"]["authorization"]["granted"])
        self.assertEqual(session_after_reconfirm["state"]["rpa_execution"]["booking_id"], bid2)
        self.assertEqual(session_after_reconfirm["state"]["rpa_execution"]["plan_version"], 2)
        # Check booking history contains both bookings
        history = session_after_reconfirm["state"]["booking_history"]
        self.assertTrue(any(b["booking_id"] == bid1 and b["plan_version"] == 1 for b in history))
        self.assertTrue(any(b["booking_id"] == bid2 and b["plan_version"] == 2 for b in history))

    def test_direct_api_confirm_validation_and_deduplication(self):
        """Tests that direct POST /api/yatra/confirm validates session, plan_version, and prevents duplicate booking."""
        # Establish a session with an active plan
        res_plan = orchestrator.orchestrate_conversational_turn(
            "Plan my trip from Delhi for 4 days with 2 travellers"
        )
        sid = res_plan["session_id"]
        plan_opt = res_plan["selected_options"]["transport"]
        slot_opt = res_plan["selected_options"]["darshan_slot"]
        option_combo = {"transport": plan_opt, "slot": slot_opt, "total_price": 2000.0}

        # 1. Direct call without human authorization -> Blocked
        resp_unauth = self.client.post("/api/yatra/confirm", json={
            "option": option_combo,
            "pax": 2,
            "user_name": "Test-User",
            "human_authorized": False,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp_unauth.status_code, 200)
        self.assertEqual(resp_unauth.json()["status"], "authorization_required")

        # 2. Record server-side authorization
        resp_grant = self.client.post("/api/yatra/authorize", json={
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp_grant.status_code, 200)
        self.assertEqual(resp_grant.json()["status"], "success")

        # 3. Direct call with human authorization -> Success
        resp_auth = self.client.post("/api/yatra/confirm", json={
            "option": option_combo,
            "pax": 2,
            "user_name": "Test-User",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp_auth.status_code, 200)
        auth_data = resp_auth.json()
        self.assertEqual(auth_data["status"], "success")
        bid = auth_data["booking_id"]

        # 3. Repeated call with same version -> Deduplicated
        resp_dup = self.client.post("/api/yatra/confirm", json={
            "option": option_combo,
            "pax": 2,
            "user_name": "Test-User",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp_dup.status_code, 200)
        dup_data = resp_dup.json()
        self.assertEqual(dup_data["status"], "success")
        self.assertEqual(dup_data["booking_id"], bid)
        self.assertTrue(dup_data.get("duplicate_prevented"))

        # 4. Modify plan in session -> Revision 2
        orchestrator.orchestrate_conversational_turn(
            "Change it to train",
            session_id=sid,
        )

        # 5. Call /api/yatra/confirm with stale plan_version 1 -> Blocked!
        resp_stale = self.client.post("/api/yatra/confirm", json={
            "option": option_combo,
            "pax": 2,
            "user_name": "Test-User",
            "human_authorized": True,
            "session_id": sid,
            "plan_version": 1,
        })
        self.assertEqual(resp_stale.status_code, 200)
        self.assertEqual(resp_stale.json()["status"], "authorization_required")
        self.assertIn("Revision #2", resp_stale.json()["message"])

    def test_direct_api_rpa_authorization_gate(self):
        """Tests that direct POST /api/yatra/rpa cannot bypass authorization when session_id is provided."""
        res_plan = orchestrator.orchestrate_conversational_turn(
            "Plan my trip from Delhi for 4 days with 2 travellers"
        )
        sid = res_plan["session_id"]

        # 1. Direct RPA call without human_authorized -> Blocked
        resp_unauth = self.client.post("/api/yatra/rpa", json={
            "user_name": "Test-User",
            "pax_count": 2,
            "transport_text": "train from Delhi",
            "slot_text": "Normal Darshan",
            "total_price": 2000.0,
            "headless": True,
            "session_id": sid,
            "human_authorized": False,
        })
        self.assertEqual(resp_unauth.status_code, 200)
        self.assertEqual(resp_unauth.json()["status"], "authorization_required")

        # 2. Direct RPA call with stale plan version -> Blocked
        resp_stale = self.client.post("/api/yatra/rpa", json={
            "user_name": "Test-User",
            "pax_count": 2,
            "transport_text": "train from Delhi",
            "slot_text": "Normal Darshan",
            "total_price": 2000.0,
            "headless": True,
            "session_id": sid,
            "plan_version": 999,  # Mismatched version
            "human_authorized": True,
        })
        self.assertEqual(resp_stale.status_code, 200)
        self.assertEqual(resp_stale.json()["status"], "authorization_required")


if __name__ == "__main__":
    unittest.main()
