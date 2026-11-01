"""
tests/test_audit_journey_e_edge_cases.py
Phase 8 — Step 7: End-to-End Integration and Reliability Audit — Journey E & Edge Cases.

Validates:
1. Browser refresh and session recovery via sessionStorage.
2. Second tab session isolation (no cross-tab contamination).
3. Budget boundary handling (zero budget / input min restrictions).
4. Sightseeing "Decide Later" flow without forced excursions.
5. Infeasible excursions display clear deterministic advisories with suggestions in the UI.
"""

import time
import unittest
from playwright.sync_api import sync_playwright


class TestAuditJourneyEEdgeCases(unittest.TestCase):
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

    def test_01_session_recovery_on_refresh(self):
        """Test 1: Session recovery on page refresh."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Go to Plan Your Yatra -> Select Form
        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("form", timeout=10000)

        # Submit search to establish session
        page.click("button:has-text('Search Yatra Options')")
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)

        # Check sessionStorage for session ID
        session_id = page.evaluate("() => sessionStorage.getItem('yatra_session_id')")
        self.assertTrue(session_id is not None and len(session_id) > 0, "sessionStorage must contain yatra_session_id")
        plan_version = page.evaluate("() => sessionStorage.getItem('yatra_plan_version')")
        self.assertTrue(plan_version is not None, "sessionStorage must contain yatra_plan_version")

        # Reload page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Check recovered values
        recovered_sid = page.evaluate("() => sessionStorage.getItem('yatra_session_id')")
        self.assertEqual(recovered_sid, session_id, "Session ID should be preserved across reload")

        # Verify no fatal uncaught errors on reload
        fatal_errors = [e for e in self.console_errors if "Failed to load resource" not in e and "favicon" not in e]
        self.assertEqual(len(fatal_errors), 0, f"Found console errors on reload: {fatal_errors}")
        print("  PASS Test 1: Session recovery on reload verified.")

    def test_02_second_tab_session_isolation(self):
        """Test 2: Second tab starts fresh without leaking state from tab 1."""
        page1 = self.page
        page1.goto("http://127.0.0.1:5173/")
        page1.wait_for_load_state("networkidle")

        # Set a session in page 1
        page1.evaluate("() => sessionStorage.setItem('yatra_session_id', 'test-session-tab-1')")

        # Open a new tab (new page in same browser context)
        page2 = self.context.new_page()
        page2.goto("http://127.0.0.1:5173/")
        page2.wait_for_load_state("networkidle")

        # Click "Plan Your Yatra" on page 2
        page2.click("button:has-text('Plan Your Yatra')")
        page2.wait_for_selector("[data-testid='choice-screen']", timeout=10000)

        # Page 2 must show Choice Screen cleanly
        self.assertTrue(page2.locator("[data-testid='choice-screen']").is_visible())
        self.assertTrue(page2.locator("[data-testid='select-form-btn']").is_visible())
        self.assertTrue(page2.locator("[data-testid='select-chat-btn']").is_visible())

        page2.close()
        print("  PASS Test 2: Second tab session isolation verified.")

    def test_03_zero_or_negative_budget_input_bounds(self):
        """Test 3: Zero or negative budget input validation."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("form", timeout=10000)

        # Locate budget input
        budget_input = page.locator("input[placeholder*='e.g. 15000']")
        self.assertTrue(budget_input.is_visible())

        # Check min attribute
        min_attr = budget_input.get_attribute("min")
        self.assertEqual(min_attr, "0", "Budget input must have min='0'")

        # Test with zero budget
        budget_input.fill("0")
        page.click("button:has-text('Search Yatra Options')")
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)

        # Must not crash and should reach Step 2
        self.assertTrue(page.locator("text=Step 2: Select Travel & Darshan Option").is_visible())
        print("  PASS Test 3: Budget input bounds and zero budget handling verified.")

    def test_04_sightseeing_decide_later_flow(self):
        """Test 4: Sightseeing 'Decide Later' flow."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("form", timeout=10000)

        # Search options
        page.click("button:has-text('Search Yatra Options')")
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)

        # Step 2 -> Step 3 (Hotels)
        page.click("button:has-text('Proceed to Accommodation')")
        page.wait_for_selector("text=Step 3: Choose Katra Accommodation", timeout=15000)

        # Step 3 -> Step 4 (Sightseeing)
        page.click("button:has-text('Proceed to Sightseeing')")
        page.wait_for_selector("text=Step 4: Select Sightseeing & Holy Shrines", timeout=15000)

        # Click "Decide Later / Skip for Now"
        page.click("[data-testid='choose-later-btn']")
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Feasibility advisory should not show false infeasible warnings
        self.assertFalse(page.locator("text=Infeasible Sightseeing Destinations").is_visible())
        print("  PASS Test 4: Sightseeing 'Decide Later' flow verified.")

    def test_05_infeasible_excursion_shows_clear_advisory_in_ui(self):
        """Test 5: Selecting Patnitop on a 3-day trip shows clear infeasible advisory in UI."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("form", timeout=10000)

        # Select 3 Days duration
        page.select_option("select:has(option:has-text('3 Days'))", "3")

        # Search options
        page.click("button:has-text('Search Yatra Options')")
        page.wait_for_selector("text=Step 2: Select Travel & Darshan Option", timeout=15000)

        # Step 2 -> Step 3
        page.click("button:has-text('Proceed to Accommodation')")
        page.wait_for_selector("text=Step 3: Choose Katra Accommodation", timeout=15000)

        # Step 3 -> Step 4
        page.click("button:has-text('Proceed to Sightseeing')")
        page.wait_for_selector("text=Step 4: Select Sightseeing & Holy Shrines", timeout=15000)

        # Select Patnitop
        patnitop_card = page.locator("div.card:has-text('Patnitop')").first
        self.assertTrue(patnitop_card.is_visible())
        patnitop_card.locator("button:has-text('+ Add Place')").click()

        # Generate Itinerary
        page.click("button:has-text('Generate Day-Wise Itinerary')")
        page.wait_for_selector("text=Customized Day-Wise Timeline Itinerary", timeout=15000)

        # Verify Infeasible Advisory is displayed
        page.wait_for_selector("[data-testid='infeasible-advisory']", timeout=10000)
        advisory_text = page.locator("[data-testid='infeasible-advisory']").text_content()
        self.assertIn("Patnitop", advisory_text)
        self.assertIn("85 km", advisory_text)
        self.assertTrue("4+" in advisory_text or "extend" in advisory_text.lower() or "requires" in advisory_text.lower())

        # Verify Day 2 is the exclusive holy trek
        day2_text = page.locator("div.card:has-text('DAY 02')").text_content()
        self.assertIn("Holy Yatra", day2_text)
        print("  PASS Test 5: Infeasible excursion advisory with explanation verified.")


if __name__ == "__main__":
    unittest.main()
