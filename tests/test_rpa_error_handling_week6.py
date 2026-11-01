"""
tests/test_rpa_error_handling_week6.py
Comprehensive automated test suite for Week 6 Assignment:
RPA Error Handling and Retry Strategy

Covers all 14 required evaluation scenarios:
1. A recoverable timeout succeeds on a later attempt.
2. All retry attempts fail and the operation escalates.
3. A non-recoverable error is not retried.
4. State validation succeeds when the expected state is present.
5. State validation detects a missing required selector.
6. A valid empty availability result is not misclassified as a structural error.
7. A changed page structure triggers handover.
8. Malformed extracted data triggers an appropriate failure or handover.
9. Browser cleanup happens after success and failure.
10. Screenshot failure does not hide the original exception.
11. Retry limits prevent infinite loops.
12. The Week 4 booking workflow remains functional.
13. The Week 5 availability extraction workflow remains functional.
14. Booking authorization and plan-version safeguards remain intact.
"""

import os
import sys
import io
import time
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from backend.main import app
import agents.rpa_agent as rpa_agent
from agents.rpa_agent import (
    RPAError,
    RecoverableRPAError,
    NonRecoverableRPAError,
    StructuralPageChangeError,
    DataIntegrityError,
    StateValidationError,
    validate_portal_loaded,
    validate_calendar_tab_active,
    validate_date_input_state,
    validate_category_filter_state,
    validate_calendar_readiness,
    validate_slot_record_integrity,
    validate_booking_form_state,
    validate_booking_confirmation_state,
    retry_with_backoff,
    create_handover_result,
    generate_mock_portal_html,
    navigate_to_availability_calendar,
    extract_slot_availability,
    check_yatra_slot_availability,
    execute_playwright_mock_booking,
    DEFAULT_MOCK_SLOTS,
)
from agents import session_store

# Ensure UTF-8 output encoding on Windows consoles safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


class TestRPAErrorHandlingWeek6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.temp_dir = tempfile.gettempdir()

    # =========================================================================
    # 1. A recoverable timeout succeeds on a later attempt
    # =========================================================================
    def test_01_recoverable_timeout_succeeds_on_later_attempt(self):
        """Verifies retry-and-escalate catches recoverable timeout and succeeds on attempt 2."""
        call_count = 0
        logs = []

        def simulated_action(attempt_number):
            nonlocal call_count
            call_count += 1
            if attempt_number == 1:
                raise PlaywrightTimeoutError("Simulated transient page rendering timeout on attempt 1")
            return {"status": "SUCCESS", "extracted_slots": 5}

        result = retry_with_backoff(
            action_callable=simulated_action,
            operation_name="test_transient_action",
            max_attempts=3,
            base_delay_seconds=0.05,
            logs=logs
        )

        self.assertEqual(call_count, 2)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["extracted_slots"], 5)
        self.assertTrue(any("Retrying in" in log for log in logs))
        self.assertTrue(any("attempt 1/3" in log for log in logs))

    # =========================================================================
    # 2. All retry attempts fail and the operation escalates
    # =========================================================================
    def test_02_all_retry_attempts_fail_and_operation_escalates(self):
        """Verifies persistent recoverable failure attempts max_attempts times and escalates."""
        call_count = 0
        logs = []

        def failing_action(attempt_number):
            nonlocal call_count
            call_count += 1
            raise PlaywrightTimeoutError(f"Persistent timeout on attempt {attempt_number}")

        with self.assertRaises(RecoverableRPAError) as ctx:
            retry_with_backoff(
                action_callable=failing_action,
                operation_name="test_persistent_failing_action",
                max_attempts=3,
                base_delay_seconds=0.05,
                logs=logs
            )

        self.assertEqual(call_count, 3)
        self.assertIn("Exhausted 3 attempts", str(ctx.exception))
        self.assertTrue(any("[ESCALATE] Maximum retry attempts" in log for log in logs))

        # Test escalation into structured handover
        handover = create_handover_result(
            error=ctx.exception,
            failed_operation="test_persistent_failing_action",
            attempt_count=call_count,
            logs=logs
        )
        self.assertEqual(handover["status"], "HANDOVER_REQUIRED")
        self.assertTrue(handover["handover_required"])
        self.assertFalse(handover["retryable"])
        self.assertEqual(handover["error_category"], "RETRY_EXHAUSTED")
        self.assertEqual(handover["attempt_count"], 3)

    # =========================================================================
    # 3. A non-recoverable error is not retried
    # =========================================================================
    def test_03_non_recoverable_error_is_not_retried(self):
        """Verifies non-recoverable error terminates immediately without retrying."""
        call_count = 0
        logs = []

        def structural_failing_action(attempt_number):
            nonlocal call_count
            call_count += 1
            raise StructuralPageChangeError(
                "Critical DOM node #slotsContainer missing",
                operation="test_structural",
                selector="#slotsContainer"
            )

        with self.assertRaises(StructuralPageChangeError):
            retry_with_backoff(
                action_callable=structural_failing_action,
                operation_name="test_structural_failing_action",
                max_attempts=3,
                base_delay_seconds=0.05,
                logs=logs
            )

        self.assertEqual(call_count, 1)
        self.assertTrue(any("[NON_RECOVERABLE]" in log for log in logs))
        self.assertFalse(any("[RETRY]" in log for log in logs))

    # =========================================================================
    # 4. State validation succeeds when expected state is present
    # =========================================================================
    def test_04_state_validation_succeeds_when_expected_state_present(self):
        """Verifies state validation helpers succeed against valid portal DOM."""
        portal_html = generate_mock_portal_html(render_delay_ms=50)
        html_path = os.path.join(self.temp_dir, "test_valid_portal.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(portal_html)

        html_url = f"file:///{html_path.replace(os.sep, '/')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(html_url)

                # 1. Validate portal loaded
                self.assertTrue(validate_portal_loaded(page))

                # 2. Switch tab and validate calendar tab active
                page.locator("#tabCalendar").click()
                self.assertTrue(validate_calendar_tab_active(page))

                # 3. Validate date input state
                page.locator("#calendarDate").fill("2026-10-21")
                self.assertTrue(validate_date_input_state(page, "2026-10-21"))

                # 4. Validate category filter state
                page.locator("#slotCategoryFilter").select_option(value="VIP Darshan")
                self.assertTrue(validate_category_filter_state(page, "VIP Darshan"))

                # 5. Trigger search and validate readiness
                page.locator("#btnCheckAvailability").click()
                readiness = validate_calendar_readiness(page, timeout_ms=3000)
                self.assertEqual(readiness, "SLOTS_FOUND")
            finally:
                browser.close()

    # =========================================================================
    # 5. State validation detects missing required selector
    # =========================================================================
    def test_05_state_validation_detects_missing_required_selector(self):
        """Verifies that state validation raises StructuralPageChangeError when a required selector is missing."""
        corrupted_html = "<html><body><div id='brokenPortal'>No navigation or cards</div></body></html>"
        html_path = os.path.join(self.temp_dir, "test_corrupted_portal.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(corrupted_html)

        html_url = f"file:///{html_path.replace(os.sep, '/')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(html_url)

                with self.assertRaises(StructuralPageChangeError) as ctx:
                    validate_portal_loaded(page)

                self.assertIn(".card", str(ctx.exception))
                self.assertEqual(ctx.exception.selector, ".card")
            finally:
                browser.close()

    # =========================================================================
    # 6. Valid empty availability result is not misclassified as structural error
    # =========================================================================
    def test_06_valid_empty_availability_result_not_misclassified_as_structural_error(self):
        """Verifies that an empty availability day returns SUCCESS with is_empty=True, not an error."""
        result = check_yatra_slot_availability(
            requested_date="2026-10-25",  # Date with no slots in DEFAULT_MOCK_SLOTS
            headless=True
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertTrue(result["is_empty"])
        self.assertEqual(result["total_slots"], 0)
        self.assertEqual(len(result["slots"]), 0)
        self.assertFalse(result["handover_required"])

    # =========================================================================
    # 7. Changed page structure triggers handover
    # =========================================================================
    def test_07_changed_page_structure_triggers_handover(self):
        """Verifies that missing calendar section in DOM triggers immediate pause-and-handover."""
        # Create HTML where calendar section is removed
        modified_html = generate_mock_portal_html()
        modified_html = modified_html.replace('id="calendarSection"', 'id="calendarSection_REMOVED_BY_REDESIGN"')

        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True,
            portal_html=modified_html,
            enable_retry=True,
            max_attempts=2
        )

        self.assertEqual(result["status"], "HANDOVER_REQUIRED")
        self.assertTrue(result["handover_required"])
        self.assertFalse(result["retryable"])
        self.assertEqual(result["error_category"], "STRUCTURAL_CHANGE")
        self.assertEqual(result["failed_operation"], "check_yatra_slot_availability")
        self.assertIn("Human intervention required", result["message"])
        self.assertTrue(any("closed cleanly" in log for log in result["logs"]))

    # =========================================================================
    # 8. Malformed extracted data triggers handover
    # =========================================================================
    def test_08_malformed_extracted_data_triggers_handover(self):
        """Verifies that negative capacity or malformed slot records trigger DataIntegrityError and handover."""
        # 1. Direct validation unit test
        corrupt_slot = {
            "slot_id": "SLOT-999",
            "yatra_date": "2026-10-20",
            "availability_status": "available",
            "remaining_capacity": -10,  # Negative capacity is invalid!
            "price": 0.0
        }
        with self.assertRaises(DataIntegrityError):
            validate_slot_record_integrity(corrupt_slot)

        # 2. End-to-end workflow test with corrupted slot data
        corrupt_slots = [
            {"id": 999, "slot_date": "2026-10-20", "slot_time": "06:00", "session": "Morning", "category": "Normal Darshan", "price": 0, "seats_available": -50, "status": "available"}
        ]
        corrupt_html = generate_mock_portal_html(slots_data=corrupt_slots, render_delay_ms=50)

        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True,
            portal_html=corrupt_html
        )

        self.assertEqual(result["status"], "HANDOVER_REQUIRED")
        self.assertTrue(result["handover_required"])
        self.assertEqual(result["error_category"], "DATA_INTEGRITY_VIOLATION")
        self.assertIn("Negative remaining capacity", result["error"])

    # =========================================================================
    # 9. Browser cleanup happens after success and failure
    # =========================================================================
    def test_09_browser_cleanup_happens_after_success_and_failure(self):
        """Verifies Playwright browser instance is closed cleanly in both success and failure states."""
        # Case A: Success
        res_success = check_yatra_slot_availability(requested_date="2026-10-20", headless=True)
        self.assertEqual(res_success["status"], "SUCCESS")
        self.assertTrue(any("Playwright browser instance closed cleanly" in log for log in res_success["logs"]))

        # Case B: Failure (broken DOM)
        broken_html = "<html><body>Broken DOM</body></html>"
        res_failure = check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True,
            portal_html=broken_html,
            max_attempts=1
        )
        self.assertEqual(res_failure["status"], "HANDOVER_REQUIRED")
        self.assertTrue(any("Playwright browser instance closed cleanly" in log for log in res_failure["logs"]))

    # =========================================================================
    # 10. Screenshot failure does not hide original exception
    # =========================================================================
    def test_10_screenshot_failure_does_not_hide_original_exception(self):
        """Verifies that an unexpected exception during screenshot capture does not mask the primary error."""
        primary_error = StructuralPageChangeError("Primary structural failure in navigation", selector="#tabCalendar")
        mock_page = MagicMock()
        mock_page.screenshot.side_effect = IOError("Simulated disk write failure for screenshot")

        logs = []
        handover = create_handover_result(
            error=primary_error,
            failed_operation="test_op",
            attempt_count=1,
            page=mock_page,
            screenshot_path="C:/fake/path.png",
            logs=logs
        )

        self.assertEqual(handover["status"], "HANDOVER_REQUIRED")
        self.assertEqual(handover["error_category"], "STRUCTURAL_CHANGE")
        self.assertIn("Primary structural failure in navigation", handover["message"])
        self.assertIn("screenshot_capture_error", handover["diagnostics"])
        self.assertIn("Simulated disk write failure", handover["diagnostics"]["screenshot_capture_error"])
        self.assertTrue(any("Screenshot capture failed" in log for log in logs))

    # =========================================================================
    # 11. Retry limits prevent infinite loops
    # =========================================================================
    def test_11_retry_limits_prevent_infinite_loops(self):
        """Verifies retry_with_backoff strictly limits executions to max_attempts."""
        invocations = []

        def infinite_attempt_action(attempt):
            invocations.append(attempt)
            raise PlaywrightTimeoutError(f"Attempt {attempt} timed out")

        with self.assertRaises(RecoverableRPAError):
            retry_with_backoff(
                action_callable=infinite_attempt_action,
                operation_name="loop_check",
                max_attempts=4,
                base_delay_seconds=0.01,
                backoff_multiplier=1.5
            )

        self.assertEqual(invocations, [1, 2, 3, 4])
        self.assertEqual(len(invocations), 4)

    # =========================================================================
    # 12. Week 4 booking workflow remains functional
    # =========================================================================
    def test_12_week4_booking_workflow_remains_functional(self):
        """Verifies execute_playwright_mock_booking works with state validation and side-effect protection."""
        booking_result = execute_playwright_mock_booking(
            user_name="Pooja Verma",
            pax_count=2,
            transport_text="Helicopter (Katra to Sanjichhat)",
            slot_text="2026-10-20: Morning VIP Aarti",
            total_price=9280.0,
            headless=True
        )

        self.assertEqual(booking_result["status"], "SUCCESS")
        self.assertIsNotNone(booking_result["booking_id"])
        self.assertTrue(str(booking_result["booking_id"]).startswith("VD-RPA-"))
        self.assertFalse(booking_result.get("handover_required", False))
        self.assertTrue(any("Validated booking form readiness" in log for log in booking_result["logs"]))
        self.assertTrue(any("Validated booking confirmation state" in log for log in booking_result["logs"]))

    # =========================================================================
    # 13. Week 5 availability extraction workflow remains functional
    # =========================================================================
    def test_13_week5_availability_extraction_remains_functional(self):
        """Verifies check_yatra_slot_availability continues extracting structured slot data."""
        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertFalse(result["handover_required"])
        self.assertGreaterEqual(result["total_slots"], 7)
        self.assertGreater(result["available_count"], 0)
        self.assertGreater(result["full_count"], 0)

        # Confirm all slot records are well-formed
        for s in result["slots"]:
            self.assertIn(s["availability_status"], ["available", "full", "unavailable"])
            self.assertGreaterEqual(s["price"], 0.0)
            if s["remaining_capacity"] is not None:
                self.assertGreaterEqual(s["remaining_capacity"], 0)

    # =========================================================================
    # 14. Booking authorization and plan-version safeguards remain intact
    # =========================================================================
    def test_14_booking_authorization_and_plan_version_safeguards_intact(self):
        """Verifies availability check is read-only and preserves session state and authorization gates."""
        session_id = f"test-safe-session-{int(time.time())}"
        session_store.init_db()
        session_store.create_session(
            session_id=session_id,
            initial_state={
                "plan_version": 1,
                "authorized": False,
                "itinerary": {"destination": "Vaishno Devi"}
            }
        )

        # Call availability checking endpoint
        response = self.client.post(
            "/api/yatra/rpa/availability",
            json={"date": "2026-10-20", "category": "VIP Darshan", "headless": True, "max_attempts": 2}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertFalse(data.get("handover_required", False))

        # Check session was completely untouched
        loaded = session_store.get_session(session_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.get("plan_version", 1), 1)
        self.assertFalse(loaded.get("authorized", False))
        self.assertNotIn("rpa_execution", loaded)


if __name__ == "__main__":
    unittest.main()
