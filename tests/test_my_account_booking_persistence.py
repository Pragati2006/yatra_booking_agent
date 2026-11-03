"""
tests/test_my_account_booking_persistence.py
Systematic test suite validating Phase 2, 3, 4, 5 & 6 requirements:
1. Authenticated booking is persisted in SQLite.
2. Booking contains the correct user_id.
3. My Bookings API (/api/auth/saved-bookings) returns the newly completed booking.
4. Correct booking count returned.
5. All booking details match the final confirmation.
6. Booking reference matches the generated Demo Pilgrim Pass and PDF pass.
7. Refreshing preserves booking history (persisted permanently in SQLite).
8. Logging out and logging back in preserves the booking.
9. Another user cannot retrieve this booking (strict cross-user isolation).
10. Guest access to booking history is rejected with 401 Unauthorized.
11. Duplicate confirmation preserves idempotency and does not create duplicate bookings.
12. Failed or expired workflows do not appear as confirmed bookings.
"""

import os
import sys
from dotenv import load_dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
load_dotenv(os.path.join(project_root, ".env"))

import uuid
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from agents.auth_service import auth_service, get_email_provider
import agents.session_store as session_store
from utils.pdf_generator import generate_pdf_pass_bytes


class TestMyAccountBookingPersistence(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.provider = get_email_provider()

    def _login_user(self, email: str):
        self.client.post("/api/auth/request-otp", json={"email": email})
        otp = self.provider.get_latest_otp_for(email)
        self.assertIsNotNone(otp)
        verify_res = self.client.post("/api/auth/verify-otp", json={"email": email, "otp_code": otp})
        self.assertEqual(verify_res.status_code, 200)
        data = verify_res.json()
        return data["user"], data["session_token"]

    def test_1_and_2_and_3_and_4_and_5_authenticated_booking_persisted(self):
        """Tests 1, 2, 3, 4, 5: Authenticated booking is persisted with user_id, retrieved via API, details match."""
        email = f"pilgrim_{uuid.uuid4().hex[:6]}@example.com"
        user, token = self._login_user(email)
        headers = {"Authorization": f"Bearer {token}"}

        # Initially, user has 0 bookings
        res0 = self.client.get("/api/auth/saved-bookings", headers=headers)
        self.assertEqual(res0.status_code, 200)
        self.assertEqual(res0.json()["count"], 0)
        self.assertEqual(len(res0.json()["bookings"]), 0)

        # Create session and workflow
        sid = f"sess_{uuid.uuid4().hex[:8]}"
        session_store.create_session(
            session_id=sid,
            initial_state={
                "plan_version": 1,
                "authorization": {"granted": True},
                "authorized_plan_version": 1,
                "requirements": {"origin": "Delhi", "pax": 3, "start_date": "2026-10-25"},
                "hotel": {"name": "Devi Darshan Hotel (Katra)"},
                "pending_options": {
                    "slot": {"category": "VIP Darshan", "slot_date": "2026-10-25", "slot_time": "Morning (06:00)"},
                    "transport": "Train (Vande Bharat Express)",
                    "total_price": 18500.0,
                },
            },
            user_id=user["user_id"],
        )

        simulated_bid = f"VD-RPA-{uuid.uuid4().hex[:6].upper()}"

        def fake_start(*args, **kwargs):
            wf = session_store.create_user_workflow(
                session_id=kwargs.get("session_id", sid),
                state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
                step="security_checkpoint",
                operation="yatra_mock_booking",
                pending_action="ENTER_OTP_IN_PORTAL",
                checkpoint_data={
                    "user_name": kwargs.get("user_name", "Rohan Sharma"),
                    "pax_count": kwargs.get("pax_count", 3),
                    "transport_text": kwargs.get("transport_text"),
                    "slot_text": kwargs.get("slot_text"),
                    "total_price": kwargs.get("total_price", 18500.0),
                    "checkpoint_mode": "OTP",
                },
            )
            return {
                "status": "PAUSED",
                "workflow_id": wf["workflow_id"],
                "state": wf["state"],
                "checkpoint_mode": "OTP",
                "session_id": sid,
            }

        def fake_resume(*args, **kwargs):
            w_id = kwargs.get("workflow_id")
            s_id = kwargs.get("session_id")
            session_store.update_user_workflow(
                workflow_id=w_id,
                session_id=s_id,
                state=session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED,
                step="booking_confirmed",
                pending_action="NONE",
                checkpoint_data={
                    "booking_id": simulated_bid,
                    "user_name": "Rohan Sharma",
                    "pax_count": 3,
                    "slot_date": "2026-10-25",
                    "category": "VIP Darshan",
                    "slot_time": "Morning (06:00)",
                    "total_price": 18500.0,
                    "transport_text": "Train (Vande Bharat Express) from Delhi",
                },
            )
            return {
                "status": "SUCCESS",
                "workflow_id": w_id,
                "session_id": s_id,
                "booking_id": simulated_bid,
                "state": "USER_ACTION_COMPLETED",
                "user_name": "Rohan Sharma",
                "pax_count": 3,
                "slot_date": "2026-10-25",
                "category": "VIP Darshan",
                "slot_time": "Morning (06:00)",
                "total_price": 18500.0,
                "transport_text": "Train (Vande Bharat Express) from Delhi",
            }

        with patch("agents.coordinator.start_user_controlled_workflow", side_effect=fake_start), \
             patch("agents.coordinator.resume_user_controlled_workflow", side_effect=fake_resume):

            # Start workflow
            start_res = self.client.post(
                "/api/yatra/rpa/workflow/start",
                json={
                    "session_id": sid,
                    "user_name": "Rohan Sharma",
                    "pax_count": 3,
                    "transport_text": "Train (Vande Bharat Express) from Delhi",
                    "slot_text": "VIP Darshan",
                    "total_price": 18500.0,
                    "checkpoint_mode": "OTP",
                    "headless": True,
                    "plan_version": 1,
                    "human_authorized": True,
                },
                headers=headers,
            )
            self.assertEqual(start_res.status_code, 200)
            start_data = start_res.json()
            wf_id = start_data["workflow_id"]
            self.assertEqual(start_data["status"], "PAUSED")

            # Resume workflow with OTP clearance
            resume_res = self.client.post(
                "/api/yatra/rpa/workflow/resume",
                json={
                    "session_id": sid,
                    "workflow_id": wf_id,
                    "user_confirmed_action": True,
                    "manual_input_value": "123456",
                    "simulate_manual_clearance": True,
                    "headless": True,
                },
                headers=headers,
            )
            self.assertEqual(resume_res.status_code, 200)
            resume_data = resume_res.json()
            self.assertEqual(resume_data["status"], "SUCCESS")
            booking_id = resume_data["booking_id"]
            self.assertEqual(booking_id, simulated_bid)

        # Test 1 & 2: Check SQLite persistence directly
        db_bookings = auth_service.get_user_bookings(user_id=user["user_id"])
        self.assertEqual(len(db_bookings), 1, "Exactly one booking must be persisted in SQLite")
        saved_b = db_bookings[0]
        self.assertEqual(saved_b["booking_id"], booking_id)
        self.assertEqual(saved_b["user_id"], user["user_id"], "Booking must contain the authenticated user's ID")
        self.assertEqual(saved_b["status"], "SIMULATED_CONFIRMED")

        # Test 3 & 4: My Bookings API returns the newly completed booking with count = 1
        api_res = self.client.get("/api/auth/saved-bookings", headers=headers)
        self.assertEqual(api_res.status_code, 200)
        api_data = api_res.json()
        self.assertEqual(api_data["status"], "success")
        self.assertEqual(api_data["count"], 1)
        self.assertEqual(len(api_data["bookings"]), 1)

        # Test 5: All booking details match the confirmation
        b = api_data["bookings"][0]
        self.assertEqual(b["booking_id"], booking_id)
        self.assertEqual(b["user_name"], "Rohan Sharma")
        self.assertEqual(b["pax_count"], 3)
        self.assertEqual(b["slot_date"], "2026-10-25")
        self.assertEqual(b["category"], "VIP Darshan")
        self.assertEqual(b["total_price"], 18500.0)
        self.assertIn("receipt", b)
        receipt = b["receipt"]
        self.assertEqual(receipt.get("portal_label"), "LOCAL MOCK PORTAL / DEMO")
        self.assertEqual(receipt.get("disclaimer"), "NOT AN OFFICIAL SHRINE BOARD BOOKING")

    def test_6_booking_reference_matches_pdf_pass(self):
        """Test 6: Booking reference matches the generated Demo Pilgrim Pass and PDF endpoint."""
        email = f"pdf_pilgrim_{uuid.uuid4().hex[:6]}@example.com"
        user, token = self._login_user(email)
        headers = {"Authorization": f"Bearer {token}"}

        # Save booking directly
        bid = f"VD-RPA-{uuid.uuid4().hex[:6].upper()}"
        auth_service.save_booking(
            user_id=user["user_id"],
            booking_data={
                "booking_id": bid,
                "user_name": "Devotee Priya",
                "pax_count": 2,
                "slot_date": "2026-10-20",
                "category": "Normal Darshan",
                "slot_time": "06:00",
                "transport_info": "Vande Bharat Express",
                "hotel_name": "Devi Darshan Hotel",
                "total_price": 12000.0,
            },
        )

        # Request PDF pass from endpoint
        pdf_res = self.client.get(f"/api/yatra/booking/{bid}/pdf", headers=headers)
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers["content-type"], "application/pdf")
        self.assertIn(f"attachment; filename=\"Pilgrim_Pass_{bid}.pdf\"", pdf_res.headers["content-disposition"])
        self.assertTrue(pdf_res.content.startswith(b"%PDF-1.4"))
        self.assertIn(bid.encode("ascii"), pdf_res.content, "PDF content must contain exact booking reference")

    def test_7_and_8_refresh_and_relogin_preserves_booking(self):
        """Tests 7 & 8: Refreshing and logging out/in preserves booking history."""
        email = f"persist_{uuid.uuid4().hex[:6]}@example.com"
        user, token1 = self._login_user(email)
        headers1 = {"Authorization": f"Bearer {token1}"}

        bid = f"VD-RPA-{uuid.uuid4().hex[:6].upper()}"
        auth_service.save_booking(
            user_id=user["user_id"],
            booking_data={
                "booking_id": bid,
                "user_name": "Devotee Amit",
                "pax_count": 4,
                "total_price": 24000.0,
            },
        )

        # Check 1 (simulating refresh)
        res1 = self.client.get("/api/auth/saved-bookings", headers=headers1)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["count"], 1)

        # Logout
        self.client.post("/api/auth/logout", headers=headers1)

        # Login again (new session token)
        user2, token2 = self._login_user(email)
        self.assertEqual(user2["user_id"], user["user_id"])
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Check 2 (after re-login)
        res2 = self.client.get("/api/auth/saved-bookings", headers=headers2)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["count"], 1)
        self.assertEqual(res2.json()["bookings"][0]["booking_id"], bid)

    def test_9_cross_user_isolation(self):
        """Test 9: Another user cannot retrieve User A's booking."""
        user_a, token_a = self._login_user(f"user_a_{uuid.uuid4().hex[:6]}@example.com")
        user_b, token_b = self._login_user(f"user_b_{uuid.uuid4().hex[:6]}@example.com")

        bid_a = f"VD-RPA-{uuid.uuid4().hex[:6].upper()}"
        auth_service.save_booking(
            user_id=user_a["user_id"],
            booking_data={"booking_id": bid_a, "user_name": "User A", "pax_count": 1},
        )

        # User B lists bookings -> should see 0
        res_b = self.client.get("/api/auth/saved-bookings", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(res_b.status_code, 200)
        self.assertEqual(res_b.json()["count"], 0)

        # User B tries to get specific booking of User A -> 404
        detail_res = self.client.get(
            f"/api/auth/saved-bookings/{bid_a}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        self.assertEqual(detail_res.status_code, 404)

        # User B tries to download User A's PDF -> 404
        pdf_res = self.client.get(
            f"/api/yatra/booking/{bid_a}/pdf",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        self.assertEqual(pdf_res.status_code, 404)

    def test_10_guest_access_rejected(self):
        """Test 10: Guest access to booking history is rejected with 401 Unauthorized."""
        res = self.client.get("/api/auth/saved-bookings")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json()["detail"])

        detail_res = self.client.get("/api/auth/saved-bookings/VD-RPA-999999")
        self.assertEqual(detail_res.status_code, 401)

    def test_11_duplicate_confirmation_idempotent(self):
        """Test 11: Duplicate confirmation does not create duplicate bookings in SQLite."""
        user, token = self._login_user(f"idemp_{uuid.uuid4().hex[:6]}@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        bid = f"VD-RPA-{uuid.uuid4().hex[:6].upper()}"

        # First save
        res1 = self.client.post(
            "/api/auth/save-booking",
            json={
                "booking_id": bid,
                "user_name": "Devotee Suresh",
                "pax_count": 2,
                "total_price": 10000.0,
            },
            headers=headers,
        )
        self.assertEqual(res1.status_code, 200)

        # Repeat same save (simulating re-submission or page reload)
        res2 = self.client.post(
            "/api/auth/save-booking",
            json={
                "booking_id": bid,
                "user_name": "Devotee Suresh",
                "pax_count": 2,
                "total_price": 10000.0,
            },
            headers=headers,
        )
        self.assertEqual(res2.status_code, 200)

        # Verify only 1 record exists
        list_res = self.client.get("/api/auth/saved-bookings", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.json()["count"], 1)
        self.assertEqual(len(list_res.json()["bookings"]), 1)

    def test_12_failed_or_expired_workflow_not_saved_as_confirmed(self):
        """Test 12: Expired or unconfirmed workflows do not appear in user bookings."""
        user, token = self._login_user(f"unconf_{uuid.uuid4().hex[:6]}@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        sid = f"sess_{uuid.uuid4().hex[:8]}"
        session_store.create_session(
            session_id=sid,
            initial_state={"plan_version": 1, "authorization": {"granted": True}},
            user_id=user["user_id"],
        )

        def fake_start(*args, **kwargs):
            wf = session_store.create_user_workflow(
                session_id=kwargs.get("session_id", sid),
                state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
                step="security_checkpoint",
                operation="yatra_mock_booking",
                pending_action="ENTER_OTP_IN_PORTAL",
                checkpoint_data={"checkpoint_mode": "OTP"},
            )
            return {
                "status": "PAUSED",
                "workflow_id": wf["workflow_id"],
                "state": wf["state"],
                "checkpoint_mode": "OTP",
                "session_id": sid,
            }

        with patch("agents.coordinator.start_user_controlled_workflow", side_effect=fake_start):
            # Workflow started and paused at OTP
            start_res = self.client.post(
                "/api/yatra/rpa/workflow/start",
                json={
                    "session_id": sid,
                    "user_name": "Incomplete Pilgrim",
                    "pax_count": 1,
                    "checkpoint_mode": "OTP",
                    "headless": True,
                    "plan_version": 1,
                    "human_authorized": True,
                },
                headers=headers,
            )
            self.assertEqual(start_res.status_code, 200)
            wf_id = start_res.json()["workflow_id"]

        # Cancel workflow
        cancel_res = self.client.post(
            "/api/yatra/rpa/workflow/cancel",
            json={"session_id": sid, "workflow_id": wf_id, "reason": "User abandoned"},
            headers=headers,
        )
        self.assertEqual(cancel_res.status_code, 200)

        # User bookings must remain empty
        b_res = self.client.get("/api/auth/saved-bookings", headers=headers)
        self.assertEqual(b_res.status_code, 200)
        self.assertEqual(b_res.json()["count"], 0)


if __name__ == "__main__":
    unittest.main()
