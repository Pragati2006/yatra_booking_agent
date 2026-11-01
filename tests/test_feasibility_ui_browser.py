import time
import unittest
from playwright.sync_api import sync_playwright

class TestSightseeingFeasibilityUI(unittest.TestCase):
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

    def tearDown(self):
        self.context.close()

    def test_all_feasibility_ui_scenarios(self):
        page = self.page

        print("\n--- Testing Scenario 1 & 2: Feasible + Infeasible Sightseeing on 3-day trip ---")
        # Navigate to home and start booking wizard
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Start Darshan Planning from navbar
        page.click("button:has-text('Plan Your Yatra Now ➔')")
        if page.locator("[data-testid='select-form-btn']").is_visible():
            page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # Set 3-day duration
        duration_select = page.locator("label:has-text('Trip Duration') + select")
        duration_select.select_option("3")
        page.click("button:has-text('Search Yatra Options ➔')")

        # Step 2: Select Transport
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)
        page.click("button:has-text('Proceed to Accommodation ➔')")

        # Step 3: Choose or skip hotel
        page.wait_for_selector("text=Step 3: Choose Katra Accommodation", timeout=15000)
        page.click("button:has-text('Skip Hotel')")

        # Step 4: Sightseeing selection (All 29 destinations)
        page.wait_for_selector("text=Step 4: Select Sightseeing & Holy Shrines", timeout=15000)

        # Select Bhairavnath Temple (trek route -> feasible)
        bhairav_card = page.locator("div.card:has-text('Bhairavnath Temple')").first
        bhairav_card.locator("button:has-text('+ Add Place')").click()

        # Select Patnitop (distant excursion -> infeasible on 3-day trip)
        patnitop_card = page.locator("div.card:has-text('Patnitop')").first
        patnitop_card.locator("button:has-text('+ Add Place')").click()

        # Click Generate Day-Wise Itinerary
        page.click("button:has-text('Generate Day-Wise Itinerary')")

        # Step 5: Timeline Itinerary with Feasibility Advisory
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Check Feasible Advisory is displayed
        feasible_advisory = page.locator("[data-testid='feasible-advisory']")
        self.assertTrue(feasible_advisory.is_visible(), "Feasible advisory banner should be visible")
        feasible_text = feasible_advisory.text_content()
        self.assertIn("Bhairavnath Temple", feasible_text, "Bhairavnath Temple should be identified as feasible")
        print("  PASS: Feasible destination (Bhairavnath Temple) displayed with badge.")

        # Check Infeasible Advisory is displayed with reason & suggestion
        infeasible_advisory = page.locator("[data-testid='infeasible-advisory']")
        self.assertTrue(infeasible_advisory.is_visible(), "Infeasible advisory banner should be visible")
        infeasible_text = infeasible_advisory.text_content()
        self.assertIn("Patnitop", infeasible_text, "Patnitop should be listed in infeasible advisory")
        self.assertIn("Reason:", infeasible_text, "Backend-provided reason should be visible")
        self.assertIn("Suggestion:", infeasible_text, "Backend-provided suggestion should be visible")
        print("  PASS: Infeasible destination (Patnitop) displays place, reason, and suggestion.")

        print("\n--- Testing Scenario 3: Replanning Replaces Stale Advisory Data ---")
        # Click Back to Sightseeing
        page.click("button:has-text('← Back to Sightseeing')")
        page.wait_for_selector("text=Step 4: Select Sightseeing & Holy Shrines", timeout=10000)

        # Deselect Patnitop (remove infeasible place)
        patnitop_card = page.locator("div.card:has-text('Patnitop')").first
        patnitop_card.locator("button:has-text('✓ Selected')").click()

        # Regenerate Itinerary
        page.click("button:has-text('Generate Day-Wise Itinerary')")
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Now infeasible advisory should be gone!
        self.assertEqual(page.locator("[data-testid='infeasible-advisory']").count(), 0, "Infeasible advisory should disappear after removing infeasible destination")
        # Feasible advisory still present with Bhairavnath Temple
        self.assertTrue(page.locator("[data-testid='feasible-advisory']").is_visible(), "Feasible advisory should remain for Bhairavnath Temple")
        print("  PASS: Replanning successfully cleared stale infeasible advisory.")

        print("\n--- Testing Scenario 4: 'Choose Later' Does Not Produce False Warning ---")
        # Click Back to Sightseeing
        page.click("button:has-text('← Back to Sightseeing')")
        page.wait_for_selector("text=Step 4: Select Sightseeing & Holy Shrines", timeout=10000)

        # Click "Decide Later / Skip for Now"
        page.click("button:has-text('Decide Later / Skip for Now')")
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Check that NO infeasible advisory is displayed
        self.assertEqual(page.locator("[data-testid='infeasible-advisory']").count(), 0, "No false infeasible advisory on choose later")
        # Check that choose-later notice is displayed
        later_notice = page.locator("[data-testid='choose-later-notice']")
        self.assertTrue(later_notice.is_visible(), "Choose later reassurance note should be visible")
        self.assertIn("Decide Later", later_notice.text_content(), "Reassurance note should state decide later")
        print("  PASS: 'Choose Later' displayed reassurance note without false warnings.")

        print("\n--- Testing Scenario 5: Authorization and Booking Lifecycle Intact ---")
        # Proceed to Step 6
        page.click("button:has-text('Proceed to Human Review & Authorization ➔')")
        page.wait_for_selector("text=Review Summary & Human Authorization Gate", timeout=15000)

        # Check booking particulars
        self.assertTrue(page.locator("text=Booking Particulars").is_visible())
        self.assertTrue(page.locator("text=Travel Route & Transport").is_visible())

        # Check authorization gate checkbox
        auth_checkbox = page.locator("input[type='checkbox']")
        self.assertTrue(auth_checkbox.is_visible())
        auth_checkbox.check()

        # Confirm booking button is now enabled
        confirm_btn = page.locator("button:has-text('Authorize & Confirm Booking')")
        self.assertTrue(confirm_btn.is_enabled())
        confirm_btn.click()

        # Step 7: Confirmation
        page.wait_for_selector("text=Booking Confirmed", timeout=15000)
        self.assertTrue(page.locator("text=Booking Confirmed").is_visible() or page.locator("text=Booking Reference").is_visible())
        print("  PASS: Existing authorization flow and booking lifecycle confirmed successfully.")

if __name__ == '__main__':
    unittest.main()
