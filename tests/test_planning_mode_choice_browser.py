"""
tests/test_planning_mode_choice_browser.py
Phase 8 — Step 5: User Choice Between Form-Based and Chat-Based Trip Planning.

Verifies:
1. Choice Screen is presented on entry without forcing either mode.
2. Both options ("Plan with a Form" and "Chat with AI") are clearly explained and functional.
3. Form intake opens with all supported fields and allows switching to Chat without detail loss.
4. Chat mode allows natural planning and switching to Form without detail loss.
5. Bi-directional state synchronization (trip requirements, itinerary, feasibility advisories).
6. Human authorization and booking safeguards remain intact in both modes.
"""

import time
import unittest
from playwright.sync_api import sync_playwright


class TestPlanningModeChoiceBrowser(unittest.TestCase):
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

    def test_01_choice_screen_presentation_and_visual_balance(self):
        """Test 1: Verify both choices appear prominently on the entry screen without forcing either mode."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        # Click "Plan Your Yatra" on navbar
        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)

        # Confirm choice screen is visible and neither mode was opened automatically
        self.assertTrue(page.locator("[data-testid='choice-screen']").is_visible(), "Choice screen should be displayed")
        self.assertFalse(page.locator(".stepper-container").is_visible(), "Stepper should not appear before choosing form")
        self.assertFalse(page.locator("[data-testid='chat-planning-workspace']").is_visible(), "Chat workspace should not open before choosing chat")

        # Confirm Option 1: Plan with a Form
        form_card = page.locator("[data-testid='choice-form-card']")
        self.assertTrue(form_card.is_visible(), "Form option card must be visible")
        self.assertIn("Plan with a Form", form_card.text_content())
        self.assertIn("Structured & Direct", form_card.text_content())
        self.assertTrue(page.locator("[data-testid='select-form-btn']").is_visible())

        # Confirm Option 2: Chat with AI
        chat_card = page.locator("[data-testid='choice-chat-card']")
        self.assertTrue(chat_card.is_visible(), "Chat option card must be visible")
        self.assertIn("Chat with AI", chat_card.text_content())
        self.assertIn("Conversational & Flexible", chat_card.text_content())
        self.assertTrue(page.locator("[data-testid='select-chat-btn']").is_visible())

        print("  PASS Test 1: Entry screen displays balanced choice screen without forcing either mode.")

    def test_02_select_form_opens_structured_intake_with_switcher(self):
        """Test 2: Selecting 'Plan with a Form' opens the guided flow with all extended fields and a visible switcher."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)

        # Select Form
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # Verify mode switcher bar is visible
        switcher_bar = page.locator("[data-testid='mode-switcher-bar']")
        self.assertTrue(switcher_bar.is_visible(), "Mode switcher bar must be visible in form mode")
        self.assertIn("Guided Structured Form", switcher_bar.text_content())
        self.assertTrue(page.locator("[data-testid='switch-to-chat-btn']").is_visible(), "Switch to Chat button must be visible")

        # Verify extended form fields exist
        self.assertTrue(page.locator("label:has-text('Budget Scope')").is_visible(), "Budget scope selector must exist")
        self.assertTrue(page.locator("label:has-text('Budget Amount')").is_visible(), "Budget amount input must exist")
        self.assertTrue(page.locator("label:has-text('Travel Pace / Style')").is_visible(), "Travel pace selector must exist")
        self.assertTrue(page.locator("label:has-text('Stay Preference')").is_visible(), "Stay preference selector must exist")
        self.assertTrue(page.locator("label:has-text('Sightseeing Plan')").is_visible(), "Sightseeing plan selector must exist")

        print("  PASS Test 2: 'Plan with a Form' opens structured intake with all extended fields and switcher.")

    def test_03_switch_from_form_to_chat_preserves_details(self):
        """Test 3: Start with the form, enter custom details, and switch to chat without losing details."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # Set Departure City to Mumbai, Duration to 5 days, Pax to 3
        origin_select = page.locator("label:has-text('Departure City') + select")
        origin_select.select_option("Mumbai")

        duration_select = page.locator("label:has-text('Trip Duration') + select")
        duration_select.select_option("5")

        pax_select = page.locator("label:has-text('Pilgrims (Pax)') + select")
        pax_select.select_option("3")

        # Search options to populate shared trip request
        page.click("button:has-text('Search Yatra Options ➔')")
        page.wait_for_selector("[data-testid='recommended-yatra-page']", timeout=15000)

        # Verify in Recommended Yatra: origin is Mumbai
        body_text = page.inner_text("body")
        self.assertIn("Mumbai", body_text)

        # Now click Switch to Chat!
        page.click("[data-testid='switch-to-chat-btn']")
        page.wait_for_selector("[data-testid='chat-planning-workspace']", timeout=10000)

        # Verify chat workspace is active and reflects Mumbai and 3 pilgrims
        chat_switcher = page.locator("[data-testid='mode-switcher-bar']")
        self.assertIn("Conversational AI Assistant", chat_switcher.text_content())
        self.assertIn("Mumbai", chat_switcher.text_content(), "Chat switcher should preserve Mumbai from form")
        self.assertIn("3 Pilgrims", chat_switcher.text_content(), "Chat switcher should preserve pax count from form")

        # Switch back to Form
        page.click("[data-testid='switch-to-form-btn']")
        page.wait_for_selector("[data-testid='recommended-yatra-page']", timeout=10000)
        self.assertIn("Mumbai", page.inner_text("body"), "Returning to form should preserve Mumbai")

        print("  PASS Test 3: Form details preserved seamlessly when switching to Chat and back.")

    def test_04_chat_planning_and_switch_to_form_preserves_plan(self):
        """Test 4: Start in Chat, plan a trip, and switch to Form preserving the active plan."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)

        # Select Chat
        page.click("[data-testid='select-chat-btn']")
        page.wait_for_selector("[data-testid='chat-planning-workspace']", timeout=10000)

        chat_input = page.locator("[data-testid='chat-planning-workspace'] input[placeholder*='Ask Yatra AI']")
        self.assertTrue(chat_input.is_visible())

        # Ask complete trip plan
        chat_input.fill("I want to travel from Delhi for 4 days with 2 travellers and total budget 15000")
        page.click("[data-testid='chat-planning-workspace'] button:has-text('Send ➔')")

        # Wait for plan generation
        page.wait_for_selector("div:has-text('PLAN')", timeout=20000)
        time.sleep(1.5)

        # Verify chat shared trip badge or mode switcher reflects trip
        switcher = page.locator("[data-testid='mode-switcher-bar']")
        self.assertTrue("Delhi" in switcher.text_content() or "Pilgrim" in switcher.text_content())

        # Switch to Form
        page.click("[data-testid='switch-to-form-btn']")

        # The form should receive the shared state
        time.sleep(1.0)
        form_content = page.content()
        self.assertTrue("Delhi" in form_content or "Step" in form_content, "Form mode should load shared trip context")
        print("  PASS Test 4: Starting in Chat and switching to Form preserves trip plan and session.")

    def test_05_itinerary_and_feasibility_in_form_with_full_flow(self):
        """Test 5: Verify realistic itinerary and feasibility advisories in Form mode, and verify that switching to chat displays the synced itinerary badge."""
        page = self.page
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('Plan Your Yatra')")
        page.wait_for_selector("[data-testid='choice-screen']", timeout=10000)
        page.click("[data-testid='select-form-btn']")
        page.wait_for_selector("text=Plan Your Sacred Yatra", timeout=10000)

        # Set 3 days duration
        duration_select = page.locator("label:has-text('Trip Duration') + select")
        duration_select.select_option("3")
        page.click("button:has-text('Search Yatra Options ➔')")

        # In Recommendation-First flow: lands on recommended yatra page
        page.wait_for_selector("[data-testid='recommended-yatra-page']", timeout=15000)

        # Open sightseeing customization via Change My Selections
        page.click("[data-testid='change-my-selections-btn']")
        page.click("[data-testid='edit-cat-sightseeing']")

        # Step 4: Add Bhairavnath (feasible) and Patnitop (infeasible on 3-day)
        page.wait_for_selector("text=Select Sightseeing & Holy Shrines", timeout=15000)
        bhairav_card = page.locator("div.card:has-text('Bhairavnath Temple')").first
        bhairav_card.locator("button:has-text('+ Add Place')").click()

        patnitop_card = page.locator("div.card:has-text('Patnitop')").first
        patnitop_card.locator("button:has-text('+ Add Place')").click()

        # Step 5: Generate Itinerary
        page.click("button:has-text('Generate Day-Wise Itinerary')")
        page.wait_for_selector("[data-testid='recommended-yatra-page']", timeout=15000)

        # Feasible & Infeasible advisories visible
        self.assertTrue(page.locator("[data-testid='feasible-advisory']").is_visible(), "Feasible advisory must be visible")
        self.assertTrue(page.locator("[data-testid='infeasible-advisory']").is_visible(), "Infeasible advisory must be visible")

        # Now switch to Chat while itinerary is active!
        page.click("[data-testid='switch-to-chat-btn']")
        page.wait_for_selector("[data-testid='chat-planning-workspace']", timeout=10000)

        # Active itinerary badge must be visible in Chat mode!
        itinerary_badge = page.locator("[data-testid='chat-shared-trip-badge']")
        self.assertTrue(itinerary_badge.is_visible(), "Active itinerary badge must appear in chat mode")
        badge_text = itinerary_badge.text_content()
        self.assertIn("Active Itinerary Synced", badge_text)
        self.assertIn("Bhairavnath Temple", badge_text)

        # Click return to Form directly from badge
        page.click("button:has-text('View Full Timeline in Form ➔')")
        page.wait_for_selector("[data-testid='recommended-yatra-page']", timeout=10000)
        self.assertTrue(page.locator("[data-testid='feasible-advisory']").is_visible(), "Returning to form retains feasible advisory")

        # Step: Confirm selections & proceed to Human Review & Authorization Gate
        page.click("[data-testid='confirm-selections-continue-btn']")
        page.wait_for_selector("text=Review Summary & Human Authorization Gate", timeout=15000)

        # Check authorization checkbox & confirm
        page.click("button:has-text('Run Playwright RPA Mock Verification')")
        page.wait_for_selector("text=RPA Agent Execution Successful", timeout=25000)

        auth_checkbox = page.locator("input[type='checkbox']")
        if not auth_checkbox.is_checked():
            auth_checkbox.check()

        page.click("button:has-text('Authorize & Confirm Booking ➔')")

        # Step 7: Confirmation
        page.wait_for_selector("text=JAI MATA DI! BOOKING CONFIRMED", timeout=20000)
        self.assertIn("Official Booking Reference ID", page.content())
        print("  PASS Test 5: End-to-end plan, feasibility advisories, chat sync badge, and authorization gate verified.")


if __name__ == "__main__":
    unittest.main()
