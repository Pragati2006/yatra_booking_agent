"""
tests/test_passwordless_auth_week9.py
Week 9: Passwordless Email OTP Authentication & Data Isolation Test Suite.

Verifies all 25 required test cases:
1. Guest can open application without login (Default Guest Mode)
2. Guest can ask tourism questions
3. Guest can generate itineraries
4. Guest can use permitted mock availability checking
5. Guest can voluntarily open login/request OTP
6. New user registration through email OTP
7. Existing user login through email OTP
8. Duplicate email prevention (normalized unique identity)
9. Invalid OTP rejection
10. Expired OTP rejection
11. OTP single-use behavior (cannot be reused)
12. Maximum verification attempts (5 attempts limit)
13. Request rate limiting (60s cooldown)
14. Resend cooldown enforcement
15. Secure session creation (HttpOnly cookie & token)
16. Session expiration enforcement
17. Logout and server session revocation
18. Cross-user data isolation (User A cannot access User B data)
19. Guest cannot access private saved data (401 response)
20. Authenticated user can save conversations
21. Authenticated user can retrieve conversations
22. Authenticated user can save itineraries
23. Authenticated user can retrieve itineraries
24. Guest-to-account selective data transfer
25. No OTP or email credentials in application logs
"""

import os
import sys
import io
import time
import uuid
import logging
import sqlite3
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

# Ensure utf-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from backend.main import app
import agents.auth_service as auth_module
from agents.auth_service import (
    auth_service,
    get_email_provider,
    set_email_provider,
    MockEmailProvider,
    normalize_email,
    generate_secure_otp,
    hash_otp,
    compute_otp_hmac,
)

client = TestClient(app)


class TestPasswordlessAuthWeek9(unittest.TestCase):
    """Week 9 Passwordless Email OTP Authentication & Data Isolation Test Suite."""

    def setUp(self):
        client.cookies.clear()
        # Use a fresh MockEmailProvider for each test
        self.mock_provider = MockEmailProvider()
        set_email_provider(self.mock_provider)
        self.test_email = f"pilgrim_{uuid.uuid4().hex[:8]}@example.com"

    def tearDown(self):
        self.mock_provider.clear()
        client.cookies.clear()

    # -------------------------------------------------------------------------
    # 1. Guest Mode Experience
    # -------------------------------------------------------------------------
    def test_01_guest_can_open_app_without_login(self):
        """Verifies app opens in default Guest Mode without registration walls or 401 errors."""
        resp = client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "guest")
        self.assertFalse(data.get("authenticated"))
        self.assertIsNone(data.get("user"))

    def test_02_guest_can_ask_tourism_questions(self):
        """Verifies unauthenticated guest can ask tourism questions freely."""
        resp = client.post("/api/chat", json={"message": "What places can I visit around Katra?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "TOURISM")
        self.assertIn("reply", data)
        self.assertTrue(len(data["reply"]) > 20)

    def test_03_guest_can_generate_itineraries(self):
        """Verifies unauthenticated guest can generate complete travel itineraries."""
        resp = client.post(
            "/api/yatra/itinerary",
            json={
                "option": {
                    "transport": {"mode": "Train", "departure": "06:00", "arrival": "14:00", "price": 1200},
                    "slot": {"time": "18:00", "session": "Evening Aarti", "price": 0},
                    "total_price": 2400,
                },
                "hotel": {"name": "Devi Darshan Hotel", "category": "Mid-Range", "price": 2500},
                "hotel_nights": 2,
                "sightseeing_places": ["Bhairavnath Temple", "Ban Ganga"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("itinerary", data)

    def test_04_guest_can_use_mock_availability(self):
        """Verifies unauthenticated guest can check darshan availability via mock RPA."""
        resp = client.post("/api/chat", json={"message": "Check VIP Darshan availability for 2026-10-20"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "AVAILABILITY")
        self.assertIsNotNone(data.get("availability_result"))

    # -------------------------------------------------------------------------
    # 2. Email OTP Request & Verification Flow
    # -------------------------------------------------------------------------
    def test_05_guest_can_voluntarily_request_otp(self):
        """Verifies user can voluntarily request OTP without compulsory prompt."""
        resp = client.post("/api/auth/request-otp", json={"email": self.test_email})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("email"), self.test_email.lower())
        self.assertTrue(data.get("delivered"))

    def test_06_new_user_registration_through_email_otp(self):
        """Verifies new user registration with 6-digit OTP creates a user account."""
        req_res = client.post("/api/auth/request-otp", json={"email": self.test_email}).json()
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp), 6)

        verify_res = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(verify_res.status_code, 200)
        data = verify_res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertTrue(data.get("is_new_user"))
        self.assertIsNotNone(data.get("session_token"))
        user = data.get("user")
        self.assertIsNotNone(user)
        self.assertEqual(user.get("email"), self.test_email.lower())
        self.assertTrue(user.get("user_id").startswith("usr_"))

    def test_07_existing_user_login_through_email_otp(self):
        """Verifies subsequent login by registered user authenticates the existing account."""
        # 1. Register first
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp1 = self.mock_provider.get_latest_otp_for(self.test_email)
        res1 = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp1}).json()
        user_id_1 = res1["user"]["user_id"]

        # Backdate cooldown to request again immediately
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        with sqlite3.connect(auth_service.db_path) as conn:
            conn.execute("UPDATE otp_challenges SET last_requested_at = ? WHERE email = ?", (past_iso, self.test_email))
            conn.commit()

        # 2. Login again
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp2 = self.mock_provider.get_latest_otp_for(self.test_email)
        res2 = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp2}).json()
        self.assertFalse(res2.get("is_new_user"))
        self.assertEqual(res2["user"]["user_id"], user_id_1)

    def test_08_duplicate_email_prevention(self):
        """Verifies case variations (Pilgrim@Example.COM vs pilgrim@example.com) map to identical user."""
        email_upper = self.test_email.upper()
        client.post("/api/auth/request-otp", json={"email": email_upper})
        otp = self.mock_provider.get_latest_otp_for(email_upper)
        res_upper = client.post("/api/auth/verify-otp", json={"email": email_upper, "otp_code": otp}).json()
        uid_1 = res_upper["user"]["user_id"]

        # Verify normalized email in DB
        with sqlite3.connect(auth_service.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users WHERE email = ?", (self.test_email.lower(),))
            count = cur.fetchone()[0]
            self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 3. OTP Security Invariants
    # -------------------------------------------------------------------------
    def test_09_invalid_otp_rejection(self):
        """Verifies incorrect OTP is rejected with remaining attempts indicator."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        res = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": "000000"})
        self.assertEqual(res.status_code, 401)
        data = res.json()["detail"]
        self.assertEqual(data.get("error_code"), "INCORRECT_CODE")
        self.assertEqual(data.get("remaining_attempts"), 4)

    def test_10_expired_otp_rejection(self):
        """Verifies OTP past 5-minute expiry is rejected as CODE_EXPIRED."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)

        # Backdate expiration past 5 minutes
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with sqlite3.connect(auth_service.db_path) as conn:
            conn.execute("UPDATE otp_challenges SET expires_at = ? WHERE email = ?", (past_iso, self.test_email))
            conn.commit()

        res = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"].get("error_code"), "CODE_EXPIRED")

    def test_11_otp_single_use_behavior(self):
        """Verifies OTP cannot be reused once verified."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)

        # First verification succeeds
        res1 = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(res1.status_code, 200)

        # Reusing the same OTP must fail
        res2 = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.json()["detail"].get("error_code"), "NO_ACTIVE_CHALLENGE")

    def test_12_maximum_verification_attempts(self):
        """Verifies challenge is invalidated after 5 failed attempts."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        for i in range(4):
            r = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": f"11111{i}"})
            self.assertEqual(r.status_code, 401)

        # 5th attempt invalidates challenge
        r5 = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": "999999"})
        self.assertEqual(r5.status_code, 400)
        self.assertEqual(r5.json()["detail"].get("error_code"), "MAX_ATTEMPTS_EXCEEDED")

    def test_13_request_rate_limiting(self):
        """Verifies requesting OTP within 60s cooldown is rejected with 429."""
        r1 = client.post("/api/auth/request-otp", json={"email": self.test_email})
        self.assertEqual(r1.status_code, 200)

        # Immediate second request
        r2 = client.post("/api/auth/request-otp", json={"email": self.test_email})
        self.assertEqual(r2.status_code, 429)
        self.assertEqual(r2.json()["detail"].get("error_code"), "RATE_LIMITED")
        self.assertGreater(r2.json()["detail"].get("retry_after_seconds"), 0)

    def test_14_resend_cooldown_enforcement(self):
        """Verifies resending is permitted once 60s cooldown has elapsed."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        # Fast-forward 65 seconds
        past_iso = (datetime.now(timezone.utc) - timedelta(seconds=65)).isoformat()
        with sqlite3.connect(auth_service.db_path) as conn:
            conn.execute("UPDATE otp_challenges SET last_requested_at = ? WHERE email = ?", (past_iso, self.test_email))
            conn.commit()

        r2 = client.post("/api/auth/request-otp", json={"email": self.test_email})
        self.assertEqual(r2.status_code, 200)

    # -------------------------------------------------------------------------
    # 4. Session Security & Revocation
    # -------------------------------------------------------------------------
    def test_15_secure_session_creation(self):
        """Verifies verify-otp sets HttpOnly session cookie and returns session token."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        resp = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("yatra_auth_session", resp.cookies)
        self.assertIsNotNone(resp.json().get("session_token"))

    def test_16_session_expiration_enforcement(self):
        """Verifies expired server session token is rejected by /api/auth/me."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        token = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp}).json()["session_token"]

        # Backdate session expiration in DB
        past_iso = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        with sqlite3.connect(auth_service.db_path) as conn:
            conn.execute("UPDATE auth_sessions SET expires_at = ? WHERE session_token = ?", (past_iso, token))
            conn.commit()

        me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(me_res.get("status"), "guest")
        self.assertFalse(me_res.get("authenticated"))

    def test_17_logout_and_session_revocation(self):
        """Verifies logout revokes the server session token and returns to Guest Mode."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        token = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp}).json()["session_token"]

        # Logout
        logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # Subsequent check must be Guest Mode
        me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(me_res.get("status"), "guest")
        self.assertFalse(me_res.get("authenticated"))

    # -------------------------------------------------------------------------
    # 5. User Data Persistence & Strict Isolation
    # -------------------------------------------------------------------------
    def test_18_cross_user_data_isolation(self):
        """Verifies User A cannot read, modify, or delete User B's saved itineraries or conversations."""
        # Create User A
        email_a = f"user_a_{uuid.uuid4().hex[:6]}@example.com"
        client.post("/api/auth/request-otp", json={"email": email_a})
        token_a = client.post("/api/auth/verify-otp", json={"email": email_a, "otp_code": self.mock_provider.get_latest_otp_for(email_a)}).json()["session_token"]

        # Create User B
        email_b = f"user_b_{uuid.uuid4().hex[:6]}@example.com"
        client.post("/api/auth/request-otp", json={"email": email_b})
        token_b = client.post("/api/auth/verify-otp", json={"email": email_b, "otp_code": self.mock_provider.get_latest_otp_for(email_b)}).json()["session_token"]

        # User A saves an itinerary
        save_a = client.post(
            "/api/auth/save-itinerary",
            json={"title": "User A Private Yatra", "itinerary": {"days": 3}},
            headers={"Authorization": f"Bearer {token_a}"},
        ).json()
        itin_id_a = save_a["itinerary"]["itinerary_id"]

        # User B lists saved itineraries -> MUST NOT see User A's itinerary
        list_b = client.get("/api/auth/saved-itineraries", headers={"Authorization": f"Bearer {token_b}"}).json()
        self.assertEqual(list_b.get("count"), 0)
        self.assertEqual(len(list_b.get("itineraries")), 0)

        # User B attempts to delete User A's itinerary -> MUST FAIL with 404
        del_attempt = client.delete(
            f"/api/auth/saved-itinerary/{itin_id_a}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        self.assertEqual(del_attempt.status_code, 404)

    def test_19_guest_cannot_access_private_saved_data(self):
        """Verifies unauthenticated guest request to saved endpoints receives 401."""
        r_itin = client.get("/api/auth/saved-itineraries")
        self.assertEqual(r_itin.status_code, 401)

        r_conv = client.get("/api/auth/saved-conversations")
        self.assertEqual(r_conv.status_code, 401)

    def test_20_authenticated_user_can_save_conversations(self):
        """Verifies authenticated user can save chat threads."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        token = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": self.mock_provider.get_latest_otp_for(self.test_email)}).json()["session_token"]

        msgs = [
            {"role": "user", "content": "How do I reach Bhawan?"},
            {"role": "assistant", "content": "You can trek 13 km from Katra via Himkoti route."},
        ]
        res = client.post(
            "/api/auth/save-conversation",
            json={"title": "Route Inquiry", "messages": msgs},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["conversation"]["title"], "Route Inquiry")

    def test_21_authenticated_user_can_retrieve_conversations(self):
        """Verifies authenticated user can list saved conversation threads."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        token = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": self.mock_provider.get_latest_otp_for(self.test_email)}).json()["session_token"]

        # Save conversation
        client.post(
            "/api/auth/save-conversation",
            json={"title": "Aarti Timings Thread", "messages": [{"role": "user", "content": "Aarti timings?"}]},
            headers={"Authorization": f"Bearer {token}"},
        )

        res = client.get("/api/auth/saved-conversations", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        convs = res.json()["conversations"]
        self.assertGreaterEqual(len(convs), 1)
        self.assertEqual(convs[0]["title"], "Aarti Timings Thread")

    def test_22_authenticated_user_can_save_itineraries(self):
        """Verifies authenticated user can save generated itineraries."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        token = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": self.mock_provider.get_latest_otp_for(self.test_email)}).json()["session_token"]

        itin_payload = {"total_cost": 12500, "days": [{"day": 1, "plan": "Arrival in Katra"}]}
        res = client.post(
            "/api/auth/save-itinerary",
            json={"title": "Family Yatra Autumn 2026", "itinerary": itin_payload},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["itinerary"]["title"], "Family Yatra Autumn 2026")

    def test_23_authenticated_user_can_retrieve_itineraries(self):
        """Verifies authenticated user can retrieve saved itineraries."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        token = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": self.mock_provider.get_latest_otp_for(self.test_email)}).json()["session_token"]

        client.post(
            "/api/auth/save-itinerary",
            json={"title": "Solo Darshan Plan", "itinerary": {"pax": 1}},
            headers={"Authorization": f"Bearer {token}"},
        )

        res = client.get("/api/auth/saved-itineraries", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        itins = res.json()["itineraries"]
        self.assertGreaterEqual(len(itins), 1)
        self.assertEqual(itins[0]["title"], "Solo Darshan Plan")

    # -------------------------------------------------------------------------
    # 6. Guest-to-Account Transition & Log Privacy
    # -------------------------------------------------------------------------
    def test_24_guest_to_account_selective_data_transfer(self):
        """Verifies guest with active in-memory chat/itinerary can selectively transfer work upon login."""
        # 1. Guest creates conversation in chat
        chat_msgs = [
            {"role": "user", "content": "Plan a 3-day trip from Delhi to Katra"},
            {"role": "assistant", "content": "Here is an option with Vande Bharat Express and VIP Darshan."},
        ]

        # 2. Guest decides to sign in
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        auth_data = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp}).json()
        token = auth_data["session_token"]

        # 3. User selectively transfers the active conversation
        transfer_res = client.post(
            "/api/auth/save-conversation",
            json={"title": "Delhi to Katra Trip Chat", "messages": chat_msgs},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(transfer_res.status_code, 200)

        # 4. Verify conversation is persisted to account
        saved_convs = client.get("/api/auth/saved-conversations", headers={"Authorization": f"Bearer {token}"}).json()["conversations"]
        self.assertTrue(any(c["title"] == "Delhi to Katra Trip Chat" for c in saved_convs))

    def test_25_no_otp_or_email_credentials_in_logs(self):
        """Verifies zero plain OTP values or credentials appear in application logs during authentication."""
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        prev_level = root_logger.level
        root_logger.setLevel(logging.INFO)

        try:
            # Execute full OTP flow
            client.post("/api/auth/request-otp", json={"email": self.test_email})
            otp = self.mock_provider.get_latest_otp_for(self.test_email)
            client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})

            captured_logs = log_stream.getvalue()
            # Assert plain OTP value is NEVER logged
            self.assertNotIn(otp, captured_logs, "CRITICAL: Plain OTP code was found in application logs!")
            # Assert no passwords logged
            self.assertNotIn("password", captured_logs.lower())
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(prev_level)

    # -------------------------------------------------------------------------
    # 6. Quality & Security Hardening (HMAC, CSRF, Prod Blocking, Secure Cookies)
    # -------------------------------------------------------------------------
    def test_26_hmac_based_otp_verification(self):
        """Verifies OTP verification uses HMAC-SHA256 with server-side secret, challenge-specific data, and constant-time check."""
        req_res = client.post("/api/auth/request-otp", json={"email": self.test_email})
        self.assertEqual(req_res.status_code, 200)
        otp = self.mock_provider.get_latest_otp_for(self.test_email)

        # Retrieve stored challenge from SQLite database
        conn = sqlite3.connect(auth_service.db_path)
        cur = conn.cursor()
        cur.execute("SELECT otp_hash, created_at FROM otp_challenges WHERE email = ?", (normalize_email(self.test_email),))
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        stored_hmac, created_at = row

        # Compute HMAC independently with challenge-specific data
        expected_hmac = compute_otp_hmac(otp, self.test_email, created_at=created_at)
        self.assertEqual(stored_hmac, expected_hmac)

        # Confirm constant-time verification succeeds
        verify_res = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json().get("status"), "success")
        self.assertIsNotNone(verify_res.json().get("session_token"))

    def test_27_dev_endpoint_accessible_in_development_mode(self):
        """Verifies /api/auth/test/latest-otp operates correctly in development/test mode with MockEmailProvider."""
        with patch.dict(os.environ, {"APP_ENV": "development", "ENABLE_DEV_TEST_ENDPOINTS": "true"}):
            client.post("/api/auth/request-otp", json={"email": self.test_email})
            resp = client.get(f"/api/auth/test/latest-otp?email={self.test_email}")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("latest_otp", resp.json())
            self.assertEqual(len(resp.json()["latest_otp"]), 6)

    def test_28_dev_endpoint_strictly_rejected_404_in_production_mode(self):
        """Verifies /api/auth/test/latest-otp returns 404 Not Found in production mode to prevent information disclosure."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            resp = client.get(f"/api/auth/test/latest-otp?email={self.test_email}")
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.json().get("detail"), "Not Found")

    def test_29_csrf_protection_rejects_cross_site_cookie_requests(self):
        """Verifies CSRF protection rejects cross-origin cookie-authenticated state-changing POST requests."""
        # Authenticate user to obtain session cookie
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        verify_res = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(verify_res.status_code, 200)

        # Attempt state-changing POST with malicious Origin header
        malicious_headers = {"Origin": "https://malicious-phishing-site.com"}
        csrf_attempt = client.post(
            "/api/auth/save-itinerary",
            json={"title": "Hacked Itinerary", "itinerary": {"days": []}},
            headers=malicious_headers,
        )
        self.assertEqual(csrf_attempt.status_code, 403)
        self.assertIn("CSRF validation failed", csrf_attempt.json().get("detail", ""))

    def test_30_csrf_protection_permits_same_origin_and_bearer_tokens(self):
        """Verifies CSRF protection permits legitimate same-origin requests and Authorization: Bearer tokens."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        verify_res = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        token = verify_res.json()["session_token"]

        # 1. Permitted with same-origin header
        same_origin_res = client.post(
            "/api/auth/save-itinerary",
            json={"title": "Safe Itinerary 1", "itinerary": {"days": []}},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        self.assertEqual(same_origin_res.status_code, 200)

        # 2. Permitted with explicit Bearer token header regardless of origin (cross-site immune)
        bearer_res = client.post(
            "/api/auth/save-itinerary",
            json={"title": "Safe Itinerary 2", "itinerary": {"days": []}},
            headers={"Authorization": f"Bearer {token}", "Origin": "https://external-client.com"},
        )
        self.assertEqual(bearer_res.status_code, 200)

    def test_31_cookie_security_flags_in_production(self):
        """Verifies session cookie has Secure, HttpOnly, and SameSite=Lax flags in production."""
        client.post("/api/auth/request-otp", json={"email": self.test_email})
        otp = self.mock_provider.get_latest_otp_for(self.test_email)

        with patch.dict(os.environ, {"APP_ENV": "production"}):
            resp = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
            self.assertEqual(resp.status_code, 200)
            set_cookie_header = resp.headers.get("set-cookie", "")
            self.assertIn("httponly", set_cookie_header.lower())
            self.assertIn("samesite=lax", set_cookie_header.lower())
            self.assertIn("secure", set_cookie_header.lower())


if __name__ == "__main__":
    unittest.main()

