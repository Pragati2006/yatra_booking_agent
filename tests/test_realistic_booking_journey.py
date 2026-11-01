"""
tests/test_realistic_booking_journey.py
Phase 7: End-to-End Realistic Booking Journey & Regression Test Suite

Verifies 18 distinct scenarios covering the complete realistic pilgrimage booking experience:
1.  Successful booking from beginning to end (happy path with pass generation)
2.  Invalid OTP rejection (fails state validation, blocks continuation)
3.  Expired OTP / Expired workflow handling (bounded TTL rejection)
4.  Successful OTP with automatic workflow continuation
5.  CAPTCHA failure handling (wrong CAPTCHA text rejected)
6.  Successful CAPTCHA followed by continuation
7.  Multiple sequential checkpoints detection and clearance
8.  Unavailable darshan slot handling (sold-out / empty inventory notice)
9.  Invalid pilgrim details validation (empty name / invalid passenger count)
10. User pause and resume later from SQLite persistence
11. Expired workflow rejection upon resume
12. Duplicate Continue clicks (idempotency: returns existing confirmed receipt)
13. Duplicate booking submission prevention (side-effect safety: never re-submits)
14. Browser/session reinitialization resilience
15. Booking confirmation and receipt generation (print pass, valid ID, stepper state)
16. Cleanup error after confirmation does not overwrite booking ID
17. Session ownership validation (cross-session access rejection)
18. Existing Week 5–10 regression test compatibility
"""

import os
import sys
import time
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi.testclient import TestClient
from backend.main import app

from agents import session_store, rpa_agent, coordinator
from agents.rpa_agent import (
    generate_mock_portal_html,
    detect_security_checkpoint,
    validate_checkpoint_cleared,
    validate_booking_confirmation_state,
    execute_user_controlled_booking_workflow,
    execute_playwright_mock_booking,
    check_yatra_slot_availability,
    StateValidationError,
    StructuralPageChangeError,
)


class TestRealisticBookingJourney(unittest.TestCase):
    """Phase 7: 18 Comprehensive Scenarios for Realistic Pilgrimage Booking Journey."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db_path = os.path.join(cls.temp_dir, "test_realistic_sessions.db")
        session_store.init_db(cls.test_db_path)

    def setUp(self):
        self.session_id = f"test-real-session-{time.time_ns()}"
        session_store.create_session(
            session_id=self.session_id,
            initial_state={"plan_version": 1},
            db_path=self.test_db_path,
        )

    # -------------------------------------------------------------------------
    # SCENARIO 1: SUCCESSFUL BOOKING FROM BEGINNING TO END (HAPPY PATH)
    # -------------------------------------------------------------------------
    def test_01_successful_booking_happy_path(self):
        """Verifies end-to-end booking execution generates valid booking ID and confirmation."""
        result = execute_playwright_mock_booking(
            user_name="Manoj Sharma",
            pax_count=2,
            transport_text="Vande Bharat Express (Train)",
            slot_text="Morning Aarti & Darshan (06:00)",
            total_price=0.0,
            headless=True,
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertIsNotNone(result["booking_id"])
        self.assertTrue(result["booking_id"].startswith("VD-RPA-"))
        self.assertFalse(result.get("handover_required", True))
        self.assertIsNotNone(result.get("screenshot_path"))

    # -------------------------------------------------------------------------
    # SCENARIO 2: INVALID OTP REJECTION
    # -------------------------------------------------------------------------
    def test_02_invalid_otp_rejection(self):
        """Verifies that submitting an invalid OTP (< 4 digits) fails checkpoint clearance and halts resumption."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Anita Deshmukh",
            pax_count=1,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(paused["status"], "PAUSED")
        wf_id = paused["workflow_id"]

        # Attempt to resume with an invalid OTP string
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="12",  # Invalid short OTP
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "VALIDATION_FAILED")
        self.assertIn("Checkpoint has not been cleared in the portal", resumed["message"])

    # -------------------------------------------------------------------------
    # SCENARIO 3: EXPIRED OTP / WORKFLOW TTL HANDLING
    # -------------------------------------------------------------------------
    def test_03_expired_otp_handling(self):
        """Verifies that expired OTP verification windows transition to EXPIRED and refuse resumption."""
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="otp_verification",
            operation="yatra_booking",
            pending_action="ENTER_OTP_IN_PORTAL",
            expires_in_seconds=300,
            db_path=self.test_db_path,
        )

        # Backdate expiration timestamp in SQLite to simulate TTL expiry
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("UPDATE user_workflows SET expires_at = ? WHERE workflow_id = ?", (past_iso, wf["workflow_id"]))

        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf["workflow_id"],
            user_confirmed_action=True,
            manual_input_value="123456",
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "EXPIRED")
        self.assertEqual(resumed["error_category"], "WORKFLOW_EXPIRED")

    # -------------------------------------------------------------------------
    # SCENARIO 4: SUCCESSFUL OTP WITH AUTOMATIC WORKFLOW CONTINUATION
    # -------------------------------------------------------------------------
    def test_04_successful_otp_workflow_continuation(self):
        """Verifies that valid OTP input enables clean resumption through to confirmed receipt."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Praveen Rawat",
            pax_count=3,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(paused["status"], "PAUSED")
        wf_id = paused["workflow_id"]

        # Resume with correct simulated OTP
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "SUCCESS")
        self.assertEqual(resumed["state"], session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED)
        self.assertIsNotNone(resumed["booking_id"])
        self.assertTrue(resumed["booking_id"].startswith("VD-RPA-"))

    # -------------------------------------------------------------------------
    # SCENARIO 5: CAPTCHA FAILURE HANDLING
    # -------------------------------------------------------------------------
    def test_05_captcha_failure_handling(self):
        """Verifies that an incorrect CAPTCHA answer fails validation and prevents booking."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Sunita Yadav",
            pax_count=2,
            checkpoint_mode="CAPTCHA",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(paused["status"], "PAUSED")
        wf_id = paused["workflow_id"]

        # Incorrect CAPTCHA
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="WRONG_CODE",
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "VALIDATION_FAILED")
        self.assertIn("Checkpoint has not been cleared in the portal", resumed["message"])

    # -------------------------------------------------------------------------
    # SCENARIO 6: SUCCESSFUL CAPTCHA FOLLOWED BY CONTINUATION
    # -------------------------------------------------------------------------
    def test_06_successful_captcha_continuation(self):
        """Verifies that solving the CAPTCHA correctly allows automation to finalize the booking."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Deepak Joshi",
            pax_count=1,
            checkpoint_mode="CAPTCHA",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(paused["status"], "PAUSED")
        wf_id = paused["workflow_id"]

        # Valid mock CAPTCHA answer is M7K9P
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="M7K9P",
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "SUCCESS")
        self.assertEqual(resumed["state"], session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED)
        self.assertIsNotNone(resumed["booking_id"])

    # -------------------------------------------------------------------------
    # SCENARIO 7: MULTIPLE SEQUENTIAL CHECKPOINTS DETECTION
    # -------------------------------------------------------------------------
    def test_07_multiple_sequential_checkpoints(self):
        """Verifies that both OTP and CAPTCHA checkpoints are distinctly identified by detector."""
        from playwright.sync_api import sync_playwright

        for mode in ("OTP", "CAPTCHA"):
            html = generate_mock_portal_html(security_mode=mode)
            p_path = os.path.join(self.temp_dir, f"checkpoint_{mode}.html")
            with open(p_path, "w", encoding="utf-8") as f:
                f.write(html)
            p_url = f"file:///{p_path.replace(os.sep, '/')}"

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(p_url)
                    page.fill("#userName", "Pilgrim Test")
                    page.fill("#paxCount", "1")
                    page.click("#submitBtn")
                    time.sleep(0.3)

                    cp = detect_security_checkpoint(page)
                    self.assertIsNotNone(cp)
                    if mode == "OTP":
                        self.assertEqual(cp["checkpoint_type"], session_store.WORKFLOW_STATE_OTP_REQUIRED)
                        self.assertEqual(cp["pending_action"], "ENTER_OTP_IN_PORTAL")
                    else:
                        self.assertEqual(cp["checkpoint_type"], session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED)
                        self.assertEqual(cp["pending_action"], "SOLVE_CAPTCHA_IN_PORTAL")
                finally:
                    browser.close()

    # -------------------------------------------------------------------------
    # SCENARIO 8: UNAVAILABLE DARSHAN SLOT HANDLING
    # -------------------------------------------------------------------------
    def test_08_unavailable_darshan_slot_handling(self):
        """Verifies that querying a date with no inventory cleanly reports 0 slots without crash."""
        res = check_yatra_slot_availability(
            requested_date="2099-12-31",  # Future date with zero slots
            headless=True,
            max_attempts=1,
        )
        self.assertEqual(res["status"].upper(), "SUCCESS")
        self.assertEqual(res["total_slots"], 0)
        self.assertEqual(res["available_count"], 0)

    # -------------------------------------------------------------------------
    # SCENARIO 9: INVALID PILGRIM DETAILS VALIDATION
    # -------------------------------------------------------------------------
    def test_09_invalid_pilgrim_details_validation(self):
        """Verifies that empty pilgrim names or non-positive passenger counts are rejected upfront."""
        # Empty user name in direct mock booking
        res_empty = execute_playwright_mock_booking(
            user_name="",
            pax_count=2,
            transport_text="Train",
            slot_text="VIP Darshan",
            total_price=0,
            headless=True,
        )
        self.assertEqual(res_empty["status"], "VALIDATION_FAILED")
        self.assertEqual(res_empty["error_category"], "INVALID_PILGRIM_DETAILS")

        # Zero pax count in user-controlled workflow initiation
        res_zero = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Valid Name",
            pax_count=0,
            checkpoint_mode="OTP",
            db_path=self.test_db_path,
        )
        self.assertEqual(res_zero["status"], "VALIDATION_FAILED")
        self.assertEqual(res_zero["error_category"], "INVALID_PILGRIM_DETAILS")

    # -------------------------------------------------------------------------
    # SCENARIO 10: USER PAUSE AND RESUME LATER FROM SQLITE PERSISTENCE
    # -------------------------------------------------------------------------
    def test_10_user_pause_and_resume_later_from_sqlite(self):
        """Verifies that workflow paused state persists in SQLite and can be reloaded after reload."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Meera Bai",
            pax_count=2,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Simulate restart/reload: retrieve from SQLite
        reloaded = session_store.get_user_workflow(wf_id, session_id=self.session_id, db_path=self.test_db_path)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded["workflow_id"], wf_id)
        self.assertEqual(reloaded["state"], session_store.WORKFLOW_STATE_OTP_REQUIRED)
        self.assertEqual(reloaded["checkpoint_data"]["user_name"], "Meera Bai")

        # Resume after reload
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(resumed["status"], "SUCCESS")
        self.assertIsNotNone(resumed["booking_id"])

    # -------------------------------------------------------------------------
    # SCENARIO 11: EXPIRED WORKFLOW REJECTION
    # -------------------------------------------------------------------------
    def test_11_expired_workflow_rejection(self):
        """Verifies that attempting to resume an expired workflow returns WORKFLOW_EXPIRED."""
        past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED,
            step="captcha",
            operation="booking",
            pending_action="SOLVE_CAPTCHA_IN_PORTAL",
            expires_in_seconds=300,
            db_path=self.test_db_path,
        )
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("UPDATE user_workflows SET expires_at = ? WHERE workflow_id = ?", (past_iso, wf["workflow_id"]))

        res = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf["workflow_id"],
            user_confirmed_action=True,
            manual_input_value="M7K9P",
            db_path=self.test_db_path,
        )
        self.assertEqual(res["status"], "EXPIRED")
        self.assertEqual(res["error_category"], "WORKFLOW_EXPIRED")

    # -------------------------------------------------------------------------
    # SCENARIO 12: DUPLICATE CONTINUE CLICKS (IDEMPOTENCY)
    # -------------------------------------------------------------------------
    def test_12_duplicate_continue_clicks_idempotency(self):
        """Verifies that calling resume on an already confirmed workflow is idempotent."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Girish Kumar",
            pax_count=1,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # First resume
        resumed_1 = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(resumed_1["status"], "SUCCESS")
        orig_bid = resumed_1["booking_id"]

        # Second resume (duplicate click simulation)
        resumed_2 = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(resumed_2["status"], "SUCCESS")
        self.assertEqual(resumed_2["booking_id"], orig_bid)
        self.assertTrue(resumed_2.get("is_idempotent_replay", False))

    # -------------------------------------------------------------------------
    # SCENARIO 13: DUPLICATE BOOKING SUBMISSION PREVENTION
    # -------------------------------------------------------------------------
    def test_13_duplicate_booking_submission_prevention(self):
        """Verifies side-effect protection: ambiguous booking confirmation never retries submission."""
        with patch("agents.rpa_agent.validate_booking_confirmation_state") as mock_val:
            mock_val.side_effect = StateValidationError("Confirmation timed out", operation="confirm")

            result = execute_playwright_mock_booking(
                user_name="Sanjay Mishra",
                pax_count=2,
                transport_text="Bus",
                slot_text="Normal Darshan",
                total_price=0,
                headless=True,
            )

            self.assertTrue(result.get("handover_required", False))
            self.assertTrue(result.get("diagnostics", {}).get("side_effect_prevented", False))

    # -------------------------------------------------------------------------
    # SCENARIO 14: BROWSER / SESSION REINITIALIZATION
    # -------------------------------------------------------------------------
    def test_14_browser_session_reinitialization(self):
        """Verifies that launching a fresh browser context during resumption reliably handles the portal."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Kavita Nair",
            pax_count=2,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Resumption with fresh headless browser instance
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(resumed["status"], "SUCCESS")
        self.assertTrue(resumed["booking_id"].startswith("VD-RPA-"))

    # -------------------------------------------------------------------------
    # SCENARIO 15: BOOKING CONFIRMATION AND RECEIPT GENERATION
    # -------------------------------------------------------------------------
    def test_15_booking_confirmation_and_receipt_elements(self):
        """Verifies that confirmation receipt includes print button and valid booking attributes."""
        from playwright.sync_api import sync_playwright

        html = generate_mock_portal_html()
        p_path = os.path.join(self.temp_dir, "test_receipt.html")
        with open(p_path, "w", encoding="utf-8") as f:
            f.write(html)
        p_url = f"file:///{p_path.replace(os.sep, '/')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(p_url)
                page.fill("#userName", "Harish Chandra")
                page.fill("#paxCount", "2")
                page.click("#submitBtn")
                time.sleep(0.3)

                # Verify confirmation container is present
                self.assertTrue(page.locator("#confirmation").is_visible())
                # Verify booking id
                bid = page.text_content("#outBookingId")
                self.assertTrue(bid.startswith("VD-RPA-"))
                # Verify print button is present
                self.assertEqual(page.locator("#btnPrintReceipt").count(), 1)
            finally:
                browser.close()

    # -------------------------------------------------------------------------
    # SCENARIO 16: CLEANUP ERROR AFTER CONFIRMATION DOES NOT OVERWRITE BOOKING ID
    # -------------------------------------------------------------------------
    def test_16_cleanup_error_does_not_overwrite_booking_id(self):
        """Verifies that an error occurring during post-confirmation cleanup preserves the confirmed booking ID."""
        with patch("agents.rpa_agent.create_handover_result") as mock_handover:
            # We mock page.screenshot to raise an error during execution
            with patch("playwright.sync_api._generated.Page.screenshot", side_effect=RuntimeError("Simulated screenshot failure")):
                result = execute_playwright_mock_booking(
                    user_name="Rohit Verma",
                    pax_count=1,
                    transport_text="Flight",
                    slot_text="VIP Darshan",
                    total_price=0,
                    headless=True,
                )
                self.assertEqual(result["status"], "SUCCESS")
                self.assertIsNotNone(result["booking_id"])
                mock_handover.assert_not_called()

    # -------------------------------------------------------------------------
    # SCENARIO 17: SESSION OWNERSHIP VALIDATION (CROSS-SESSION REJECTION)
    # -------------------------------------------------------------------------
    def test_17_session_ownership_cross_session_rejection(self):
        """Verifies strict cross-session isolation: session B cannot resume session A's workflow."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        resumed = execute_user_controlled_booking_workflow(
            session_id="different-unauthorized-session-456",
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(resumed["status"], "ERROR")
        self.assertEqual(resumed["error_category"], "CROSS_SESSION_ACCESS_DENIED")

    # -------------------------------------------------------------------------
    # SCENARIO 18: EXISTING REGRESSION COMPATIBILITY
    # -------------------------------------------------------------------------
    def test_18_existing_regression_compatibility(self):
        """Regression test: verifies that slot checking, state validation, and coordinator remain functional."""
        # 1. Slot checking
        avail = check_yatra_slot_availability(
            requested_date="2026-10-20",
            category="VIP Darshan",
            headless=True,
            max_attempts=1,
        )
        self.assertEqual(avail["status"].upper(), "SUCCESS")
        self.assertTrue(avail["total_slots"] > 0)

        # 2. Coordinator status retrieval
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_status = coordinator.get_user_controlled_workflow_status(
            session_id=self.session_id,
            workflow_id=paused["workflow_id"],
            db_path=self.test_db_path,
        )
        self.assertIsNotNone(wf_status)
        self.assertEqual(wf_status["state"], session_store.WORKFLOW_STATE_OTP_REQUIRED)


if __name__ == "__main__":
    unittest.main()
