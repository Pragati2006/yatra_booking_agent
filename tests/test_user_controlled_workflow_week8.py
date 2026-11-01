"""
tests/test_user_controlled_workflow_week8.py
Comprehensive Week 8 Test Suite: User-Controlled Workflow Implementation.

Verifies:
1. OTP checkpoint detection.
2. CAPTCHA checkpoint detection.
3. Agent pauses when intervention is required.
4. User receives the correct intervention message.
5. Workflow state is saved in SQLite.
6. Pending workflow can be retrieved.
7. Workflow state survives application restart.
8. Correct user/session can resume its own workflow.
9. Another session cannot resume that workflow (cross-session rejection).
10. Resume requires explicit user confirmation.
11. Browser state is validated before resumption.
12. Expired workflows cannot resume.
13. Cancelled workflows cannot resume.
14. Invalid user confirmation is rejected.
15. Browser closure produces safe handover.
16. No OTP or password is stored in session records.
17. No automatic CAPTCHA solving occurs.
18. No automatic payment or booking retry occurs.
19. Existing Week 5 availability tests pass.
20. Existing Week 6 error-handling tests pass.
21. Existing Week 7 LLM integration tests pass.
22. Existing booking authorization safeguards remain intact.
"""

import os
import sys
import io
import time
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Ensure UTF-8 output encoding on Windows consoles safely
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
    execute_user_controlled_booking_workflow,
    execute_playwright_mock_booking,
)


class TestUserControlledWorkflowWeek8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db_path = os.path.join(cls.temp_dir, "test_week8_sessions.db")
        session_store.init_db(cls.test_db_path)

    def setUp(self):
        self.session_id = f"test-session-{time.time_ns()}"
        session_store.create_session(
            session_id=self.session_id,
            initial_state={"plan_version": 1},
            db_path=self.test_db_path,
        )

    # -------------------------------------------------------------------------
    # TEST 1: OTP CHECKPOINT DETECTION
    # -------------------------------------------------------------------------
    def test_01_otp_checkpoint_detection(self):
        """Verifies that the Playwright RPA agent accurately detects OTP checkpoint on page."""
        from playwright.sync_api import sync_playwright

        html_content = generate_mock_portal_html(security_mode="OTP")
        portal_path = os.path.join(self.temp_dir, "mock_otp_test.html")
        with open(portal_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        portal_url = f"file:///{portal_path.replace(os.sep, '/')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(portal_url)
                page.fill("#userName", "Ramesh Kumar")
                page.fill("#paxCount", "2")
                page.click("#submitBtn")
                time.sleep(0.3)

                checkpoint = detect_security_checkpoint(page)
                self.assertIsNotNone(checkpoint)
                self.assertEqual(checkpoint["checkpoint_type"], session_store.WORKFLOW_STATE_OTP_REQUIRED)
                self.assertEqual(checkpoint["status"], session_store.WORKFLOW_STATE_WAITING_FOR_USER)
                self.assertEqual(checkpoint["pending_action"], "ENTER_OTP_IN_PORTAL")
                self.assertIn("OTP", checkpoint["message"])
            finally:
                browser.close()

    # -------------------------------------------------------------------------
    # TEST 2: CAPTCHA CHECKPOINT DETECTION
    # -------------------------------------------------------------------------
    def test_02_captcha_checkpoint_detection(self):
        """Verifies that the Playwright RPA agent accurately detects CAPTCHA challenge checkpoint."""
        from playwright.sync_api import sync_playwright

        html_content = generate_mock_portal_html(security_mode="CAPTCHA")
        portal_path = os.path.join(self.temp_dir, "mock_captcha_test.html")
        with open(portal_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        portal_url = f"file:///{portal_path.replace(os.sep, '/')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(portal_url)
                page.fill("#userName", "Pooja Sharma")
                page.fill("#paxCount", "1")
                page.click("#submitBtn")
                time.sleep(0.3)

                checkpoint = detect_security_checkpoint(page)
                self.assertIsNotNone(checkpoint)
                self.assertEqual(checkpoint["checkpoint_type"], session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED)
                self.assertEqual(checkpoint["status"], session_store.WORKFLOW_STATE_WAITING_FOR_USER)
                self.assertEqual(checkpoint["pending_action"], "SOLVE_CAPTCHA_IN_PORTAL")
                self.assertIn("CAPTCHA", checkpoint["message"])
            finally:
                browser.close()

    # -------------------------------------------------------------------------
    # TEST 3: AGENT PAUSES WHEN INTERVENTION IS REQUIRED
    # -------------------------------------------------------------------------
    def test_03_agent_pauses_when_intervention_is_required(self):
        """Verifies that execution halts cleanly at the checkpoint returning PAUSED envelope."""
        result = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            user_name="Sunil Verma",
            pax_count=2,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(result["status"], "PAUSED")
        self.assertEqual(result["state"], session_store.WORKFLOW_STATE_OTP_REQUIRED)
        self.assertIn("workflow_id", result)
        self.assertIsNotNone(result["workflow_id"])
        self.assertFalse(result.get("handover_required", True))

    # -------------------------------------------------------------------------
    # TEST 4: USER RECEIVES THE CORRECT INTERVENTION MESSAGE
    # -------------------------------------------------------------------------
    def test_04_user_receives_correct_intervention_message(self):
        """Verifies that the intervention message instructs user to enter OTP in portal, not in chat."""
        result_otp = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertIn("Never provide OTPs to the AI chat", result_otp["message"])
        self.assertIn("authorized booking portal", result_otp["message"])

        result_captcha = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="CAPTCHA",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertIn("Automation is strictly prohibited from bypassing this challenge", result_captcha["message"])

    # -------------------------------------------------------------------------
    # TEST 5: WORKFLOW STATE IS SAVED IN SQLITE
    # -------------------------------------------------------------------------
    def test_05_workflow_state_is_saved_in_sqlite(self):
        """Verifies that workflow records are properly inserted into user_workflows SQLite table."""
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="security_checkpoint",
            operation="mock_booking",
            pending_action="ENTER_OTP_IN_PORTAL",
            expires_in_seconds=300,
            checkpoint_data={"pax": 2, "slot": "Morning"},
            db_path=self.test_db_path,
        )

        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT state, step, operation, pending_action FROM user_workflows WHERE workflow_id = ?", (wf["workflow_id"],))
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], session_store.WORKFLOW_STATE_OTP_REQUIRED)
        self.assertEqual(row[1], "security_checkpoint")
        self.assertEqual(row[2], "mock_booking")
        self.assertEqual(row[3], "ENTER_OTP_IN_PORTAL")

    # -------------------------------------------------------------------------
    # TEST 6: PENDING WORKFLOW CAN BE RETRIEVED
    # -------------------------------------------------------------------------
    def test_06_pending_workflow_can_be_retrieved(self):
        """Verifies that pending workflows are retrievable via session_store and FastAPI endpoint."""
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED,
            step="captcha_gate",
            operation="yatra_booking",
            pending_action="SOLVE_CAPTCHA_IN_PORTAL",
            db_path=self.test_db_path,
        )

        retrieved = session_store.get_user_workflow(wf["workflow_id"], session_id=self.session_id, db_path=self.test_db_path)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["workflow_id"], wf["workflow_id"])
        self.assertEqual(retrieved["state"], session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED)

        # Test FastAPI endpoint
        with patch("agents.session_store.DEFAULT_DB_PATH", self.test_db_path):
            resp = self.client.get(f"/api/yatra/rpa/workflow/{wf['workflow_id']}?session_id={self.session_id}")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["workflow"]["workflow_id"], wf["workflow_id"])

    # -------------------------------------------------------------------------
    # TEST 7: WORKFLOW STATE SURVIVES APPLICATION RESTART
    # -------------------------------------------------------------------------
    def test_07_workflow_state_survives_application_restart(self):
        """Simulates full application restart with SQLite reload and verifies workflow persists."""
        restart_db = os.path.join(self.temp_dir, "restart_test.db")
        session_store.init_db(restart_db)

        wf = session_store.create_user_workflow(
            session_id="restart-session-123",
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="checkpoint",
            operation="booking",
            pending_action="ENTER_OTP",
            checkpoint_data={"pilgrim": "Aarav"},
            db_path=restart_db,
        )

        # "Restart": new connection, reload state
        reloaded_wf = session_store.get_user_workflow(wf["workflow_id"], session_id="restart-session-123", db_path=restart_db)
        self.assertIsNotNone(reloaded_wf)
        self.assertEqual(reloaded_wf["workflow_id"], wf["workflow_id"])
        self.assertEqual(reloaded_wf["state"], session_store.WORKFLOW_STATE_OTP_REQUIRED)
        self.assertEqual(reloaded_wf["checkpoint_data"].get("pilgrim"), "Aarav")

    # -------------------------------------------------------------------------
    # TEST 8: CORRECT USER/SESSION CAN RESUME ITS OWN WORKFLOW
    # -------------------------------------------------------------------------
    def test_08_correct_user_can_resume_workflow(self):
        """Verifies that the session that created the workflow can resume it with valid clearance."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        self.assertEqual(paused["status"], "PAUSED")
        wf_id = paused["workflow_id"]

        # Resume with simulated manual clearance
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

    # -------------------------------------------------------------------------
    # TEST 9: ANOTHER SESSION CANNOT RESUME THAT WORKFLOW (CROSS-SESSION REJECTION)
    # -------------------------------------------------------------------------
    def test_09_another_session_cannot_resume_workflow(self):
        """Verifies strict cross-session isolation: session B cannot resume session A's workflow."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Other session attempts to resume
        other_session = "malicious-or-different-session-999"
        resumed = execute_user_controlled_booking_workflow(
            session_id=other_session,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="123456",
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "ERROR")
        self.assertEqual(resumed["error_category"], "CROSS_SESSION_ACCESS_DENIED")

    # -------------------------------------------------------------------------
    # TEST 10: RESUME REQUIRES EXPLICIT USER CONFIRMATION
    # -------------------------------------------------------------------------
    def test_10_resume_requires_explicit_user_confirmation(self):
        """Verifies that attempting to resume without user_confirmed_action=True is rejected."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="CAPTCHA",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Call resume with user_confirmed_action=False
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=False,
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "REJECTED")
        self.assertEqual(resumed["error_category"], "CONFIRMATION_REQUIRED")

    # -------------------------------------------------------------------------
    # TEST 11: BROWSER STATE IS VALIDATED BEFORE RESUMPTION
    # -------------------------------------------------------------------------
    def test_11_browser_state_validated_before_resumption(self):
        """Verifies that if manual action was NOT completed in the portal, resumption rejects with VALIDATION_FAILED."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="OTP",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Call resume with invalid OTP (less than 4 digits)
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="12",  # invalid length, mock portal will not verify
            headless=True,
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "VALIDATION_FAILED")
        self.assertIn("has not been cleared in the portal", resumed["message"])

    # -------------------------------------------------------------------------
    # TEST 12: EXPIRED WORKFLOWS CANNOT RESUME
    # -------------------------------------------------------------------------
    def test_12_expired_workflows_cannot_resume(self):
        """Verifies that expired workflows transition to EXPIRED and refuse resumption."""
        # Create workflow that expires in the past
        past_dt = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="checkpoint",
            operation="booking",
            pending_action="ENTER_OTP",
            expires_in_seconds=300,
            db_path=self.test_db_path,
        )

        # Manually backdate expires_at in SQLite
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("UPDATE user_workflows SET expires_at = ? WHERE workflow_id = ?", (past_dt, wf["workflow_id"]))

        # Attempt to resume
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
    # TEST 13: CANCELLED WORKFLOWS CANNOT RESUME
    # -------------------------------------------------------------------------
    def test_13_cancelled_workflows_cannot_resume(self):
        """Verifies that cancelled workflows remain cancelled and cannot be resumed."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="CAPTCHA",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Cancel workflow
        cancel_res = session_store.cancel_user_workflow(wf_id, session_id=self.session_id, reason="Changed travel dates", db_path=self.test_db_path)
        self.assertEqual(cancel_res["status"], "success")
        self.assertEqual(cancel_res["state"], session_store.WORKFLOW_STATE_CANCELLED)

        # Attempt to resume
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value="M7K9P",
            db_path=self.test_db_path,
        )

        self.assertEqual(resumed["status"], "CANCELLED")
        self.assertEqual(resumed["error_category"], "WORKFLOW_CANCELLED")

    # -------------------------------------------------------------------------
    # TEST 14: INVALID USER CONFIRMATION IS REJECTED
    # -------------------------------------------------------------------------
    def test_14_invalid_user_confirmation_is_rejected(self):
        """Verifies that FastAPI /api/yatra/rpa/workflow/resume rejects missing or false user confirmation."""
        with patch("agents.session_store.DEFAULT_DB_PATH", self.test_db_path):
            resp = self.client.post("/api/yatra/rpa/workflow/resume", json={
                "session_id": self.session_id,
                "workflow_id": "non-existent-wf",
                "user_confirmed_action": False,
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "confirmation_required")

    # -------------------------------------------------------------------------
    # TEST 15: BROWSER CLOSURE PRODUCES SAFE HANDOVER
    # -------------------------------------------------------------------------
    def test_15_browser_closure_produces_safe_handover(self):
        """Verifies that if the browser page is unexpectedly closed, safe handover result is returned."""
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="security_checkpoint",
            operation="booking",
            pending_action="ENTER_OTP",
            checkpoint_data={"portal_url": "invalid://non_existent_page"},
            db_path=self.test_db_path,
        )

        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf["workflow_id"],
            user_confirmed_action=True,
            db_path=self.test_db_path,
        )

        self.assertIn(resumed["status"], ("HANDOVER_REQUIRED", "VALIDATION_FAILED"))
        self.assertTrue(resumed.get("handover_required", False) or resumed["status"] == "VALIDATION_FAILED")

    # -------------------------------------------------------------------------
    # TEST 16: NO OTP OR PASSWORD STORED IN SESSION RECORDS
    # -------------------------------------------------------------------------
    def test_16_no_otp_or_password_stored_in_session_records(self):
        """Verifies that sensitive credentials are systematically purged from checkpoint data."""
        sensitive_data = {
            "user_name": "Devotee",
            "pax": 2,
            "otp": "987654",
            "password": "SuperSecretPassword123!",
            "captcha_solution": "M7K9P",
            "card_number": "4111111111111234",
            "cvv": "123",
        }

        sanitized = session_store.sanitize_checkpoint_data(sensitive_data)
        self.assertNotIn("otp", sanitized)
        self.assertNotIn("password", sanitized)
        self.assertNotIn("captcha_solution", sanitized)
        self.assertNotIn("card_number", sanitized)
        self.assertNotIn("cvv", sanitized)
        self.assertEqual(sanitized["user_name"], "Devotee")

        # Persist and inspect raw SQLite string
        wf = session_store.create_user_workflow(
            session_id=self.session_id,
            state=session_store.WORKFLOW_STATE_OTP_REQUIRED,
            step="checkpoint",
            operation="booking",
            pending_action="ENTER_OTP",
            checkpoint_data=sensitive_data,
            db_path=self.test_db_path,
        )

        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT checkpoint_data_json FROM user_workflows WHERE workflow_id = ?", (wf["workflow_id"],))
            raw_json = cursor.fetchone()[0]

        self.assertNotIn("987654", raw_json)
        self.assertNotIn("SuperSecretPassword123!", raw_json)
        self.assertNotIn("4111111111111234", raw_json)

    # -------------------------------------------------------------------------
    # TEST 17: NO AUTOMATIC CAPTCHA SOLVING OCCURS
    # -------------------------------------------------------------------------
    def test_17_no_automatic_captcha_solving_occurs(self):
        """Verifies that the RPA automation never attempts to solve CAPTCHA autonomously without manual input."""
        paused = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            checkpoint_mode="CAPTCHA",
            headless=True,
            db_path=self.test_db_path,
        )
        wf_id = paused["workflow_id"]

        # Call resume with NO manual input and NO simulated clearance
        resumed = execute_user_controlled_booking_workflow(
            session_id=self.session_id,
            workflow_id=wf_id,
            user_confirmed_action=True,
            manual_input_value=None,
            simulate_manual_clearance=False,
            headless=True,
            db_path=self.test_db_path,
        )

        # Must fail state validation because automation cannot solve CAPTCHA on its own
        self.assertEqual(resumed["status"], "VALIDATION_FAILED")
        self.assertIn("has not been cleared in the portal", resumed["message"])

    # -------------------------------------------------------------------------
    # TEST 18: NO AUTOMATIC PAYMENT OR BOOKING RETRY OCCURS
    # -------------------------------------------------------------------------
    def test_18_no_automatic_payment_or_booking_retry_occurs(self):
        """Verifies that side-effect actions (like booking submissions) are never repeated on failure."""
        with patch("agents.rpa_agent.validate_booking_confirmation_state") as mock_validate:
            mock_validate.side_effect = rpa_agent.StateValidationError("Confirmation timed out.", operation="confirm")

            result = execute_playwright_mock_booking(
                user_name="Rajesh Gupta",
                pax_count=1,
                transport_text="Train",
                slot_text="Slot 1",
                total_price=500,
                headless=True,
            )

            # Ensure handover is triggered and side-effect is prevented
            self.assertTrue(result.get("handover_required", False))
            self.assertTrue(result.get("diagnostics", {}).get("side_effect_prevented", False))

    # -------------------------------------------------------------------------
    # TEST 19: EXISTING WEEK 5 AVAILABILITY TESTS PASS
    # -------------------------------------------------------------------------
    def test_19_existing_week5_availability_tests_pass(self):
        """Regression test: verifies that Week 5 slot availability extraction operates cleanly."""
        res = rpa_agent.check_yatra_slot_availability(
            requested_date="2026-10-20",
            category="VIP Darshan",
            headless=True,
            max_attempts=1,
        )
        self.assertEqual(res["status"].upper(), "SUCCESS")
        self.assertTrue(res["total_slots"] > 0)

    # -------------------------------------------------------------------------
    # TEST 20: EXISTING WEEK 6 ERROR-HANDLING TESTS PASS
    # -------------------------------------------------------------------------
    def test_20_existing_week6_error_handling_tests_pass(self):
        """Regression test: verifies that Week 6 retry, state validation, and handover logic remain intact."""
        attempts = []
        def flaky_action(attempt: int):
            attempts.append(attempt)
            if attempt < 2:
                raise rpa_agent.RecoverableRPAError("Transient slow load", operation="test")
            return "recovered"

        res = rpa_agent.retry_with_backoff(
            action_callable=flaky_action,
            operation_name="test_flaky",
            max_attempts=3,
            base_delay_seconds=0.01,
        )
        self.assertEqual(res, "recovered")
        self.assertEqual(len(attempts), 2)

    # -------------------------------------------------------------------------
    # TEST 21: EXISTING WEEK 7 LLM INTEGRATION TESTS PASS
    # -------------------------------------------------------------------------
    def test_21_existing_week7_llm_integration_tests_pass(self):
        """Regression test: verifies that Week 7 LangChain tool integration routes availability accurately."""
        from agents import orchestrator
        sess = session_store.get_session(self.session_id, db_path=self.test_db_path)
        res = orchestrator.handle_availability_query(
            user_text="Is VIP Darshan available on 2026-10-20?",
            session=sess,
        )
        self.assertIn("reply", res)
        self.assertIn("execution_mode", res)
        self.assertIn(res["execution_mode"], ("llm_tool_calling", "deterministic_fallback"))

    # -------------------------------------------------------------------------
    # TEST 22: EXISTING BOOKING AUTHORIZATION SAFEGUARDS REMAIN INTACT
    # -------------------------------------------------------------------------
    def test_22_existing_booking_authorization_safeguards_intact(self):
        """Regression test: verifies that booking and RPA execution require server-side human authorization."""
        # Attempt RPA execution without human authorization
        with patch("agents.session_store.DEFAULT_DB_PATH", self.test_db_path):
            resp = self.client.post("/api/yatra/rpa", json={
                "session_id": self.session_id,
                "user_name": "Test Pilgrim",
                "pax_count": 1,
                "transport_text": "Train",
                "slot_text": "Normal Darshan",
                "total_price": 0,
                "plan_version": 1,
                "human_authorized": False,
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "authorization_required")


if __name__ == "__main__":
    unittest.main()
