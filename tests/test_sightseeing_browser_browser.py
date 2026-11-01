"""
tests/test_sightseeing_browser_browser.py
Phase 8 — Step 6: Interactive Jammu & Kashmir Sightseeing Browser.

Verifies:
1. All 29 catalogue destinations load from the existing source.
2. Category filters and real-time name search work with accurate live count badges.
3. Adding and removing destinations updates selected list, card styles, and summary bar.
4. Quick-remove tags in the selected summary bar work seamlessly.
5. Selected places reach itinerary generation, and infeasible places are reported honestly with reasons & suggestions.
6. Selections survive switching between Form and Chat modes bi-directionally.
7. Removing an infeasible destination clears stale warnings upon replanning.
8. "Decide Later / Keep Vaishno Devi Only" continues to work without forcing selections.
9. Human authorization and booking safeguards remain intact.
"""

import time
import unittest
from playwright.sync_api import sync_playwright


class TestSightseeingBrowser(unittest.TestCase):
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

    def _navigate_to_sightseeing_browser(self):
        """Helper to navigate to Step 4 Sightseeing Browser via the form flow."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Open Choice screen and pick Form
        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # Set 3-day duration
        duration_select = page.locator("label:has-text('Trip Duration') + select")
        duration_select.select_option("3")

        # Search options to advance to Step 2
        page.click("button:has-text('Search Yatra Options ➔')")
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)
        page.click("button:has-text('Proceed to Accommodation ➔')")

        # Advance through Step 3 (skip hotel) to Step 4
        page.wait_for_selector("text=Step 3: Choose Katra Accommodation", timeout=15000)
        page.click("button:has-text('Skip Hotel')")

        # Wait for Step 4 Sightseeing Browser
        page.wait_for_selector("[data-testid='sightseeing-browser']", timeout=15000)

    def test_01_catalogue_loading_search_and_category_filtering(self):
        """Test 1: Verify all 29 catalogue destinations load, search works, and category filtering updates results."""
        page = self.page
        self._navigate_to_sightseeing_browser()

        # Verify browser header and destination count
        header_text = page.locator("[data-testid='sightseeing-browser']").text_content()
        self.assertIn("29 verified destinations", header_text, "Expected all 29 destinations to be loaded")

        # 1. Test Search by Name
        search_input = page.locator("[data-testid='sightseeing-search-input']")
        search_input.fill("Bhairavnath")
        time.sleep(0.5)

        # Confirm filtered to Bhairavnath Temple
        self.assertTrue(page.locator("[data-testid='place-card-bhairavnath-temple']").is_visible())
        self.assertFalse(page.locator("[data-testid='place-card-patnitop']").is_visible(), "Patnitop should not match 'Bhairavnath'")

        # Clear search
        page.click("[data-testid='clear-search-btn']")
        time.sleep(0.5)
        self.assertTrue(page.locator("[data-testid='place-card-patnitop']").is_visible(), "Patnitop should be visible after clearing search")

        # 2. Test Category Filters
        page.click("[data-testid='category-filter-hill-station']")
        time.sleep(0.5)

        # Hill stations should be visible (e.g. Patnitop, Sanasar)
        self.assertTrue(page.locator("[data-testid='place-card-patnitop']").is_visible())
        self.assertFalse(page.locator("[data-testid='place-card-bhairavnath-temple']").is_visible(), "Bhairavnath is on trek route, not hill station")

        # Reset to All
        page.click("[data-testid='category-filter-all']")
        time.sleep(0.5)
        self.assertTrue(page.locator("[data-testid='place-card-bhairavnath-temple']").is_visible())

        # 3. Test Empty Search State
        search_input.fill("NonExistentPlaceXYZ")
        time.sleep(0.5)
        empty_state = page.locator("[data-testid='sightseeing-empty-state']")
        self.assertTrue(empty_state.is_visible(), "Empty state should appear for non-matching search")
        page.click("[data-testid='reset-filters-btn']")
        time.sleep(0.5)
        self.assertTrue(page.locator("[data-testid='place-card-bhairavnath-temple']").is_visible())

        print("  PASS Test 1: 29 destinations loaded, real-time search, category filters, and empty state verified.")

    def test_02_destination_selection_summary_bar_and_quick_remove(self):
        """Test 2: Verify selecting places updates card styling, summary bar tags, and quick-remove controls."""
        page = self.page
        self._navigate_to_sightseeing_browser()

        # Initially, 0 places selected
        self.assertIn("0 Places Selected", page.locator("[data-testid='selected-count-badge']").text_content())

        # Select Bhairavnath Temple
        page.click("[data-testid='toggle-place-bhairavnath-temple']")
        time.sleep(0.3)

        # Card should now say '✓ Selected'
        bhairav_btn = page.locator("[data-testid='toggle-place-bhairavnath-temple']")
        self.assertIn("✓ Selected", bhairav_btn.text_content())

        # Summary bar should now show tag for Bhairavnath Temple
        summary = page.locator("[data-testid='selected-places-summary']")
        self.assertTrue(page.locator("[data-testid='selected-place-tag-bhairavnath-temple']").is_visible())
        self.assertIn("1 Places Selected", page.locator("[data-testid='selected-count-badge']").text_content())

        # Select Patnitop as well
        page.click("[data-testid='toggle-place-patnitop']")
        time.sleep(0.3)
        self.assertTrue(page.locator("[data-testid='selected-place-tag-patnitop']").is_visible())
        self.assertIn("2 Places Selected", page.locator("[data-testid='selected-count-badge']").text_content())

        # Use quick-remove "×" button on Patnitop's tag in the summary bar
        page.click("[data-testid='remove-place-patnitop']")
        time.sleep(0.3)

        # Patnitop should be removed from summary and button reverted to '+ Add Place'
        self.assertFalse(page.locator("[data-testid='selected-place-tag-patnitop']").is_visible())
        self.assertIn("+ Add Place", page.locator("[data-testid='toggle-place-patnitop']").text_content())
        self.assertIn("1 Places Selected", page.locator("[data-testid='selected-count-badge']").text_content())

        print("  PASS Test 2: Destination selection, card visual feedback, and summary bar quick-remove verified.")

    def test_03_itinerary_feasibility_replanning_and_stale_warning_cleanup(self):
        """Test 3: Select feasible and infeasible places, verify honest advisories, remove infeasible place, and verify cleanup."""
        page = self.page
        self._navigate_to_sightseeing_browser()

        # Select Bhairavnath Temple (trek route -> feasible on 3-day trip)
        page.click("[data-testid='toggle-place-bhairavnath-temple']")

        # Select Patnitop (distant hill station -> infeasible on 3-day trip)
        page.click("[data-testid='toggle-place-patnitop']")

        # Generate Itinerary
        page.click("[data-testid='generate-itinerary-btn']")
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Verify Feasible and Infeasible advisories
        feasible_advisory = page.locator("[data-testid='feasible-advisory']")
        self.assertTrue(feasible_advisory.is_visible())
        self.assertIn("Bhairavnath Temple", feasible_advisory.text_content())

        infeasible_advisory = page.locator("[data-testid='infeasible-advisory']")
        self.assertTrue(infeasible_advisory.is_visible())
        self.assertIn("Patnitop", infeasible_advisory.text_content())
        self.assertIn("Reason:", infeasible_advisory.text_content())
        self.assertIn("Suggestion:", infeasible_advisory.text_content())

        # Now click Back to Sightseeing
        page.click("button:has-text('← Back to Sightseeing')")
        page.wait_for_selector("[data-testid='sightseeing-browser']", timeout=10000)

        # Deselect Patnitop using summary bar remove button
        page.click("[data-testid='remove-place-patnitop']")
        time.sleep(0.3)

        # Regenerate Itinerary
        page.click("[data-testid='generate-itinerary-btn']")
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Infeasible advisory must disappear; feasible advisory remains
        self.assertEqual(page.locator("[data-testid='infeasible-advisory']").count(), 0, "Infeasible advisory should disappear after removing Patnitop")
        self.assertTrue(page.locator("[data-testid='feasible-advisory']").is_visible(), "Feasible advisory should remain for Bhairavnath Temple")

        print("  PASS Test 3: Feasibility advisories, grounded reasons, and stale warning cleanup verified.")

    def test_04_selections_survive_switching_between_form_and_chat(self):
        """Test 4: Verify selections made in Sightseeing Browser survive switching to Chat and back."""
        page = self.page
        self._navigate_to_sightseeing_browser()

        # Select Bhairavnath Temple and Baba Dhansar
        page.click("[data-testid='toggle-place-bhairavnath-temple']")
        page.click("[data-testid='toggle-place-baba-dhansar']")

        # Switch to Chat mode
        page.click("[data-testid='switch-to-chat-btn']")
        page.wait_for_selector("[data-testid='chat-planning-workspace']", timeout=10000)

        # Verify Chat Mode is active
        chat_switcher = page.locator("[data-testid='mode-switcher-bar']")
        self.assertIn("Conversational AI Assistant", chat_switcher.text_content())

        # Switch back to Form mode
        page.click("[data-testid='switch-to-form-btn']")
        page.wait_for_selector("[data-testid='sightseeing-browser']", timeout=10000)

        # Both Bhairavnath Temple and Baba Dhansar must still be selected in the summary bar!
        self.assertTrue(page.locator("[data-testid='selected-place-tag-bhairavnath-temple']").is_visible())
        self.assertTrue(page.locator("[data-testid='selected-place-tag-baba-dhansar']").is_visible())
        self.assertIn("2 Places Selected", page.locator("[data-testid='selected-count-badge']").text_content())

        print("  PASS Test 4: Selections survive switching between Form and Chat modes bi-directionally.")

    def test_05_decide_later_and_authorization_gate_lifecycle(self):
        """Test 5: Verify 'Decide Later' generates core pilgrimage without false warnings, and booking authorization remains intact."""
        page = self.page
        self._navigate_to_sightseeing_browser()

        # Click Decide Later / Keep Vaishno Devi Only
        page.click("[data-testid='choose-later-btn']")
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Confirm no infeasible warnings
        self.assertEqual(page.locator("[data-testid='infeasible-advisory']").count(), 0)

        # Proceed to Authorization Gate
        page.click("button:has-text('Proceed to Human Review & Authorization ➔')")
        page.wait_for_selector("text=Review Summary & Human Authorization Gate", timeout=15000)

        # RPA mock execution
        page.click("button:has-text('Run Playwright RPA Mock Verification')")
        page.wait_for_selector("text=RPA Agent Execution Successful", timeout=25000)

        auth_checkbox = page.locator("input[type='checkbox']")
        if not auth_checkbox.is_checked():
            auth_checkbox.check()

        page.click("button:has-text('Authorize & Confirm Booking ➔')")

        # Step 7: Confirmation Page
        page.wait_for_selector("text=JAI MATA DI! BOOKING CONFIRMED", timeout=20000)
        self.assertIn("Official Booking Reference ID", page.content())

        print("  PASS Test 5: 'Decide Later' and human authorization gate lifecycle verified.")


if __name__ == "__main__":
    unittest.main()
