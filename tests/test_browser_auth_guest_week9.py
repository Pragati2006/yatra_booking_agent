"""
tests/test_browser_auth_guest_week9.py
Week 9: Browser E2E Verification of Optional Passwordless Authentication & Guest Mode.

Verifies using Playwright against the React application:
1. Opens application directly in Guest Mode with zero blocking login walls.
2. Clicking 'Sign In' in Navbar opens AuthModal.
3. Entering email dispatches OTP via MockEmailProvider.
4. Entering 6-digit OTP authenticates user and updates Navbar with 'Saved Trips' and 'Sign Out'.
5. Clicking 'Sign Out' returns interface seamlessly to Guest Mode.
"""

import os
import sys
import time
import unittest
from unittest.mock import patch

# Ensure utf-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
from backend.main import app
import agents.auth_service as auth_service
from agents.auth_service import get_email_provider, set_email_provider, MockEmailProvider


class TestBrowserAuthGuestWeek9(unittest.TestCase):
    """Playwright browser tests for Guest Mode and optional authentication flow."""

    def setUp(self):
        self.mock_provider = MockEmailProvider()
        set_email_provider(self.mock_provider)
        self.test_email = "pilgrim.browser.test@example.com"

    def tearDown(self):
        self.mock_provider.clear()

    def test_01_guest_mode_and_auth_workflow_via_api_and_dom_contract(self):
        """Verifies Guest Mode invariants and email OTP authentication contract."""
        client = TestClient(app)

        # 1. Guest Mode check: /api/auth/me returns guest without error
        me_resp = client.get("/api/auth/me")
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["status"], "guest")
        self.assertFalse(me_resp.json()["authenticated"])

        # 2. Request OTP
        req_resp = client.post("/api/auth/request-otp", json={"email": self.test_email})
        self.assertEqual(req_resp.status_code, 200)
        otp = self.mock_provider.get_latest_otp_for(self.test_email)
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp), 6)

        # 3. Verify OTP
        verify_resp = client.post("/api/auth/verify-otp", json={"email": self.test_email, "otp_code": otp})
        self.assertEqual(verify_resp.status_code, 200)
        token = verify_resp.json()["session_token"]
        self.assertIsNotNone(token)

        # 4. Authenticated check
        auth_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(auth_me.status_code, 200)
        self.assertEqual(auth_me.json()["status"], "authenticated")
        self.assertEqual(auth_me.json()["user"]["email"], self.test_email.lower())

        # 5. Logout
        logout_resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_resp.status_code, 200)

        # 6. Post-logout check -> back to Guest Mode
        after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(after_logout.json()["status"], "guest")

    def test_02_playwright_live_browser_otp_flow(self):
        """
        Executes live Playwright browser automation verifying:
        1. Default Guest Mode (no login wall, 'Sign In' button present)
        2. AuthModal opening and email submission
        3. Transition to 6-digit OTP entry screen with countdown
        4. OTP input and successful authentication
        5. Authenticated Navbar state ('Saved Trips', 'Sign Out', email badge)
        6. Saved Trips modal opening and inspection
        7. Smooth Sign Out reverting back to Guest Mode
        Captures full-cycle audit screenshots in docs/.
        """
        email = f"pilgrim.live.{int(time.time())}@yatra.org"
        docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
        os.makedirs(docs_dir, exist_ok=True)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 800})

                # 1. Navigate to frontend in Guest Mode
                page.goto("http://127.0.0.1:5173/", timeout=15000)
                page.wait_for_selector("button:has-text('Sign In'), button:has-text('👤 Sign In')", timeout=10000)

                # Verify Guest Mode: no modal visible, Sign In button is present
                signin_btn = page.locator("button:has-text('Sign In'), button:has-text('👤 Sign In')").first
                self.assertTrue(signin_btn.is_visible(), "Sign In button must be visible in Guest Mode")

                guest_screenshot = os.path.join(docs_dir, "auth_step0_guest_mode.png")
                page.screenshot(path=guest_screenshot)

                # 2. Open AuthModal
                signin_btn.click()
                email_input = page.locator("#authEmailInput")
                email_input.wait_for(state="visible", timeout=5000)
                self.assertTrue(email_input.is_visible(), "Auth modal email input must be visible")

                # Type email
                email_input.fill(email)
                modal_screenshot = os.path.join(docs_dir, "auth_step1_email_input.png")
                page.screenshot(path=modal_screenshot)

                # 3. Request OTP
                send_code_btn = page.locator("button:has-text('Send Verification Code')").first
                send_code_btn.click()

                # Wait for OTP step
                otp_input = page.locator("#authOtpInput")
                otp_input.wait_for(state="visible", timeout=8000)
                self.assertTrue(otp_input.is_visible(), "OTP input field must be visible after sending code")

                otp_screen_screenshot = os.path.join(docs_dir, "auth_step2_otp_entry.png")
                page.screenshot(path=otp_screen_screenshot)

                # 4. Fetch the OTP generated for this email
                # Use page.evaluate to fetch from backend test endpoint
                res = page.evaluate(f"""
                    fetch('http://127.0.0.1:8000/api/auth/test/latest-otp?email={email}')
                        .then(r => r.json())
                """)
                latest_otp = res.get("latest_otp")
                self.assertIsNotNone(latest_otp, "Should retrieve generated OTP from test endpoint")
                self.assertEqual(len(latest_otp), 6)

                # 5. Fill OTP and Verify
                otp_input.fill(latest_otp)
                verify_btn = page.locator("button:has-text('Verify & Sign In'), button:has-text('Verify')").first
                verify_btn.click()

                # Wait for success screen in modal
                continue_btn = page.locator("button:has-text('Continue to Application'), button:has-text('✕')").first
                continue_btn.wait_for(state="visible", timeout=8000)
                continue_btn.click()
                # Condition-based wait for authenticated navbar elements to render
                signout_btn = page.locator("[data-testid='nav-logout-btn'], button:has-text('Sign Out'), button:has-text('🚪 Sign Out')").first
                saved_trips_btn = page.locator("[data-testid='nav-saved-trips-btn'], button:has-text('Saved Trips'), button:has-text('My Account')").first
                saved_trips_btn.wait_for(state="visible", timeout=10000)
                signout_btn.wait_for(state="visible", timeout=10000)
                self.assertTrue(signout_btn.is_visible(), "Sign Out button must be visible after authentication")
                self.assertTrue(saved_trips_btn.is_visible(), "Saved Trips button must be visible after authentication")

                auth_screenshot = os.path.join(docs_dir, "auth_step3_authenticated_navbar.png")
                page.screenshot(path=auth_screenshot)

                # 7. Open Saved Trips Modal
                saved_trips_btn.click()
                saved_modal = page.locator("div[role='dialog']:has-text('My Account & Saved History'), div[role='dialog']:has-text('Saved')")
                saved_modal.wait_for(state="visible", timeout=8000)

                saved_modal_screenshot = os.path.join(docs_dir, "auth_step4_saved_trips_modal.png")
                page.screenshot(path=saved_modal_screenshot)

                # Close Saved Trips modal
                close_btn = saved_modal.locator("[data-testid='account-modal-close-btn'], button:has-text('✕')").first
                close_btn.click()
                page.wait_for_timeout(300)

                # 8. Sign Out
                signout_btn.click()
                page.wait_for_selector("button:has-text('Sign In'), button:has-text('👤 Sign In')", timeout=5000)

                # Verify reverted to Guest Mode
                self.assertTrue(signin_btn.is_visible(), "Sign In button must return after logout")
                logout_screenshot = os.path.join(docs_dir, "auth_step5_logged_out_guest_mode.png")
                page.screenshot(path=logout_screenshot)

                browser.close()
        except Exception as e:
            # If server not reachable in some environments, skip gracefully
            if "net::ERR_CONNECTION_REFUSED" in str(e):
                self.skipTest(f"Live frontend server not reachable: {e}")
            else:
                raise


if __name__ == "__main__":
    unittest.main()

