"""
tests/test_browser_flexible_workflow.py
Playwright Real-Browser Test for the Preference-Driven Recommendation and Confirmation Flow:
- Submitting intake preferences automatically produces complete recommendations on "Your Recommended Yatra" page.
- All selected options appear together: Transport, Accommodation, Darshan slot, Itinerary, and Itemised Budget.
- Confirmation prompt: "Are you happy with these selections, or would you like to change anything before proceeding?"
- Path B: "Change My Selections" allows editing specific categories and returning directly to the summary.
- Path A: "Confirm Selections & Continue" proceeds to Final Booking Review & Human Authorization Gate.
- Explicit human authorization gate before Playwright Mock RPA execution and final confirmation.
"""

import time
import unittest
from playwright.sync_api import sync_playwright


class TestBrowserFlexibleWorkflow(unittest.TestCase):
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

    def test_recommendation_first_workflow_in_browser(self):
        page = self.page

        # 1. Navigate to React App and open Yatra Planner
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")
        page.click("button:has-text('Plan Your Yatra')")

        # 2. Choice Screen: Click "Plan with a Form"
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # 3. Fill form preferences: Delhi, mode Train, 2 Pax, 4 Days, 15000 budget
        page.select_option("#travel-origin", "Delhi")
        page.select_option("#travel-mode", "train")

        # 4. Click Search: Must NOT take user through sequential wizard by default
        page.click("button:has-text('Search Yatra Options ➔')")

        # 5. Verify immediate consolidated "Your Recommended Yatra" page
        page.wait_for_selector("[data-testid='recommended-yatra-page']", timeout=20000)
        time.sleep(1)

        body_text = page.inner_text("body")
        self.assertIn("Your Recommended Yatra Package", body_text)
        self.assertIn("AI Recommended Package", body_text)

        # Verify all selected options are displayed together on this page
        # 1. Overview
        self.assertIn("Pilgrimage Overview", body_text)
        self.assertIn("Delhi", body_text)
        self.assertIn("Katra & Bhawan", body_text)
        self.assertIn("2 Pilgrims", body_text)

        # 2. Transport
        self.assertTrue("Indian Railways" in body_text or "TRAIN" in body_text)
        self.assertIn("Transport Fare", body_text)

        # 3. Darshan Slot
        self.assertIn("DARSHAN", body_text)
        self.assertIn("Shrine Verified", body_text)

        # 4. Accommodation
        self.assertIn("HOTEL", body_text)
        self.assertIn("Hotel Total", body_text)

        # 5. Itinerary
        self.assertIn("Day-by-Day Sacred Itinerary", body_text)
        self.assertIn("Pacing Note", body_text)

        # 6. Itemised Budget
        self.assertIn("Itemised Budget Breakdown", body_text)
        self.assertTrue("Grand Group Total" in body_text or "GRAND GROUP TOTAL" in body_text)
        self.assertTrue("Cost Per Pilgrim" in body_text or "COST PER PILGRIM" in body_text)

        # 6. Verify confirmation prompt and actions
        self.assertIn("Are you happy with these selections, or would you like to change anything before proceeding?", body_text)
        self.assertTrue(page.locator("[data-testid='confirm-selections-continue-btn']").is_visible())
        self.assertTrue(page.locator("[data-testid='change-my-selections-btn']").is_visible())

        # 7. Test Path B: "Change My Selections"
        page.click("[data-testid='change-my-selections-btn']")
        time.sleep(0.5)

        # Verify drawer contains editable categories
        self.assertTrue(page.locator("[data-testid='edit-cat-transport']").is_visible())
        self.assertTrue(page.locator("[data-testid='edit-cat-accommodation']").is_visible())
        self.assertTrue(page.locator("[data-testid='edit-cat-sightseeing']").is_visible())

        # Click Transport category to change selection
        page.click("[data-testid='edit-cat-transport']")
        time.sleep(1)

        # Verify user is on Transport customization view
        page.wait_for_selector("text=Customize Travel & Darshan Option", timeout=10000)
        self.assertTrue(page.locator("[data-testid='return-to-recommended-yatra-btn']").is_visible())

        # Return to Recommended Yatra without restarting or visiting other sections
        page.click("[data-testid='return-to-recommended-yatra-btn']")
        page.wait_for_selector("[data-testid='recommended-yatra-page']", timeout=10000)
        time.sleep(0.5)

        # 8. Test Path A: "Confirm Selections & Continue"
        page.click("[data-testid='confirm-selections-continue-btn']")
        time.sleep(1)

        # 9. Verify Final Booking Review & Human Authorization Gate
        page.wait_for_selector("text=Review Summary & Human Authorization Gate", timeout=15000)
        review_content = page.content()
        self.assertIn("Plan Revision #", review_content)
        self.assertIn("Human Authorization Gate", review_content)

        # 10. Run Playwright RPA Mock Verification demo
        page.wait_for_selector("button:has-text('Run Playwright RPA Mock Verification')", timeout=10000)
        page.click("button:has-text('Run Playwright RPA Mock Verification')")

        # Wait for RPA execution
        page.wait_for_selector("text=RPA Agent Execution Successful", timeout=20000)

        # 11. Authorize and Confirm Booking
        page.click("button:has-text('Authorize & Confirm Booking ➔')")
        page.wait_for_selector("text=JAI MATA DI! BOOKING CONFIRMED", timeout=15000)

        final_content = page.content()
        self.assertIn("VD", final_content)
        self.assertIn("Official Booking Reference ID", final_content)
        self.assertIn("DEMO AUTOMATION", final_content)


if __name__ == "__main__":
    unittest.main()
