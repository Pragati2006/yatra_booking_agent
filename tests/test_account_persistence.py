"""
tests/test_account_persistence.py
Phase 7 Verification: Account-Linked Chats, Trips, and Booking History.

Verifies all 14 required Phase 7 specifications:
1. Authenticated user saves a conversation.
2. User retrieves it after logging in again (cross-session retrieval).
3. Guest selectively transfers a conversation to authenticated account.
4. User saves and retrieves an itinerary.
5. Guest selectively transfers a trip plan to authenticated account.
6. Authenticated user completes a simulated booking (associated with verified user_id).
7. Booking appears in My Bookings (/api/auth/saved-bookings).
8. User logs out and logs in again; booking remains available.
9. Demo pass details contain mock indicators (SIMULATED_CONFIRMED, COMPLETED_SANDBOX, disclaimer).
10. Another user cannot access the booking (Strict cross-user authorization rejection).
11. Guest booking remains available in its original guest session without account pollution.
12. Duplicate resume/retry does not create duplicate booking records (idempotence).
13. Failed/abandoned booking does not create a confirmed booking record.
14. Regression coverage across existing auth and session data models.
"""

import os
import sys
import uuid
import sqlite3
import unittest
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from backend.main import app
import agents.auth_service as auth_module
from agents.auth_service import (
    auth_service,
    set_email_provider,
    MockEmailProvider,
)
import agents.session_store as session_store

client = TestClient(app)


class TestAccountPersistence(unittest.TestCase):
    """Phase 7 comprehensive test suite for account-linked chats, trips, and booking history."""

    def setUp(self):
        client.cookies.clear()
        self.mock_provider = MockEmailProvider()
        set_email_provider(self.mock_provider)
        self.test_email = f"devotee_{uuid.uuid4().hex[:8]}@example.com"
        self.user_b_email = f"devotee_b_{uuid.uuid4().hex[:8]}@example.com"

    def tearDown(self):
        self.mock_provider.clear()
        client.cookies.clear()

    def _login(self, email: str) -> dict:
        """Helper to request OTP, verify, and return auth info dictionary."""
        client.cookies.clear()
        req_res = client.post("/api/auth/request-otp", json={"email": email})
        self.assertEqual(req_res.status_code, 200)
        otp = self.mock_provider.get_latest_otp_for(email)
        self.assertIsNotNone(otp, f"No OTP generated for {email}")

        ver_res = client.post("/api/auth/verify-otp", json={"email": email, "otp_code": otp})
        self.assertEqual(ver_res.status_code, 200)
        data = ver_res.json()
        return {
            "token": data["session_token"],
            "user_id": data["user"]["user_id"],
            "email": email,
            "headers": {"Authorization": f"Bearer {data['session_token']}"},
        }

    # -------------------------------------------------------------------------
    # Scenario 1: Authenticated user saves a conversation
    # -------------------------------------------------------------------------
    def test_01_authenticated_user_saves_conversation(self):
        """Verifies an authenticated user can save a conversation thread."""
        user = self._login(self.test_email)
        msgs = [
            {"role": "user", "content": "What are the registration requirements for Vaishno Devi Yatra?"},
            {"role": "assistant", "content": "You need a valid Yatra Parchi (RFID card) issued at Katra."},
        ]
        resp = client.post(
            "/api/auth/save-conversation",
            json={"title": "Parchi Inquiries", "messages": msgs},
            headers=user["headers"],
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        conv = data.get("conversation")
        self.assertEqual(conv["title"], "Parchi Inquiries")
        self.assertEqual(conv["user_id"], user["user_id"])
        self.assertEqual(len(conv["messages"]), 2)

    # -------------------------------------------------------------------------
    # Scenario 2: User retrieves conversation after logging in again
    # -------------------------------------------------------------------------
    def test_02_user_retrieves_conversation_after_relogin(self):
        """Verifies a user can log out, log in again from another session, and retrieve conversations."""
        # Session 1: save conversation
        user_sess1 = self._login(self.test_email)
        client.post(
            "/api/auth/save-conversation",
            json={"title": "Helicopter Timing Chat", "messages": [{"role": "user", "content": "Heli timings?"}]},
            headers=user_sess1["headers"],
        )

        # Logout
        client.post("/api/auth/logout", headers=user_sess1["headers"])
        client.cookies.clear()

        # Session 2: Login again with new OTP challenge
        user_sess2 = self._login(self.test_email)
        self.assertEqual(user_sess1["user_id"], user_sess2["user_id"])

        # Retrieve saved conversations
        resp = client.get("/api/auth/saved-conversations", headers=user_sess2["headers"])
        self.assertEqual(resp.status_code, 200)
        convs = resp.json()["conversations"]
        self.assertGreaterEqual(len(convs), 1)
        found = any(c["title"] == "Helicopter Timing Chat" for c in convs)
        self.assertTrue(found, "Saved conversation not retrieved after re-login")

    # -------------------------------------------------------------------------
    # Scenario 3: Guest selectively transfers a conversation
    # -------------------------------------------------------------------------
    def test_03_guest_selectively_transfers_conversation(self):
        """Verifies a guest active conversation session can be selectively transferred to account."""
        guest_session_id = f"guest_sess_{uuid.uuid4().hex[:8]}"
        session_store.create_session(guest_session_id)
        session_store.add_message(guest_session_id, "user", "How far is Bhawan from Katra?")
        session_store.add_message(guest_session_id, "assistant", "The trek is approximately 13 km.")

        # Guest authenticates
        user = self._login(self.test_email)

        # Selectively transfer session conversation
        resp = client.post(
            "/api/auth/transfer-conversation",
            json={"session_id": guest_session_id, "title": "Guest Trek Q&A"},
            headers=user["headers"],
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data["conversation"]["title"], "Guest Trek Q&A")
        self.assertEqual(len(data["conversation"]["messages"]), 2)

        # Verify it now appears in user's saved conversations
        convs = client.get("/api/auth/saved-conversations", headers=user["headers"]).json()["conversations"]
        self.assertTrue(any(c["title"] == "Guest Trek Q&A" for c in convs))

        # Verify sessions table in sessions.db was safely associated with user_id
        sess = session_store.get_session(guest_session_id)
        self.assertEqual(sess.get("user_id"), user["user_id"])

    # -------------------------------------------------------------------------
    # Scenario 4: User saves and retrieves an itinerary
    # -------------------------------------------------------------------------
    def test_04_user_saves_and_retrieves_itinerary(self):
        """Verifies authenticated user can save and retrieve a comprehensive trip plan."""
        user = self._login(self.test_email)
        trip_plan = {
            "origin": "Jammu",
            "pax": 3,
            "dates": {"start": "2026-11-15", "end": "2026-11-17"},
            "darshan_category": "SPECIAL_DARSHAN",
            "transport_preference": "TRAIN",
            "hotel_preference": "PREMIUM",
            "budget": 25000,
            "days": [
                {"day": 1, "desc": "Arrive at Katra, check in to hotel."},
                {"day": 2, "desc": "Trek to Bhawan via Himkoti, Special Aarti."},
                {"day": 3, "desc": "Return to Katra, departure."},
            ],
            "plan_version": 2,
        }
        resp = client.post(
            "/api/auth/save-itinerary",
            json={"title": "Jammu Family Pilgrimage 3D", "itinerary": trip_plan},
            headers=user["headers"],
        )
        self.assertEqual(resp.status_code, 200)
        itin_id = resp.json()["itinerary"]["itinerary_id"]

        # Retrieve saved itineraries
        get_res = client.get("/api/auth/saved-itineraries", headers=user["headers"])
        self.assertEqual(get_res.status_code, 200)
        itins = get_res.json()["itineraries"]
        saved = next((i for i in itins if i["itinerary_id"] == itin_id), None)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["data"]["darshan_category"], "SPECIAL_DARSHAN")
        self.assertEqual(saved["data"]["pax"], 3)
        self.assertEqual(saved["data"]["origin"], "Jammu")

    # -------------------------------------------------------------------------
    # Scenario 5: Guest selectively transfers a trip
    # -------------------------------------------------------------------------
    def test_05_guest_selectively_transfers_trip(self):
        """Verifies guest can plan a trip and selectively transfer it to their account upon login."""
        guest_session_id = f"guest_trip_{uuid.uuid4().hex[:8]}"
        session_store.create_session(guest_session_id)
        mock_reqs = {
            "origin": "Chandigarh",
            "pax": 2,
            "dates": {"start": "2026-12-01", "end": "2026-12-03"},
            "darshan_category": "VIP",
            "budget": 18000,
        }
        mock_itinerary = {
            "days": [{"day": 1, "title": "Chandigarh to Katra via NH44"}],
            "total_estimated_cost": 17500,
        }
        session_store.update_session(guest_session_id, updates={"requirements": mock_reqs, "itinerary": mock_itinerary})

        # Login
        user = self._login(self.test_email)

        # Selectively transfer trip
        resp = client.post(
            "/api/auth/transfer-trip",
            json={"session_id": guest_session_id, "title": "Chandigarh Weekend Darshan"},
            headers=user["headers"],
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data["itinerary"]["title"], "Chandigarh Weekend Darshan")
        self.assertEqual(data["itinerary"]["data"]["origin"], "Chandigarh")

        # Confirm retrieval from user's account
        itins = client.get("/api/auth/saved-itineraries", headers=user["headers"]).json()["itineraries"]
        self.assertTrue(any(i["title"] == "Chandigarh Weekend Darshan" for i in itins))

    # -------------------------------------------------------------------------
    # Scenario 6 & 7: Authenticated user completes a simulated booking & appears in My Bookings
    # -------------------------------------------------------------------------
    def test_06_and_07_authenticated_user_completes_booking_and_appears_in_my_bookings(self):
        """Verifies simulated booking through confirm_booking links to verified user and appears in saved-bookings."""
        user = self._login(self.test_email)
        sess_id = f"auth_booking_sess_{uuid.uuid4().hex[:8]}"
        session_store.create_session(sess_id, user_id=user["user_id"])

        plan_opt = {"mode": "Train", "total_price": 4200.0, "name": "Vande Bharat Express"}
        slot_opt = {"slot_date": "2026-11-20", "category": "VIP_DARSHAN", "slot_time": "08:00 AM"}
        option_combo = {"transport": plan_opt, "slot": slot_opt, "total_price": 4200.0}

        # 1. Authorize plan version 1
        auth_req = client.post("/api/yatra/authorize", json={"session_id": sess_id, "plan_version": 1})
        self.assertEqual(auth_req.status_code, 200)

        # 2. Confirm booking
        confirm_payload = {
            "option": option_combo,
            "pax": 2,
            "user_name": "Sharma Family",
            "human_authorized": True,
            "session_id": sess_id,
            "plan_version": 1,
            "hotel": {"name": "Katra Residency", "price_per_night": 1500},
        }

        resp = client.post("/api/yatra/confirm", json=confirm_payload, headers=user["headers"])
        self.assertEqual(resp.status_code, 200)
        confirm_data = resp.json()
        self.assertEqual(confirm_data.get("status"), "success")
        booking_id = confirm_data.get("booking_id")
        self.assertTrue(booking_id.startswith("YATRA-") or booking_id.startswith("VD"))

        # Verify it appears immediately in /api/auth/saved-bookings
        bookings_resp = client.get("/api/auth/saved-bookings", headers=user["headers"])
        self.assertEqual(bookings_resp.status_code, 200)
        bookings = bookings_resp.json()["bookings"]
        self.assertGreaterEqual(len(bookings), 1)

        found_booking = next((b for b in bookings if b["booking_id"] == booking_id), None)
        self.assertIsNotNone(found_booking, "Simulated booking not found in user saved-bookings")
        self.assertEqual(found_booking["user_id"], user["user_id"])
        self.assertEqual(found_booking["category"], "VIP_DARSHAN")
        self.assertEqual(found_booking["pax_count"], 2)
        self.assertEqual(found_booking["status"], "SIMULATED_CONFIRMED")
        self.assertEqual(found_booking["payment_status"], "COMPLETED_SANDBOX")

    # -------------------------------------------------------------------------
    # Scenario 8: User logs out and logs in again; booking remains available
    # -------------------------------------------------------------------------
    def test_08_booking_persists_across_logout_and_login(self):
        """Verifies booking remains available when user logs out and logs back in from another session."""
        # 1. Login user and save a simulated booking
        user1 = self._login(self.test_email)
        mock_booking_id = f"YATRA-PERSIST-{uuid.uuid4().hex[:6].upper()}"
        booking_data = {
            "booking_id": mock_booking_id,
            "user_name": "Test Pilgrim",
            "pax_count": 4,
            "slot_date": "2026-11-25",
            "category": "SPECIAL_DARSHAN",
            "slot_time": "10:00 AM",
            "total_price": 5000.0,
            "payment_status": "COMPLETED_SANDBOX",
            "status": "SIMULATED_CONFIRMED",
            "receipt": {"is_simulated": True, "notes": "Demo sandbox pass"},
        }
        save_resp = client.post("/api/auth/save-booking", json=booking_data, headers=user1["headers"])
        self.assertEqual(save_resp.status_code, 200)

        # 2. User logs out
        client.post("/api/auth/logout", headers=user1["headers"])
        client.cookies.clear()

        # 3. User logs in anew
        user2 = self._login(self.test_email)
        self.assertEqual(user1["user_id"], user2["user_id"])

        # 4. Fetch booking by id
        get_res = client.get(f"/api/auth/saved-bookings/{mock_booking_id}", headers=user2["headers"])
        self.assertEqual(get_res.status_code, 200)
        b_data = get_res.json()["booking"]
        self.assertEqual(b_data["booking_id"], mock_booking_id)
        self.assertEqual(b_data["user_id"], user2["user_id"])
        self.assertEqual(b_data["pax_count"], 4)

    # -------------------------------------------------------------------------
    # Scenario 9: Demo pass details contain mock indicators
    # -------------------------------------------------------------------------
    def test_09_demo_pass_details_marked_with_mock_indicators(self):
        """Verifies booking record and demo pass clearly denote mock/simulated status."""
        user = self._login(self.test_email)
        bid = f"YATRA-DEMO-{uuid.uuid4().hex[:6].upper()}"
        save_res = client.post(
            "/api/auth/save-booking",
            json={
                "booking_id": bid,
                "user_name": "Anoop Verma",
                "pax_count": 1,
                "slot_date": "2026-12-10",
                "category": "NORMAL_DARSHAN",
                "total_price": 0.0,
            },
            headers=user["headers"],
        )
        self.assertEqual(save_res.status_code, 200)

        # Retrieve booking
        rec = client.get(f"/api/auth/saved-bookings/{bid}", headers=user["headers"]).json()["booking"]
        self.assertEqual(rec["status"], "SIMULATED_CONFIRMED")
        self.assertEqual(rec["payment_status"], "COMPLETED_SANDBOX")
        self.assertIn("LOCAL MOCK PORTAL", rec["receipt"]["portal_label"])
        self.assertIn("Simulated", rec["receipt"]["title"])

    # -------------------------------------------------------------------------
    # Scenario 10: Another user cannot access the booking (Cross-user isolation)
    # -------------------------------------------------------------------------
    def test_10_cross_user_booking_access_rejected(self):
        """Verifies User B cannot view, list, or overwrite User A's booking."""
        user_a = self._login(self.test_email)
        user_b = self._login(self.user_b_email)

        # User A creates a booking
        bid_a = f"YATRA-ISO-{uuid.uuid4().hex[:6].upper()}"
        client.post(
            "/api/auth/save-booking",
            json={
                "booking_id": bid_a,
                "user_name": "User A Private",
                "pax_count": 2,
                "slot_date": "2026-11-28",
                "category": "VIP_DARSHAN",
                "total_price": 3000.0,
            },
            headers=user_a["headers"],
        )

        # 1. User B lists bookings -> User A's booking must NOT appear
        b_list = client.get("/api/auth/saved-bookings", headers=user_b["headers"]).json()["bookings"]
        self.assertFalse(any(b["booking_id"] == bid_a for b in b_list))

        # 2. User B attempts direct fetch of User A's booking -> 404 Not Found
        direct_fetch = client.get(f"/api/auth/saved-bookings/{bid_a}", headers=user_b["headers"])
        self.assertEqual(direct_fetch.status_code, 404)

        # 3. User B attempts to overwrite User A's booking -> 403 Forbidden
        tamper_attempt = client.post(
            "/api/auth/save-booking",
            json={
                "booking_id": bid_a,
                "user_name": "User B Attacker",
                "pax_count": 10,
                "slot_date": "2026-12-31",
                "category": "TAMPER",
                "total_price": 9999.0,
            },
            headers=user_b["headers"],
        )
        self.assertEqual(tamper_attempt.status_code, 403)

    # -------------------------------------------------------------------------
    # Scenario 11: Guest booking remains available in guest session
    # -------------------------------------------------------------------------
    def test_11_guest_booking_preserved_in_guest_session(self):
        """Verifies guest booking works without login and remains stored in session state without account leakage."""
        client.cookies.clear()
        guest_sess_id = f"guest_unlinked_{uuid.uuid4().hex[:8]}"
        session_store.create_session(guest_sess_id)

        plan_opt = {"mode": "Bus", "total_price": 1200.0, "name": "Volvo AC"}
        slot_opt = {"slot_date": "2026-12-15", "category": "NORMAL_DARSHAN", "slot_time": "09:00 AM"}
        option_combo = {"transport": plan_opt, "slot": slot_opt, "total_price": 1200.0}

        # Authorize plan version 1
        client.post("/api/yatra/authorize", json={"session_id": guest_sess_id, "plan_version": 1})

        confirm_payload = {
            "option": option_combo,
            "pax": 1,
            "user_name": "Guest Pilgrim",
            "human_authorized": True,
            "session_id": guest_sess_id,
            "plan_version": 1,
        }
        # Guest call (no auth headers, no session cookie)
        resp = client.post("/api/yatra/confirm", json=confirm_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        bid = data["booking_id"]

        # Stored in guest session
        sess = session_store.get_session(guest_sess_id)
        self.assertEqual(sess["state"]["rpa_execution"]["booking_id"], bid)
        self.assertIsNone(sess.get("user_id"))

        # Cannot be accessed via protected auth endpoint without login
        unauth_req = client.get("/api/auth/saved-bookings")
        self.assertEqual(unauth_req.status_code, 401)

    # -------------------------------------------------------------------------
    # Scenario 12: Duplicate resume does not create duplicate booking records
    # -------------------------------------------------------------------------
    def test_12_duplicate_booking_resume_is_idempotent(self):
        """Verifies re-saving or confirming the same booking_id is idempotent with no row duplication."""
        user = self._login(self.test_email)
        bid = f"YATRA-IDEM-{uuid.uuid4().hex[:6].upper()}"

        payload = {
            "booking_id": bid,
            "user_name": "Idempotent Pilgrim",
            "pax_count": 2,
            "slot_date": "2026-11-22",
            "category": "VIP_DARSHAN",
            "total_price": 2500.0,
        }

        # Save 1st time
        r1 = client.post("/api/auth/save-booking", json=payload, headers=user["headers"])
        self.assertEqual(r1.status_code, 200)

        # Save 2nd time (duplicate resume or network retry)
        r2 = client.post("/api/auth/save-booking", json=payload, headers=user["headers"])
        self.assertEqual(r2.status_code, 200)

        # Direct database query to verify exactly 1 row exists
        with sqlite3.connect(auth_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_bookings WHERE booking_id = ?", (bid,))
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1, "Duplicate booking rows found in database!")

    # -------------------------------------------------------------------------
    # Scenario 13: Failed or unconfirmed booking does not create a confirmed record
    # -------------------------------------------------------------------------
    def test_13_failed_or_unconfirmed_workflow_does_not_create_booking_record(self):
        """Verifies aborted/failed workflows or missing fields do not persist a confirmed booking."""
        user = self._login(self.test_email)

        # Attempt to save invalid booking with missing required fields
        invalid_payload = {
            "booking_id": "",
            "user_name": "",
        }
        res = client.post("/api/auth/save-booking", json=invalid_payload, headers=user["headers"])
        self.assertIn(res.status_code, (400, 422))

        # Ensure no spurious record was created
        with sqlite3.connect(auth_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_bookings WHERE user_id = ? AND booking_id = ''", (user["user_id"],))
            self.assertEqual(cursor.fetchone()[0], 0)

    # -------------------------------------------------------------------------
    # Scenario 14: User profile summary reflects account activity counts
    # -------------------------------------------------------------------------
    def test_14_user_profile_summary_and_regression_integrity(self):
        """Verifies /api/auth/profile returns correct aggregate counts for trips, chats, and bookings."""
        user = self._login(self.test_email)

        # Add 1 conversation
        client.post(
            "/api/auth/save-conversation",
            json={"title": "Profile Test Chat", "messages": [{"role": "user", "content": "Hi"}]},
            headers=user["headers"],
        )
        # Add 1 trip
        client.post(
            "/api/auth/save-itinerary",
            json={"title": "Profile Test Trip", "itinerary": {"days": 1}},
            headers=user["headers"],
        )
        # Add 1 booking
        client.post(
            "/api/auth/save-booking",
            json={
                "booking_id": f"YATRA-PROF-{uuid.uuid4().hex[:6].upper()}",
                "user_name": "Profile Devotee",
                "pax_count": 1,
                "slot_date": "2026-11-30",
                "category": "NORMAL_DARSHAN",
                "total_price": 0.0,
            },
            headers=user["headers"],
        )

        prof_res = client.get("/api/auth/profile", headers=user["headers"])
        self.assertEqual(prof_res.status_code, 200)
        profile_data = prof_res.json()["profile"]
        stats = profile_data["stats"]
        self.assertGreaterEqual(stats["saved_conversations_count"], 1)
        self.assertGreaterEqual(stats["saved_itineraries_count"], 1)
        self.assertGreaterEqual(stats["confirmed_bookings_count"], 1)


if __name__ == "__main__":
    unittest.main()
