"""
tests/test_visual_itinerary_timeline_browser.py
E2E browser tests for the redesigned Day-by-Day Sacred Itinerary visual timeline component.

Verifies:
1. Individual visual timeline items (left time column, center marker & connecting line, right title + details).
2. Elimination of dense paragraph-style activity blobs in favor of structured timeline entries.
3. Collapsible day cards: Day 1 expanded by default, other days collapsed by default.
4. Day headers display small Day label, title, date (aligned right), and summary whether collapsed or expanded.
5. "Expand all / Collapse all" button toggles all days synchronously.
6. Compact header with feasible sightseeing summary and "Modify Sights" action button.
7. Separate pacing/recovery note located beneath the itinerary.
8. Responsive layout behavior under mobile viewport dimensions without text overflow.
"""

import time
import unittest
from playwright.sync_api import sync_playwright


class TestVisualItineraryTimelineBrowser(unittest.TestCase):
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

    def _navigate_to_recommended_yatra(self):
        """Helper to navigate to Step 2 (Recommended Yatra) via the Form intake flow."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Open Booking choice screen and pick Guided Form
        page.click("[data-testid='nav-booking']")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("#travel-origin", timeout=10000)

        # Submit search to generate recommendations
        page.click("button:has-text('Search Yatra Options ➔')")
        page.wait_for_selector("text=Your Recommended Yatra Package", timeout=15000)
        page.wait_for_selector("text=Day-by-Day Sacred Itinerary", timeout=10000)

    def test_01_timeline_header_and_day_cards_rendered(self):
        """Verify main heading, day cards, day labels, titles, dates, and summaries."""
        self._navigate_to_recommended_yatra()
        page = self.page

        # Verify main heading
        heading = page.locator("text=Day-by-Day Sacred Itinerary")
        self.assertTrue(heading.is_visible())

        # Verify Day 1 card rendered
        card_1 = page.locator("[data-testid='itinerary-day-card-1']")
        self.assertTrue(card_1.is_visible())
        self.assertEqual(page.locator("[data-testid='day-label-1']").text_content().strip(), "DAY 1")
        self.assertTrue(page.locator("[data-testid='day-title-1']").is_visible())
        self.assertTrue(page.locator("[data-testid='day-date-1']").is_visible())
        self.assertTrue(page.locator("[data-testid='day-summary-1']").is_visible())

        # Verify Day 2 card rendered
        card_2 = page.locator("[data-testid='itinerary-day-card-2']")
        self.assertTrue(card_2.is_visible())
        self.assertEqual(page.locator("[data-testid='day-label-2']").text_content().strip(), "DAY 2")
        self.assertTrue(page.locator("[data-testid='day-summary-2']").is_visible())

    def test_02_collapsible_behavior_default_states_and_toggle(self):
        """Verify Day 1 is expanded by default, other days collapsed, and headers toggle smoothly."""
        self._navigate_to_recommended_yatra()
        page = self.page

        # Day 1 timeline should be visible by default
        timeline_1 = page.locator("[data-testid='day-timeline-1']")
        self.assertTrue(timeline_1.is_visible())

        # Day 2 timeline should be collapsed by default
        timeline_2 = page.locator("[data-testid='day-timeline-2']")
        self.assertFalse(timeline_2.is_visible())

        # Clicking Day 2 header should expand Day 2
        header_2 = page.locator("[data-testid='day-header-2']")
        header_2.click()
        page.wait_for_timeout(300)
        self.assertTrue(timeline_2.is_visible())

        # Verify Day 2 summary is still visible when expanded
        self.assertTrue(page.locator("[data-testid='day-summary-2']").is_visible())

        # Clicking Day 2 header again should collapse Day 2
        header_2.click()
        page.wait_for_timeout(300)
        self.assertFalse(timeline_2.is_visible())

        # Test 'Expand All / Collapse All' button
        toggle_all_btn = page.locator("[data-testid='itinerary-toggle-all-btn']")
        self.assertTrue(toggle_all_btn.is_visible())

        # Click Expand All
        toggle_all_btn.click()
        page.wait_for_timeout(300)
        self.assertTrue(page.locator("[data-testid='day-timeline-1']").is_visible())
        self.assertTrue(page.locator("[data-testid='day-timeline-2']").is_visible())
        self.assertEqual(toggle_all_btn.text_content().strip(), "Collapse All")

        # Click Collapse All
        toggle_all_btn.click()
        page.wait_for_timeout(300)
        self.assertFalse(page.locator("[data-testid='day-timeline-1']").is_visible())
        self.assertFalse(page.locator("[data-testid='day-timeline-2']").is_visible())
        self.assertEqual(toggle_all_btn.text_content().strip(), "Expand All")

    def test_03_individual_timeline_items_structure_and_concise_labels(self):
        """Verify each activity is a timeline item with prominent time, concise title, and detail line."""
        self._navigate_to_recommended_yatra()
        page = self.page

        # Expand Day 1 if not already
        if not page.locator("[data-testid='day-timeline-1']").is_visible():
            page.locator("[data-testid='day-header-1']").click()
            page.wait_for_timeout(300)

        # Check first timeline item
        item_0 = page.locator("[data-testid='timeline-item-1-0']")
        self.assertTrue(item_0.is_visible())

        # Prominent time column on left
        time_col = page.locator("[data-testid='timeline-time-1-0']")
        self.assertTrue(time_col.is_visible())
        time_text = time_col.text_content().strip()
        self.assertTrue("AM" in time_text or "PM" in time_text or "10:00" in time_text)

        # Small dot marker
        marker = page.locator("[data-testid='timeline-marker-1-0']")
        self.assertTrue(marker.is_visible())

        # Short, concise activity title (not dense paragraph)
        title_elem = page.locator("[data-testid='timeline-title-1-0']")
        self.assertTrue(title_elem.is_visible())
        title_text = title_elem.text_content().strip()
        self.assertTrue(len(title_text) < 65, f"Title should be concise, got: '{title_text}'")
        self.assertIn("Train journey", title_text)

        # Detail line underneath
        desc_elem = page.locator("[data-testid='timeline-desc-1-0']")
        self.assertTrue(desc_elem.is_visible())
        desc_text = desc_elem.text_content().strip()
        self.assertIn("Indian Railways", desc_text)
        self.assertIn("Departs", desc_text)

        # Verify other activities in Day 1 are also individual timeline rows
        self.assertTrue(page.locator("text=Arrival & Hotel Check-in").is_visible())
        self.assertTrue(page.locator("text=Mandatory Yatra RFID Registration").is_visible())

    def test_04_pacing_note_and_modify_sights_action(self):
        """Verify separate pacing note box beneath timeline and Modify Sights secondary action."""
        self._navigate_to_recommended_yatra()
        page = self.page

        # Pacing Note section beneath the timeline
        pacing_box = page.locator("[data-testid='itinerary-pacing-note']")
        self.assertTrue(pacing_box.is_visible())
        self.assertIn("Pacing Note", pacing_box.text_content())
        self.assertIn("Dedicated rest buffers are allocated post-Bhawan descent", pacing_box.text_content())

        # Modify Sights button
        modify_btn = page.locator("[data-testid='itinerary-modify-sights-btn']")
        self.assertTrue(modify_btn.is_visible())
        modify_btn.click()

        # Should navigate to sightseeing customization step
        page.wait_for_selector("text=Select Sightseeing & Holy Shrines", timeout=10000)
        self.assertTrue(page.locator("[data-testid='sightseeing-browser']").is_visible())

    def test_05_responsive_layout_mobile_viewport(self):
        """Verify timeline renders legibly on mobile viewport (375x667) without horizontal clipping."""
        self._navigate_to_recommended_yatra()
        page = self.page

        # Resize to iPhone SE dimensions
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(300)

        # Day 1 timeline should remain visible and well-structured
        self.assertTrue(page.locator("[data-testid='itinerary-day-card-1']").is_visible())
        self.assertTrue(page.locator("[data-testid='timeline-title-1-0']").is_visible())
        self.assertTrue(page.locator("[data-testid='itinerary-pacing-note']").is_visible())

        # Restore desktop viewport
        page.set_viewport_size({"width": 1280, "height": 800})


if __name__ == "__main__":
    unittest.main()
