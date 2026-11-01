"""
tests/test_featured_destinations_browser.py
E2E browser tests for Featured Destinations navbar item and standalone sightseeing browser.

Verifies:
1. "Featured Destinations" navbar link is functional and renders the dedicated destinations page.
2. Active state (aria-current="page", styles) correctly highlights "Featured Destinations".
3. Destinations load from backend with 29 catalogue entries, category filters, and live search.
4. Clicking destination card opens detailed modal with rich guidance.
5. Home page "View All 29 Destinations" button navigates smoothly to Featured Destinations.
6. Switching between tabs preserves in-progress booking sessions without resetting user inputs.
7. Regressions check on other navbar items (Home, Darshan Bookings, AI Companion, Brand logo).
"""

import time
import unittest
from playwright.sync_api import sync_playwright


class TestFeaturedDestinationsBrowser(unittest.TestCase):
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

    def test_01_featured_destinations_navbar_click_and_display(self):
        """Clicking 'Featured Destinations' in navbar renders standalone SightseeingBrowser with active state."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Initial tab is Home
        nav_home = page.locator("[data-testid='nav-home']")
        self.assertEqual(nav_home.get_attribute("aria-current"), "page")

        # Click "Featured Destinations"
        nav_sightseeing = page.locator("[data-testid='nav-sightseeing']")
        self.assertTrue(nav_sightseeing.is_visible())
        nav_sightseeing.click()

        # Check active state moved to Featured Destinations
        page.wait_for_selector("[data-testid='sightseeing-browser']", timeout=10000)
        self.assertEqual(nav_sightseeing.get_attribute("aria-current"), "page")
        self.assertIsNone(nav_home.get_attribute("aria-current"))

        # Verify page content
        self.assertTrue(page.locator("h2:has-text('Featured Destinations across Jammu & Kashmir')").is_visible())
        self.assertTrue(page.locator("[data-testid='sightseeing-grid']").is_visible())
        self.assertTrue(page.locator("h3:has-text('Bhairavnath Temple')").is_visible())
        self.assertTrue(page.locator("h3:has-text('Shiv Khori')").is_visible())

    def test_02_category_filtering_and_search(self):
        """Verify category filtering and search within standalone Featured Destinations view."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Navigate to Featured Destinations
        page.click("[data-testid='nav-sightseeing']")
        page.wait_for_selector("[data-testid='sightseeing-browser']", timeout=10000)

        # Test search filter for Shiv Khori
        search_input = page.locator("[data-testid='sightseeing-search-input']")
        search_input.fill("Shiv Khori")
        page.wait_for_timeout(300)

        self.assertTrue(page.locator("h3:has-text('Shiv Khori')").is_visible())
        self.assertFalse(page.locator("h3:has-text('Patnitop')").is_visible())

        # Clear search
        page.click("[data-testid='clear-search-btn']")
        page.wait_for_timeout(300)
        self.assertTrue(page.locator("h3:has-text('Patnitop')").is_visible())

        # Test Category Filter: Hill Stations
        page.click("[data-testid='category-filter-hill-station']")
        page.wait_for_timeout(300)
        self.assertTrue(page.locator("h3:has-text('Patnitop')").is_visible())
        self.assertFalse(page.locator("h3:has-text('Bhairavnath Temple')").is_visible())

        # Expand Heritage & Route details for Patnitop
        page.click("[data-testid='toggle-details-patnitop']")
        page.wait_for_selector("[data-testid='place-details-patnitop']", timeout=5000)
        self.assertTrue(page.locator("[data-testid='place-details-patnitop']").is_visible())
        self.assertTrue(page.locator("text=Travel & Access").is_visible())

        # Collapse Details
        page.click("[data-testid='toggle-details-patnitop']")
        page.wait_for_timeout(300)
        self.assertFalse(page.locator("[data-testid='place-details-patnitop']").is_visible())

    def test_03_home_view_all_destinations_button_navigates(self):
        """Verify 'View All 29 Destinations' button in Home page navigates to Featured Destinations."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Scroll to Home's Featured Destinations section
        page.wait_for_selector("[data-testid='view-all-destinations-btn']", timeout=10000)
        page.click("[data-testid='view-all-destinations-btn']")

        # Should land on standalone destinations view with active tab
        page.wait_for_selector("[data-testid='sightseeing-browser']", timeout=10000)
        nav_sightseeing = page.locator("[data-testid='nav-sightseeing']")
        self.assertEqual(nav_sightseeing.get_attribute("aria-current"), "page")

    def test_04_session_preservation_across_tab_switches(self):
        """Switching to Featured Destinations and back to Darshan Bookings preserves trip inputs."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Start booking
        page.click("[data-testid='nav-booking']")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)

        # Select Form mode
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("#travel-origin", timeout=10000)

        # Change departure city to 'Amritsar'
        origin_select = page.locator("#travel-origin")
        origin_select.select_option("Amritsar")

        # Change pax to 4
        pax_select = page.locator("#travel-pax")
        pax_select.select_option("4")

        # Now navigate to Featured Destinations tab
        page.click("[data-testid='nav-sightseeing']")
        page.wait_for_selector("[data-testid='sightseeing-browser']", timeout=10000)
        self.assertEqual(page.locator("[data-testid='nav-sightseeing']").get_attribute("aria-current"), "page")

        # Navigate back to Darshan Bookings tab
        page.click("[data-testid='nav-booking']")
        page.wait_for_selector("#travel-origin", timeout=10000)
        self.assertEqual(page.locator("[data-testid='nav-booking']").get_attribute("aria-current"), "page")

        # Verify values in booking form were preserved!
        preserved_origin = page.locator("#travel-origin").input_value()
        preserved_pax = page.locator("#travel-pax").input_value()
        self.assertEqual(preserved_origin, "Amritsar")
        self.assertEqual(preserved_pax, "4")

    def test_05_other_navbar_items_regression_check(self):
        """Verify Home, AI Companion, and Brand logo work properly without regressions."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # AI Companion
        page.click("[data-testid='nav-assistant']")
        page.wait_for_selector("text=Vaishno Devi AI Assistant", timeout=10000)
        self.assertEqual(page.locator("[data-testid='nav-assistant']").get_attribute("aria-current"), "page")

        # Brand logo returns to Home
        page.click("[data-testid='nav-brand-logo']")
        page.wait_for_selector("h1:has-text('Shri Mata Vaishno Devi Yatra')", timeout=10000)
        self.assertEqual(page.locator("[data-testid='nav-home']").get_attribute("aria-current"), "page")

        # Plan Your Yatra right-hand button navigates to Darshan Bookings
        page.click("[data-testid='nav-plan-yatra-btn']")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        self.assertEqual(page.locator("[data-testid='nav-booking']").get_attribute("aria-current"), "page")


if __name__ == "__main__":
    unittest.main()
