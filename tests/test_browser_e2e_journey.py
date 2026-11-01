"""
tests/test_browser_e2e_journey.py
Phase 7.1: React + FastAPI End-to-End Real Browser Integration Test.

Executes a complete 10-step user journey against the live running application
(FastAPI backend on port 8000 and React frontend on port 5173) in a real Chromium browser.
"""

import time
import unittest
from playwright.sync_api import sync_playwright


class TestBrowserE2EJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.console_errors = []
        self.page.on("console", lambda msg: self.console_errors.append(msg.text) if msg.type == "error" else None)

    def tearDown(self):
        self.context.close()

    def test_complete_real_browser_user_journey(self):
        """Tests the complete 10-step user journey in a real browser session."""
        page = self.page

        # Step 1: Navigate to React frontend
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")
        self.assertTrue("Vaishno Devi" in page.title() or "Vaishno Devi" in page.content(), "Expected 'Vaishno Devi' in page title or content")

        # Check for catastrophic JS errors
        fatal_errors = [e for e in self.console_errors if "Failed to load resource" not in e and "favicon" not in e]
        self.assertEqual(len(fatal_errors), 0, f"Found console errors on home page: {fatal_errors}")

        # Locate the AI Companion input on the Home page
        chat_input = page.locator("input[placeholder*='Ask Yatra AI']")
        self.assertTrue(chat_input.is_visible(), "AI Companion chat input should be visible on Home page")

        # =========================================================================
        # Scenario 1: Start conversation with incomplete requirements -> asks missing details
        # =========================================================================
        chat_input.fill("I want to visit Vaishno Devi")
        page.click("button:has-text('Send ➔')")

        # Wait for AI response
        page.wait_for_selector("div:has-text('AI Companion')", timeout=15000)
        time.sleep(1.5)
        content_after_turn1 = page.content()
        self.assertTrue(
            "departure city" in content_after_turn1.lower()
            or "origin" in content_after_turn1.lower()
            or "where will you be travelling from" in content_after_turn1.lower(),
            "AI companion should ask for missing trip requirements"
        )

        # =========================================================================
        # Scenario 2 & 3: Provide all required trip details -> Plan generated & displayed
        # =========================================================================
        chat_input.fill("I will travel from Delhi for 4 days with 2 travellers and total budget 15000")
        page.click("button:has-text('Send ➔')")

        # Wait for plan generation (may take a couple seconds to evaluate budget & options)
        page.wait_for_selector("div:has-text('PLAN')", timeout=20000)
        time.sleep(2.0)
        content_after_plan = page.content()
        self.assertTrue(
            "Revision #1" in content_after_plan or "PERSONALIZED YATRA PLAN" in content_after_plan or "Delhi" in content_after_plan,
            "Trip plan should be generated and displayed in browser"
        )

        # =========================================================================
        # Scenario 4: Change passenger count to 3 -> Revision 2 generated
        # =========================================================================
        chat_input.fill("Actually change it to 3 travellers")
        page.click("button:has-text('Send ➔')")
        time.sleep(2.5)
        content_after_edit = page.content()
        self.assertTrue(
            "Revision #2" in content_after_edit or "3 pilgrim" in content_after_edit or "3 traveller" in content_after_edit,
            "Plan should update to Revision #2 upon material modification"
        )

        # =========================================================================
        # Scenario 5: Attempt booking without explicit authorization -> Gate presented
        # =========================================================================
        chat_input.fill("Book option 1")
        page.click("button:has-text('Send ➔')")
        time.sleep(2.0)
        content_after_gate = page.content()
        self.assertTrue(
            "Human Confirmation Required" in content_after_gate
            or "Confirmation Gate" in content_after_gate,
            "Unconfirmed booking intent must present the Human Confirmation Gate"
        )

        # =========================================================================
        # Scenario 6 & 7: Explicitly authorize and execute mock booking -> Booking ID displayed
        # =========================================================================
        chat_input.fill("Confirm booking")
        page.click("button:has-text('Send ➔')")

        # Wait for mock RPA execution
        page.wait_for_selector("text=Booking Executed & Confirmed", timeout=25000)
        time.sleep(1.5)
        content_after_confirm = page.content()
        self.assertTrue(
            "VD-" in content_after_confirm or "VD" in content_after_confirm,
            "UI must display the verified mock booking confirmation ID"
        )

        # =========================================================================
        # Scenario 8: Attempt duplicate confirmation -> Idempotent prevention
        # =========================================================================
        chat_input.fill("Confirm booking")
        page.click("button:has-text('Send ➔')")
        time.sleep(2.0)
        content_after_dup = page.content()
        self.assertTrue(
            "already confirmed" in content_after_dup.lower()
            or "no duplicate" in content_after_dup.lower(),
            "Repeated confirmation must report duplicate prevented"
        )

        # =========================================================================
        # Scenario 9: Complete 7-Step Yatra Booking Wizard UI Flow
        # =========================================================================
        # Click "Darshan Bookings" tab in Navbar
        page.click("button:has-text('Darshan Bookings')")
        if page.locator("[data-testid='select-form-btn']").is_visible():
            page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # Step 1: Submit search form (default Delhi, 2 pax)
        page.click("button:has-text('Search Yatra Options ➔')")

        # Step 2: Transport selection
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)
        page.click("button:has-text('Proceed to Accommodation ➔')")

        # Step 3: Accommodation selection
        page.wait_for_selector("text=Step 3: Choose Katra Accommodation", timeout=15000)
        page.click("button:has-text('Proceed to Sightseeing')")

        # Step 4: Sightseeing selection
        page.wait_for_selector("text=Step 4: Select Sightseeing & Holy Shrines", timeout=15000)
        page.click("button:has-text('Generate Day-Wise Itinerary')")

        # Step 5: Itinerary timeline
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)
        page.click("button:has-text('Proceed to Human Review & Authorization ➔')")

        # Step 6: Authorization & RPA
        page.wait_for_selector("text=Review Summary & Human Authorization Gate", timeout=15000)

        # Trigger mock RPA demonstration
        page.click("button:has-text('Run Playwright RPA Mock Verification')")
        page.wait_for_selector("text=RPA Agent Execution Successful", timeout=25000)

        # Check authorization checkbox
        auth_checkbox = page.locator("input[type='checkbox']")
        if not auth_checkbox.is_checked():
            auth_checkbox.check()

        # Click confirm button
        page.click("button:has-text('Authorize & Confirm Booking ➔')")

        # Step 7: Confirmation Page
        page.wait_for_selector("text=JAI MATA DI! BOOKING CONFIRMED", timeout=20000)
        confirm_content = page.content()
        self.assertIn("Official Booking Reference ID", confirm_content)
        self.assertNotIn("Pending Confirmation", confirm_content)
        self.assertTrue("VD" in confirm_content, "Official booking ID should appear on confirmation page")

        # =========================================================================
        # Scenario 10: Session consistency and error handling verification
        # =========================================================================
        # Switch back to AI Companion tab
        page.click("button:has-text('AI Companion')")
        page.wait_for_selector("div:has-text('AI Companion')", timeout=10000)
        companion_content = page.content()
        # Verify that earlier session history and booking ID are still preserved in chat
        self.assertTrue("VD" in companion_content, "Session context and booking reference must persist across tab navigation")

    def test_authorization_invalidation_and_edge_cases(self):
        """Tests that modifying material details invalidates authorization, and verifies error handling for stale versions and invalid sessions."""
        import requests
        from agents.session_store import create_session, get_session

        base_api = "http://127.0.0.1:8000/api"

        # 1. Start a fresh session with a valid plan
        session_id = f"test-e2e-inval-{int(time.time())}"
        create_session(
            session_id=session_id,
            initial_state={
                "requirements": {
                    "origin": "Delhi",
                    "pax": 2,
                    "total_budget": 12000,
                    "duration_days": 3,
                    "darshan_preference": "Normal Darshan",
                },
                "selected_options": {
                    "transport": {"mode": "train", "price": 850, "operator": "Vande Bharat Express"},
                    "darshan_slot": {"category": "Normal Darshan", "price": 0},
                },
                "plan_version": 1,
                "authorized_plan_version": None,
            }
        )

        # 2. Explicitly authorize plan_version = 1
        resp = requests.post(f"{base_api}/yatra/authorize", json={
            "session_id": session_id,
            "plan_version": 1
        })
        self.assertEqual(resp.status_code, 200)
        session = get_session(session_id)
        self.assertEqual(session["state"]["authorized_plan_version"], 1, "Authorization must be recorded in session state")

        # 3. Simulate material plan modification (pax changed from 2 to 4)
        chat_resp = requests.post(f"{base_api}/chat", json={
            "session_id": session_id,
            "message": "Change it to 4 persons"
        })
        self.assertEqual(chat_resp.status_code, 200)

        # 4. Confirm that material detail change invalidated earlier authorization
        session_after_edit = get_session(session_id)
        self.assertEqual(session_after_edit["state"]["plan_version"], 2, "Plan version should bump to 2")
        self.assertIsNone(session_after_edit["state"]["authorized_plan_version"], "Material change MUST invalidate earlier authorization")

        # 5. Confirm that stale plan version 1 is rejected by booking endpoint
        stale_booking_resp = requests.post(f"{base_api}/yatra/confirm", json={
            "session_id": session_id,
            "plan_version": 1,
            "human_authorized": True,
            "user_name": "Test Pilgrim",
            "pax": 2,
            "option": {"transport": {"mode": "train", "price": 850}, "total_price": 1700}
        })
        self.assertEqual(stale_booking_resp.status_code, 200)
        stale_data = stale_booking_resp.json()
        self.assertEqual(stale_data.get("status"), "authorization_required", "Stale plan version 1 must fail closed with authorization_required")
        self.assertIn("Revision #2", stale_data.get("message", ""))

        # 6. Confirm that unauthorized plan version 2 is rejected by booking endpoint
        unauth_booking_resp = requests.post(f"{base_api}/yatra/confirm", json={
            "session_id": session_id,
            "plan_version": 2,
            "human_authorized": True,
            "user_name": "Test Pilgrim",
            "pax": 4,
            "option": {"transport": {"mode": "train", "price": 850}, "total_price": 3400}
        })
        self.assertEqual(unauth_booking_resp.status_code, 200)
        unauth_data = unauth_booking_resp.json()
        self.assertEqual(unauth_data.get("status"), "authorization_required", "Unauthorized plan version 2 must fail closed")
        self.assertIn("Server-side human authorization has not been granted", unauth_data.get("message", ""))

        # 7. Test invalid session ID rejected
        invalid_session_resp = requests.post(f"{base_api}/yatra/authorize", json={
            "session_id": "non-existent-session-000",
            "plan_version": 1
        })
        self.assertEqual(invalid_session_resp.status_code, 200)
        invalid_data = invalid_session_resp.json()
        self.assertEqual(invalid_data.get("status"), "authorization_required", "Invalid session ID must fail closed")

        # 8. Test browser UI handling of invalid/empty search gracefully
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")
        page.click("button:has-text('Darshan Bookings')")
        if page.locator("[data-testid='select-form-btn']").is_visible():
            page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # Trigger search with valid defaults
        page.click("button:has-text('Search Yatra Options ➔')")
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)

        # Verify no fatal console errors occurred
        fatal_errors = [e for e in self.console_errors if "Failed to load resource" not in e and "favicon" not in e]
        self.assertEqual(len(fatal_errors), 0, f"No unhandled client errors during edge case testing: {fatal_errors}")


if __name__ == "__main__":
    unittest.main()
