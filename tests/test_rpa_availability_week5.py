"""
tests/test_rpa_availability_week5.py
Focused automated test suite for Week 5 Assignment:
RPA Workflow: Availability Checking and Data Extraction

Covers all 10 required evaluation scenarios:
1. Successful navigation to the availability calendar.
2. Successful extraction of multiple slots.
3. Available, full, and unavailable statuses.
4. A requested date with no available slots.
5. An empty calendar.
6. Delayed rendering of calendar elements (explicit waits).
7. A missing calendar element or timeout (error handling).
8. Malformed or incomplete slot data (resilience).
9. Browser cleanup after success and failure.
10. Regression of the existing booking and authorization workflow.
"""

import os
import sys
import io
import json
import tempfile
import unittest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.main import app
import agents.rpa_agent as rpa_agent
from agents.rpa_agent import (
    generate_mock_portal_html,
    navigate_to_availability_calendar,
    extract_slot_availability,
    check_yatra_slot_availability,
    execute_playwright_mock_booking,
    DEFAULT_MOCK_SLOTS,
)

# Ensure UTF-8 output encoding on Windows consoles safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


class TestRPAAvailabilityWeek5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.temp_dir = tempfile.gettempdir()

    # =========================================================================
    # 1. Successful navigation to the availability calendar
    # =========================================================================
    def test_01_successful_navigation_to_availability_calendar(self):
        """Verifies Playwright navigates to the availability calendar using locators and explicit waits."""
        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            category="Normal Darshan",
            headless=True
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("Navigating to mock portal", " ".join(result["logs"]))
        self.assertIn("Waiting for availability calendar tab locator", " ".join(result["logs"]))
        self.assertIn("Waiting for calendar section to become visible", " ".join(result["logs"]))
        self.assertIn("Availability calendar navigation completed successfully.", " ".join(result["logs"]))

    # =========================================================================
    # 2. Successful extraction of multiple slots
    # =========================================================================
    def test_02_successful_extraction_of_multiple_slots(self):
        """Verifies structured extraction captures all required fields for each slot."""
        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreaterEqual(result["total_slots"], 7)
        self.assertEqual(len(result["slots"]), result["total_slots"])

        for slot in result["slots"]:
            self.assertIn("slot_id", slot)
            self.assertTrue(str(slot["slot_id"]).startswith("SLOT-") or str(slot["slot_id"]).isdigit())
            self.assertEqual(slot["yatra_date"], "2026-10-20")
            self.assertIn("slot_name", slot)
            self.assertIn("time", slot)
            self.assertIn("session", slot)
            self.assertIn(slot["availability_status"], ["available", "full", "unavailable"])
            self.assertIn("price", slot)
            self.assertIsInstance(slot["price"], float)
            self.assertIn("retrieved_at", slot)

    # =========================================================================
    # 3. Available, full, and unavailable statuses
    # =========================================================================
    def test_03_available_full_and_unavailable_statuses(self):
        """Verifies mapping of portal slot statuses into available, full, and unavailable categories."""
        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreater(result["available_count"], 0)
        self.assertGreater(result["full_count"], 0)
        self.assertGreater(result["unavailable_count"], 0)

        statuses_found = {s["availability_status"] for s in result["slots"]}
        self.assertIn("available", statuses_found)
        self.assertIn("full", statuses_found)
        self.assertIn("unavailable", statuses_found)

        # Verify capacity associations
        for s in result["slots"]:
            if s["availability_status"] == "available":
                self.assertIsNotNone(s["remaining_capacity"])
                self.assertGreater(s["remaining_capacity"], 0)
            elif s["availability_status"] == "full":
                self.assertEqual(s["remaining_capacity"], 0)

    # =========================================================================
    # 4. A requested date with no available slots
    # =========================================================================
    def test_04_requested_date_with_no_available_slots(self):
        """Verifies behavior when slots exist on a date but all are booked/full."""
        fully_booked_slots = [
            {"id": 401, "slot_date": "2026-10-28", "slot_time": "06:00", "session": "Morning Aarti", "category": "Normal Darshan", "price": 0, "seats_available": 0, "status": "full"},
            {"id": 402, "slot_date": "2026-10-28", "slot_time": "12:00", "session": "Afternoon", "category": "Normal Darshan", "price": 0, "seats_available": 0, "status": "full"},
            {"id": 403, "slot_date": "2026-10-28", "slot_time": "09:00", "session": "VIP", "category": "VIP Darshan", "price": 500, "seats_available": 0, "status": "full"},
        ]
        portal_html = generate_mock_portal_html(slots_data=fully_booked_slots)
        result = check_yatra_slot_availability(
            requested_date="2026-10-28",
            portal_html=portal_html,
            headless=True
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_slots"], 3)
        self.assertEqual(result["available_count"], 0)
        self.assertEqual(result["full_count"], 3)
        self.assertEqual(result["is_empty"], False)

    # =========================================================================
    # 5. An empty calendar
    # =========================================================================
    def test_05_empty_calendar(self):
        """Verifies handling when zero slots exist for a requested date."""
        result = check_yatra_slot_availability(
            requested_date="2026-11-30",  # Out of range date
            headless=True
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_slots"], 0)
        self.assertEqual(result["slots"], [])
        self.assertTrue(result["is_empty"])

    # =========================================================================
    # 6. Delayed rendering of calendar elements
    # =========================================================================
    def test_06_delayed_rendering_of_calendar_elements(self):
        """Verifies explicit wait synchronization when the portal simulates high rendering delay."""
        # 600ms artificial network / rendering delay in HTML
        delayed_html = generate_mock_portal_html(render_delay_ms=600)
        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            portal_html=delayed_html,
            headless=True,
            timeout_ms=10000
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreaterEqual(result["total_slots"], 7)
        self.assertIn("Waiting for dynamic loading indicator", " ".join(result["logs"]))

    # =========================================================================
    # 7. A missing calendar element or timeout
    # =========================================================================
    def test_07_missing_calendar_element_or_timeout(self):
        """Verifies graceful error handling and timeout reporting when critical calendar elements are absent."""
        # Generate defective HTML missing the check availability button
        broken_html = generate_mock_portal_html().replace('id="btnCheckAvailability"', 'id="missingBtn"')
        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            portal_html=broken_html,
            headless=True,
            timeout_ms=1500  # Short timeout for quick failure
        )
        self.assertIn(result["status"], ["TIMEOUT", "ERROR", "HANDOVER_REQUIRED"])
        self.assertIn("error", result)
        self.assertIsNotNone(result["error"])

    # =========================================================================
    # 8. Malformed or incomplete slot data
    # =========================================================================
    def test_08_malformed_or_incomplete_slot_data(self):
        """Verifies extraction resilience when slot elements have missing or non-numeric attributes."""
        malformed_slots = [
            # Missing capacity, non-numeric price, missing session
            {"id": 999, "slot_date": "2026-10-20", "slot_time": "10:00", "session": "", "category": "Special Aarti", "price": "free", "seats_available": "unknown", "status": "AVAILABLE_NOW"},
        ]
        portal_html = generate_mock_portal_html(slots_data=malformed_slots)
        result = check_yatra_slot_availability(
            requested_date="2026-10-20",
            portal_html=portal_html,
            headless=True
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_slots"], 1)
        slot = result["slots"][0]
        self.assertEqual(slot["availability_status"], "available")
        self.assertIsNone(slot["remaining_capacity"])
        self.assertEqual(slot["price"], 0.0)

    # =========================================================================
    # 9. Browser cleanup after success and failure
    # =========================================================================
    def test_09_browser_cleanup_after_success_and_failure(self):
        """Verifies browser resources are closed cleanly in both successful runs and failure cases."""
        # Success run cleanup check
        success_res = check_yatra_slot_availability(requested_date="2026-10-20", headless=True)
        self.assertIn("Playwright browser instance closed cleanly.", success_res["logs"])

        # Failure run cleanup check (invalid HTML file path)
        broken_html = generate_mock_portal_html().replace('id="tabCalendar"', 'id="corruptTab"')
        fail_res = check_yatra_slot_availability(portal_html=broken_html, timeout_ms=1200, headless=True)
        self.assertIn("Playwright browser instance closed cleanly.", fail_res["logs"])

    # =========================================================================
    # 10. Regression of existing booking and authorization workflow
    # =========================================================================
    def test_10_regression_existing_booking_and_authorization_workflow(self):
        """Verifies existing Week 4 booking checkout execution and FastAPI availability route remain 100% operational."""
        # 1. Existing Week 4 Playwright booking test
        booking_res = execute_playwright_mock_booking(
            user_name="Pragati",
            pax_count=2,
            transport_text="Vande Bharat Express (Train)",
            slot_text="Normal Darshan (06:00)",
            total_price=2474.0,
            headless=True
        )
        self.assertEqual(booking_res["status"], "SUCCESS")
        self.assertTrue(str(booking_res["booking_id"]).startswith("VD-RPA-"))
        self.assertIsNotNone(booking_res["screenshot_path"])
        self.assertTrue(os.path.exists(booking_res["screenshot_path"]))

        # 2. FastAPI endpoint test for Week 5 availability
        resp = self.client.post("/api/yatra/rpa/availability", json={
            "date": "2026-10-20",
            "category": "VIP Darshan",
            "headless": True
        })
        self.assertEqual(resp.status_code, 200)
        api_data = resp.json()
        self.assertEqual(api_data["status"], "SUCCESS")
        self.assertEqual(api_data["category_filter"], "VIP Darshan")
        self.assertGreater(api_data["total_slots"], 0)


if __name__ == "__main__":
    unittest.main()
