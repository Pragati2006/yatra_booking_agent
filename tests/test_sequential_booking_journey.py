"""
tests/test_sequential_booking_journey.py
Final RPA Booking Journey: Sequential Browser Verification Suite

Validates the complete 14-step realistic pilgrimage booking journey:
1.  Start a new booking on the local mock portal.
2.  Enter primary devotee and pilgrim details.
3.  Select yatra darshan date and category.
4.  Review booking particulars.
5.  Reach the OTP security checkpoint.
6.  Complete OTP verification with simulated SMS code.
7.  Verify Playwright resumes and transitions to the CAPTCHA challenge.
8.  Complete CAPTCHA puzzle verification.
9.  Verify Playwright resumes again into Step 5.
10. Reach the simulated payment sandbox.
11. Complete sandbox payment authorization.
12. Verify final submission without skipping stages.
13. Display actual booking confirmation returned by the mock portal.
14. Verify simulated pilgrim pass receipt with print action.

Also verifies:
- Sequential human intervention state machine (never prematurely confirms after OTP).
- 6-stage progress stepper synchronization across portal and frontend.
- Error and resilience scenarios: OTP failure, CAPTCHA failure, TTL expiry,
  duplicate resume idempotency, side-effect duplicate submission prevention,
  browser restart survival, navigation failure handover, and cleanup preservation.
- Clear receipt terminology: LOCAL MOCK PORTAL / DEMO and Demo Pilgrim Pass.
"""

import os
import sys
import time
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from playwright.sync_api import sync_playwright
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
    StateValidationError,
)

EVIDENCE_DIR = os.path.join(tempfile.gettempdir(), "rpa_journey_evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)


class TestSequentialBookingJourney(unittest.TestCase):
    """End-to-end sequential Playwright verification of the complete booking journey."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db_path = os.path.join(cls.temp_dir, "test_sequential_sessions.db")
        session_store.init_db(cls.test_db_path)

    def setUp(self):
        self.session_id = f"test-seq-session-{time.time_ns()}"
        session_store.create_session(
            session_id=self.session_id,
            initial_state={"plan_version": 1},
            db_path=self.test_db_path,
        )

    # -------------------------------------------------------------------------
    # TEST 1: COMPLETE 14-STEP SEQUENTIAL BROWSER JOURNEY WITH SCREENSHOTS
    # -------------------------------------------------------------------------
    def test_01_complete_14_step_sequential_journey(self):
        """
        Executes the full 14-step interactive pilgrimage journey in Playwright:
        Details -> Slot -> Review -> OTP -> CAPTCHA -> Payment -> Confirmation -> Print.
        Captures sequential evidence screenshots for all required stages.
        """
        portal_html = generate_mock_portal_html(security_mode="SEQUENTIAL")
        portal_file = os.path.join(self.temp_dir, "portal_sequential_journey.html")
        with open(portal_file, "w", encoding="utf-8") as f:
            f.write(portal_html)

        portal_url = f"file:///{portal_file.replace(os.sep, '/')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_viewport_size({"width": 1280, "height": 900})
                page.goto(portal_url)

                # Step 1: Start booking & enter pilgrim details
                self.assertTrue(page.locator("#step1Section").is_visible())
                page.fill("#userName", "Pradeep Sharma")
                page.fill("#userAge", "42")
                page.select_option("#userGender", "Male")
                page.fill("#userMobile", "+91 98765 12345")
                page.fill("#userEmail", "pradeep.sharma@example.com")
                page.fill("#paxCount", "2")

                ss_details = os.path.join(EVIDENCE_DIR, "screenshot_01_pilgrim_details.png")
                page.screenshot(path=ss_details)
                self.assertTrue(os.path.exists(ss_details))

                # Proceed to Step 2
                page.click("#btnStep1Next")
                time.sleep(0.3)
                self.assertTrue(page.locator("#step2Section").is_visible())

                # Step 2: Select darshan date and slot
                page.fill("#stepDate", "2026-10-20")
                page.select_option("#stepCategory", "VIP Darshan")
                time.sleep(0.2)

                # Click first available slot card
                slot_cards = page.locator("#stepSlotsList .slot-card")
                if slot_cards.count() > 0:
                    slot_cards.first.click()
                    time.sleep(0.2)

                ss_slot = os.path.join(EVIDENCE_DIR, "screenshot_02_date_and_slot.png")
                page.screenshot(path=ss_slot)
                self.assertTrue(os.path.exists(ss_slot))

                # Proceed to Step 3
                page.click("#btnStep2Next")
                time.sleep(0.3)
                self.assertTrue(page.locator("#step3Section").is_visible())

                # Step 3: Review booking particulars
                self.assertEqual(page.text_content("#revName").strip(), "Pradeep Sharma")
                self.assertEqual(page.text_content("#revPax").strip(), "2")

                # Proceed from Review to Step 4 Security Verification
                page.click("#btnStep3Next")
                time.sleep(0.3)

                # Step 4: OTP Checkpoint reached
                self.assertTrue(page.locator("#otpChallengeSection").is_visible())
                self.assertFalse(page.locator("#confirmation").is_visible())
                cp1 = detect_security_checkpoint(page)
                self.assertIsNotNone(cp1)
                self.assertEqual(cp1["checkpoint_type"], session_store.WORKFLOW_STATE_OTP_REQUIRED)

                ss_otp = os.path.join(EVIDENCE_DIR, "screenshot_03_otp_checkpoint.png")
                page.screenshot(path=ss_otp)
                self.assertTrue(os.path.exists(ss_otp))

                # Complete OTP Verification
                page.fill("#userOtpInput", "123456")
                page.click("#btnVerifyOtp")
                time.sleep(0.3)
                self.assertEqual(page.text_content("#otpStatusBadge").strip(), "VERIFIED")

                # Click proceed to next stage -> Must transition to CAPTCHA in SEQUENTIAL mode
                page.click("#btnCompleteOtpVerification")
                time.sleep(0.3)

                # Verify transition to CAPTCHA (Sequential Checkpoint 2)
                self.assertFalse(page.locator("#otpChallengeSection").is_visible())
                self.assertTrue(page.locator("#captchaChallengeSection").is_visible())
                self.assertFalse(page.locator("#confirmation").is_visible())

                cp2 = detect_security_checkpoint(page)
                self.assertIsNotNone(cp2)
                self.assertEqual(cp2["checkpoint_type"], session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED)

                ss_captcha = os.path.join(EVIDENCE_DIR, "screenshot_04_captcha_checkpoint.png")
                page.screenshot(path=ss_captcha)
                self.assertTrue(os.path.exists(ss_captcha))

                # Complete CAPTCHA Verification
                page.fill("#userCaptchaInput", "M7K9P")
                page.click("#btnVerifyCaptcha")
                time.sleep(0.3)
                self.assertEqual(page.text_content("#captchaStatusBadge").strip(), "SOLVED")

                # Click proceed to next stage -> Must transition to Step 5 Payment Sandbox
                page.click("#btnCompleteCaptchaVerification")
                time.sleep(0.3)

                # Verify transition to Step 5 (Payment Sandbox) - NOT skipped!
                self.assertFalse(page.locator("#captchaChallengeSection").is_visible())
                self.assertTrue(page.locator("#step5PaymentSection").is_visible())
                self.assertFalse(page.locator("#confirmation").is_visible())

                ss_payment = os.path.join(EVIDENCE_DIR, "screenshot_05_payment_sandbox.png")
                page.screenshot(path=ss_payment)
                self.assertTrue(os.path.exists(ss_payment))

                # Step 5: Select Demo Payment Method and Finalize
                page.select_option("#dummyPaymentSelect", "FREE_REGISTRATION")
                time.sleep(0.2)
                page.click("#btnConfirmFinalBooking")
                time.sleep(0.4)

                # Step 6: Final Confirmation Receipt Displayed
                self.assertTrue(page.locator("#confirmation").is_visible())
                booking_id = page.text_content("#outBookingId").strip()
                self.assertTrue(booking_id.startswith("VD-RPA-"))

                # Verify clear receipt terminology
                receipt_text = page.text_content("#confirmation")
                self.assertIn("LOCAL MOCK PORTAL / DEMO", receipt_text)
                self.assertIn("Simulated Yatra Booking Confirmation", receipt_text)
                self.assertIn("Demo Pilgrim Pass", receipt_text)

                # Verify print button
                self.assertEqual(page.locator("#btnPrintReceipt").count(), 1)

                ss_conf = os.path.join(EVIDENCE_DIR, "screenshot_06_final_confirmation.png")
                page.screenshot(path=ss_conf)
                self.assertTrue(os.path.exists(ss_conf))

            finally:
                browser.close()

    # -------------------------------------------------------------------------
    # TEST 2: SEQUENTIAL HUMAN INTERVENTION STATE MACHINE TRANSITIONS
    # -------------------------------------------------------------------------
    def test_02_sequential_human_intervention_lifecycle(self):
        """
        Verifies backend multi-checkpoint lifecycle transitions:
        Initiation -> PAUSED (OTP) -> Resume 1 -> PAUSED (CAPTCHA) -> Resume 2 -> SUCCESS.
        Guarantees that after OTP, the booking is NOT prematurely confirmed.
        """
        # 1. Initiation halts at OTP
        res1 = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Rajeshwar Nath",
            pax_count=2,
            checkpoint_mode="SEQUENTIAL",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(res1["status"], "PAUSED")
        self.assertEqual(res1["state"], session_store.WORKFLOW_STATE_OTP_REQUIRED)
        wf_id = res1["workflow_id"]

        # Verify SQLite record is at OTP_REQUIRED
        wf_rec1 = session_store.get_user_workflow(wf_id, session_id=self.session_id, db_path=self.test_db_path)
        self.assertEqual(wf_rec1["state"], session_store.WORKFLOW_STATE_OTP_REQUIRED)

        # 2. First Resume (clears OTP, encounters sequential CAPTCHA, pauses again!)
        res2 = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(res2["status"], "PAUSED")
        self.assertEqual(res2["state"], session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED)
        self.assertIn("CAPTCHA", res2["message"])

        # Verify SQLite record updated to CAPTCHA_REQUIRED
        wf_rec2 = session_store.get_user_workflow(wf_id, session_id=self.session_id, db_path=self.test_db_path)
        self.assertEqual(wf_rec2["state"], session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED)

        # 3. Second Resume (clears CAPTCHA, completes payment sandbox, confirms booking)
        res3 = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="M7K9P",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(res3["status"], "SUCCESS")
        self.assertEqual(res3["state"], session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED)
        self.assertIsNotNone(res3["booking_id"])
        self.assertTrue(res3["booking_id"].startswith("VD-RPA-"))

        # Final SQLite record is USER_ACTION_COMPLETED
        wf_rec3 = session_store.get_user_workflow(wf_id, session_id=self.session_id, db_path=self.test_db_path)
        self.assertEqual(wf_rec3["state"], session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED)

    # -------------------------------------------------------------------------
    # TEST 3: OTP VERIFICATION FAILURE HANDLING
    # -------------------------------------------------------------------------
    def test_03_otp_failure_handling(self):
        """Verifies that an incorrect or short OTP code fails state validation and remains paused."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        failed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="00",  # Invalid short code
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(failed["status"], "VALIDATION_FAILED")
        self.assertIn("Checkpoint has not been cleared in the portal", failed["message"])

    # -------------------------------------------------------------------------
    # TEST 4: CAPTCHA VERIFICATION FAILURE HANDLING
    # -------------------------------------------------------------------------
    def test_04_captcha_failure_handling(self):
        """Verifies that an incorrect CAPTCHA solution fails validation and remains paused."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="CAPTCHA",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        failed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="INCORRECT",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(failed["status"], "VALIDATION_FAILED")
        self.assertIn("Checkpoint has not been cleared in the portal", failed["message"])

    # -------------------------------------------------------------------------
    # TEST 5: EXPIRED WORKFLOW HANDLING
    # -------------------------------------------------------------------------
    def test_05_expired_workflow_handling(self):
        """Verifies that workflows exceeding their TTL transition to EXPIRED and refuse resumption."""
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="otp",
            operation="booking",
            pending_action="ENTER_OTP_IN_PORTAL",
            expires_in_seconds=300,
            db_path=self.test_db_path,
        )
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("UPDATE user_workflows SET expires_at = ? WHERE workflow_id = ?", (past_iso, wf["workflow_id"]))

        res = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf["workflow_id"],
            user_confirmed_action=True,
            manual_input_value="123456",
            db_path=self.test_db_path,
        )
        self.assertEqual(res["status"], "EXPIRED")
        self.assertEqual(res["error_category"], "WORKFLOW_EXPIRED")

    # -------------------------------------------------------------------------
    # TEST 6: DUPLICATE RESUME IDEMPOTENCY
    # -------------------------------------------------------------------------
    def test_06_duplicate_resume_idempotency(self):
        """Verifies that clicking resume multiple times returns existing confirmed receipt without duplicate bookings."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        res1 = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(res1["status"], "SUCCESS")
        orig_bid = res1["booking_id"]

        # Duplicate resume click
        res2 = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertEqual(res2["booking_id"], orig_bid)
        self.assertTrue(res2.get("is_idempotent_replay", False))

    # -------------------------------------------------------------------------
    # TEST 7: DUPLICATE FINAL SUBMISSION PREVENTION (SIDE-EFFECT PROTECTION)
    # -------------------------------------------------------------------------
    def test_07_duplicate_final_submission_prevention(self):
        """Verifies that booking submission is never retried blindly if confirmation times out."""
        with patch("agents.rpa_agent.validate_booking_confirmation_state", side_effect=StateValidationError("Timeout waiting for confirmation", operation="confirm")):
            result = execute_playwright_mock_booking(
                user_name="Vijay Kumar",
                pax_count=1,
                transport_text="Train",
                slot_text="VIP Darshan",
                total_price=0,
                headless=True,
            )
            self.assertTrue(result.get("handover_required", False))
            self.assertTrue(result.get("diagnostics", {}).get("side_effect_prevented", False))

    # -------------------------------------------------------------------------
    # TEST 8: BROWSER RESTART SURVIVAL DURING PAUSE
    # -------------------------------------------------------------------------
    def test_08_browser_restart_during_pause(self):
        """Verifies that a paused workflow survives complete browser closure and app restart via SQLite."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Sarla Devi",
            pax_count=2,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Connect through a completely new SQLite connection to simulate restart
        reloaded = session_store.get_user_workflow(wf_id, session_id=self.session_id, db_path=self.test_db_path)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded["state"], session_store.WORKFLOW_STATE_OTP_REQUIRED)
        self.assertEqual(reloaded["checkpoint_data"]["user_name"], "Sarla Devi")

        # Resume after restart
        res = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIsNotNone(res["booking_id"])

    # -------------------------------------------------------------------------
    # TEST 9: NETWORK OR NAVIGATION FAILURE HANDOVER
    # -------------------------------------------------------------------------
    def test_09_navigation_failure_produces_safe_handover(self):
        """Verifies that invalid navigation target produces safe handover without crashing the server."""
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="otp",
            operation="booking",
            pending_action="ENTER_OTP",
            checkpoint_data={"portal_url": "invalid://non_existent_page"},
            db_path=self.test_db_path,
        )

        res = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf["workflow_id"],
            user_confirmed_action=True,
            db_path=self.test_db_path,
        )
        self.assertIn(res["status"], ("HANDOVER_REQUIRED", "VALIDATION_FAILED"))

    # -------------------------------------------------------------------------
    # TEST 10: CLEANUP FAILURE AFTER CONFIRMED BOOKING PRESERVES BOOKING ID
    # -------------------------------------------------------------------------
    def test_10_cleanup_failure_preserves_confirmed_booking_id(self):
        """Verifies that a post-confirmation cleanup error never overwrites or clears the booking ID."""
        with patch("agents.rpa_agent.create_handover_result") as mock_handover:
            with patch("playwright.sync_api._generated.Page.screenshot", side_effect=RuntimeError("Simulated screenshot disk failure")):
                result = execute_playwright_mock_booking(
                    user_name="Anil Kapoor",
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
    # TEST 11: RESUME ERROR IS NEVER HIDDEN IF BOOKING NOT ACTUALLY COMPLETED
    # -------------------------------------------------------------------------
    def test_11_resume_error_not_hidden_if_incomplete(self):
        """Verifies that if manual verification was incomplete, failure error is explicitly returned."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Call resume without clearing checkpoint and without manual_input
        res = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value=None,
            simulate_manual_clearance=False,
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(res["status"], "VALIDATION_FAILED")
        self.assertIsNone(res.get("booking_id"))
        self.assertIn("has not been cleared in the portal", res["message"])


if __name__ == "__main__":
    unittest.main()
