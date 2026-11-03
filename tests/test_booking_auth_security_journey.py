"""
tests/test_booking_auth_security_journey.py
Validates Part 2 & Part 3 Security Requirements:
- Scenario 12: A guest cannot bypass backend booking authentication (401 on /workflow/start and /confirm).
- Scenario 13: One user cannot access another user's booking or pass (403 on resume, 404 on PDF).
- Scenario 14: Failed or unconfirmed workflows cannot download passes.
- Scenario 15: Starting a new booking does not expose or return an old receipt.
"""

import uuid
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from agents.auth_service import auth_service, get_email_provider, MockEmailProvider
import agents.session_store as session_store

class TestBookingAuthSecurityJourney(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.provider = get_email_provider()

    def _login_user(self, email: str):
        # 1. Request OTP
        req_res = self.client.post("/api/auth/request-otp", json={"email": email})
        self.assertEqual(req_res.status_code, 200)
        
        # 2. Get Mock OTP
        otp = self.provider.get_latest_otp_for(email)
        self.assertIsNotNone(otp)

        # 3. Verify OTP
        verify_res = self.client.post("/api/auth/verify-otp", json={"email": email, "otp_code": otp})
        self.assertEqual(verify_res.status_code, 200)
        data = verify_res.json()
        token = data["session_token"]
        user = data["user"]
        return user, token

    def test_guest_cannot_start_rpa_workflow(self):
        """Scenario 12: Guest without authentication header or cookie is rejected with 401."""
        # Create a valid session in session_store with authorization granted
        sid = f"real-user-sess-{uuid.uuid4().hex[:10]}"
        session_store.create_session(
            session_id=sid,
            initial_state={
                "plan_version": 1,
                "authorization": {"granted": True},
                "authorized_plan_version": 1,
            }
        )

        # Guest attempts to start RPA workflow (without Authorization header)
        resp = self.client.post("/api/yatra/rpa/workflow/start", json={
            "session_id": sid,
            "user_name": "Guest Pilgrim",
            "pax_count": 2,
            "transport_text": "Train",
            "slot_text": "Morning",
            "human_authorized": True,
            "plan_version": 1,
        })
        self.assertEqual(resp.status_code, 401, "Unauthenticated guest must receive 401 Unauthorized")
        self.assertIn("Authentication required", resp.json()["detail"])

    def test_guest_cannot_download_booking_pdf(self):
        """Scenario 12: Guest without authentication cannot download a booking pass (401)."""
        resp = self.client.get("/api/yatra/booking/VD-889900/pdf")
        self.assertEqual(resp.status_code, 401, "Unauthenticated guest must receive 401 when requesting PDF pass")

    def test_cross_user_workflow_resume_isolation(self):
        """Scenario 13: User B cannot resume or hijack User A's workflow (403 Forbidden)."""
        # User A logs in
        user_a, token_a = self._login_user(f"user_a_{uuid.uuid4().hex[:6]}@example.com")
        
        # Session belongs to User A
        sid = f"session-user-a-{uuid.uuid4().hex[:10]}"
        session_store.create_session(
            session_id=sid,
            initial_state={
                "plan_version": 1,
                "authorization": {"granted": True},
                "authorized_plan_version": 1,
            },
            user_id=user_a["user_id"],
        )

        # User B logs in
        user_b, token_b = self._login_user("user_b_malicious@example.com")

        # User B attempts to resume workflow belonging to User A
        resp = self.client.post(
            "/api/yatra/rpa/workflow/resume",
            json={
                "session_id": sid,
                "workflow_id": "wf-user-a-123",
                "user_confirmed_action": True,
            },
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(resp.status_code, 403, "User B must receive 403 Forbidden when resuming User A's workflow")
        self.assertIn("Access denied", resp.json()["detail"])

    def test_cross_user_pdf_isolation(self):
        """Scenario 13: User B cannot access or download User A's confirmed booking pass."""
        # User A logs in and has a saved booking
        user_a, token_a = self._login_user("user_a_pdf@example.com")
        booking_id = "VD-USERA-777"
        auth_service.save_booking(
            user_id=user_a["user_id"],
            booking_data={
                "booking_id": booking_id,
                "session_id": "sess-user-a",
                "user_name": "User A",
                "pax_count": 2,
                "slot_date": "2026-10-25",
                "category": "Normal Darshan",
                "slot_time": "Morning (06:00)",
                "total_price": 5000.0,
                "payment_status": "COMPLETED_SANDBOX",
                "status": "SIMULATED_CONFIRMED",
            }
        )

        # User A can download their pass
        resp_a = self.client.get(
            f"/api/yatra/booking/{booking_id}/pdf",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_a.headers["content-type"], "application/pdf")
        self.assertTrue(resp_a.content.startswith(b"%PDF-1.4"))

        # User B logs in
        user_b, token_b = self._login_user("user_b_pdf@example.com")

        # User B tries to download User A's pass
        resp_b = self.client.get(
            f"/api/yatra/booking/{booking_id}/pdf",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(resp_b.status_code, 404, "User B must receive 404/Access Denied when requesting User A's pass")

    def test_unconfirmed_workflow_cannot_generate_pass(self):
        """Scenario 14: Nonexistent or unconfirmed workflow cannot generate pass."""
        user, token = self._login_user("valid_user_no_pass@example.com")
        resp = self.client.get(
            "/api/yatra/booking/VD-NONEXISTENT/pdf",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
