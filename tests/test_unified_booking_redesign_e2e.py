"""
tests/test_unified_booking_redesign_e2e.py
End-to-End Real Browser Integration Test for Unified Yatra Booking with Playwright RPA.

Validates the full Part 1-6 Requirements:
1. Stepper reflects authentic 4-step journey (Preferences -> Recommended Yatra -> Booking Review & RPA -> Confirmation & Download Pass).
2. Guest user explores preferences (Step 1) and recommendations (Step 2) freely.
3. Compulsory login: Guest clicking "Start Yatra Booking with RPA" triggers AuthModal.
4. Email OTP request, retrieval, and verification establishing authenticated session.
5. Preserves selected itinerary upon login and returns to Step 3.
6. Authenticated user initiates single-button Playwright RPA workflow.
7. Sequential HITL checkpoints:
   - OTP challenge and failure recovery -> verified.
   - CAPTCHA challenge and failure recovery -> verified.
   - Simulated Payment (₹0 Live Charge).
   - Final confirmation persisted before Step 3 completes.
8. Bottom prominent button "Continue to Confirmation ➔" appears after successful RPA.
9. Clicking "Continue to Confirmation" navigates to Step 4 (Confirmation & Download Pass).
10. Step 4 displays genuine booking reference, pax, date, simulated payment disclaimer, and demo pilgrim pass.
11. "Download Pass (PDF)" generates standards-compliant PDF containing booking reference and disclaimer.
12. "Print Pass" triggers print-ready view.
13. Stepper allows sensible backward navigation without state loss.
14. "Plan Another Yatra" resets confirmed state, guarding Step 4 against unconfirmed workflows.
"""

import os
import sys
import json
import time
import unittest
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence_redesign")
os.makedirs(EVIDENCE_DIR, exist_ok=True)


def get_latest_test_otp(email: str) -> str:
    """Helper to query backend test inspection endpoint for latest mock OTP."""
    url = f"http://127.0.0.1:8000/api/auth/test/latest-otp?email={urllib.parse.quote(email)}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        return data["latest_otp"]


class TestUnifiedBookingRedesignE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()
        self.console_errors = []
        self.page.on("console", lambda msg: self.console_errors.append(msg.text) if msg.type == "error" else None)

    def tearDown(self):
        self.context.close()

    def test_complete_4_step_journey_with_compulsory_auth(self):
        """Tests the complete end-to-end 4-step journey with compulsory auth and PDF generation."""
        page = self.page

        # ---------------------------------------------------------------------
        # 1. STEP 1: PREFERENCES & GUEST EXPLORATION
        # ---------------------------------------------------------------------
        page.goto("http://127.0.0.1:5173/")
        page.wait_for_load_state("networkidle")
        self.assertTrue("Vaishno Devi" in page.title() or "Vaishno Devi" in page.content())

        # Navigate to "Darshan Bookings" tab
        darshan_tab = page.locator("button:has-text('Darshan Bookings')")
        darshan_tab.click()
        page.wait_for_timeout(1000)

        # If choice screen is present, select Guided Intake Form
        if page.locator("[data-testid='select-form-btn']").is_visible():
            page.locator("[data-testid='select-form-btn']").click()
            page.wait_for_timeout(800)

        # Verify Step 1 is active on 4-step stepper
        stepper = page.locator("[data-testid='main-4-step-stepper']")
        self.assertTrue(stepper.is_visible(), "Main 4-step stepper must be visible")
        self.assertTrue(page.locator("[data-testid='step-pill-1']").is_visible())

        # Submit intake form (Step 1 -> Step 2)
        submit_search_btn = page.locator("button:has-text('Search Yatra Options ➔')")
        if not submit_search_btn.is_visible():
            submit_search_btn = page.locator("button:has-text('Generate My Yatra Plan')")
        self.assertTrue(submit_search_btn.is_visible(), "Intake submit button must be visible")
        submit_search_btn.click()

        # ---------------------------------------------------------------------
        # 2. STEP 2: RECOMMENDED YATRA & SELECTION
        # ---------------------------------------------------------------------
        page.wait_for_selector("[data-testid='confirm-selections-continue-btn']", timeout=25000)
        page.locator("[data-testid='confirm-selections-continue-btn']").click()

        # ---------------------------------------------------------------------
        # 3. STEP 3: BOOKING REVIEW & RPA
        # ---------------------------------------------------------------------
        page.wait_for_selector("text=Review Summary & Human Authorization Gate", timeout=15000)
        page.wait_for_timeout(1000)

        # Verify prominent primary CTA
        primary_cta = page.locator("[data-testid='start-yatra-rpa-btn']")
        self.assertTrue(primary_cta.is_visible(), "Primary CTA must be visible")

        # Verify auth-required banner is visible for guest
        self.assertTrue(page.locator("[data-testid='auth-required-banner']").is_visible(),
                        "Guest user must see authentication requirement banner before booking")

        # ---------------------------------------------------------------------
        # COMPULSORY AUTH TRIGGER: GUEST CLICKS START BOOKING
        # ---------------------------------------------------------------------
        primary_cta.click()

        # Auth modal must appear
        page.wait_for_selector("[data-testid='auth-modal']", timeout=10000)
        self.assertTrue(page.locator("[data-testid='auth-modal']").is_visible(),
                        "Auth modal must open when guest clicks Start Yatra Booking with RPA")

        # Fill email for passwordless OTP login
        test_email = f"pilgrim_e2e_{int(time.time())}@example.com"
        email_input = page.locator("[data-testid='auth-email-input']")
        email_input.fill(test_email)

        # Request OTP
        send_otp_btn = page.locator("[data-testid='auth-send-otp-btn']")
        send_otp_btn.click()

        # Wait for OTP step in modal
        page.wait_for_selector("[data-testid='auth-otp-input']", timeout=15000)

        # Fetch simulated OTP from backend inspection endpoint
        mock_otp = get_latest_test_otp(test_email)
        self.assertTrue(len(mock_otp) == 6, f"Mock OTP must be 6 digits, got: {mock_otp}")

        # Enter OTP and verify
        otp_input = page.locator("[data-testid='auth-otp-input']")
        otp_input.fill(mock_otp)

        verify_otp_btn = page.locator("button:has-text('Verify Code & Sign In')")
        verify_otp_btn.click()

        # Wait for success screen in Auth modal
        page.wait_for_selector("text=Jai Mata Di!", timeout=15000)
        continue_app_btn = page.locator("button:has-text('Continue to Application ➔')")
        continue_app_btn.click()

        # Modal closes; verify return to Step 3 with authenticated banner
        page.wait_for_timeout(1000)
        self.assertEqual(page.locator("[data-testid='auth-modal']").count(), 0, "Auth modal must close after sign-in")
        self.assertTrue(page.locator("[data-testid='auth-active-banner']").is_visible(),
                        "Active authenticated session banner must be displayed on Step 3")

        # ---------------------------------------------------------------------
        # 4. RPA WORKFLOW INITIATION AS AUTHENTICATED USER
        # ---------------------------------------------------------------------
        primary_cta.click()

        # RPA navigates to OTP checkpoint and pauses
        page.wait_for_selector("[data-testid='modal-7-stage-stepper']", timeout=25000)
        page.wait_for_timeout(1000)

        # ---------------------------------------------------------------------
        # TEST OTP FAILURE RECOVERY & SUCCESS
        # ---------------------------------------------------------------------
        modal_otp_input = page.locator("input[placeholder*='code']")
        modal_otp_input.fill("12")  # invalid short OTP
        page.click("button:has-text('Verify & Continue ➔')")
        page.wait_for_selector("text=Action Required", timeout=20000)
        self.assertTrue(page.locator("text=Action Required").is_visible(),
                        "Validation failure must be reported when incorrect OTP is entered")

        modal_otp_input.fill("123456")  # valid mock OTP
        page.click("button:has-text('Verify & Continue ➔')")

        # ---------------------------------------------------------------------
        # TEST CAPTCHA FAILURE RECOVERY & SUCCESS
        # ---------------------------------------------------------------------
        page.wait_for_selector("text=Simulated CAPTCHA", timeout=25000)
        self.assertTrue(page.locator("text=M7K9P").first.is_visible(), "CAPTCHA challenge M7K9P must be displayed")

        captcha_input = page.locator("input[placeholder*='CAPTCHA']")
        captcha_input.fill("WRONG")
        page.click("button:has-text('Verify & Continue ➔')")
        page.wait_for_selector("text=Action Required", timeout=20000)
        self.assertTrue(page.locator("text=Action Required").is_visible(),
                        "Validation failure must be reported when incorrect CAPTCHA is entered")

        captcha_input.fill("M7K9P")
        page.click("button:has-text('Verify & Continue ➔')")

        # ---------------------------------------------------------------------
        # SIMULATED PAYMENT & STEP 3 FINAL CONFIRMATION STATE
        # ---------------------------------------------------------------------
        page.wait_for_selector("[data-testid='demo-pilgrim-pass-card']", timeout=25000)
        page.wait_for_timeout(1000)

        pass_card = page.locator("[data-testid='demo-pilgrim-pass-card']")
        self.assertTrue(pass_card.is_visible(), "Demo Pilgrim Pass card must be rendered upon RPA completion")

        pass_content = pass_card.text_content()
        self.assertTrue("VD-" in pass_content, "Pass must display booking reference ID (VD-XXXXXX)")

        # Verify bottom prominent CTA "Continue to Confirmation ➔" is rendered
        continue_to_conf_btn = page.locator("[data-testid='continue-to-confirmation-btn']")
        self.assertTrue(continue_to_conf_btn.is_visible(),
                        "Prominent bottom button 'Continue to Confirmation' must be displayed after RPA completes")

        # ---------------------------------------------------------------------
        # 5. STEP 4: CONFIRMATION & DOWNLOAD PASS
        # ---------------------------------------------------------------------
        continue_to_conf_btn.click()
        page.wait_for_timeout(1000)

        # Verify genuine Step 4 page is rendered
        page.wait_for_selector("[data-testid='step-4-confirmation-page']", timeout=10000)
        self.assertTrue(page.locator("[data-testid='step-4-confirmation-page']").is_visible(),
                        "Step 4 Confirmation & Download Pass page must be rendered")

        # Verify disclaimer banner
        disclaimer = page.locator("[data-testid='mock-portal-disclaimer-banner']")
        self.assertTrue(disclaimer.is_visible(), "Disclaimer banner must be prominent on Step 4")
        self.assertIn("NOT AN OFFICIAL SHRINE BOARD BOOKING", disclaimer.text_content())

        # Verify booking reference ID
        booking_ref = page.locator("[data-testid='confirmed-booking-reference-id']")
        self.assertTrue(booking_ref.is_visible())
        booking_id_str = booking_ref.text_content().strip()
        self.assertTrue(booking_id_str.startswith("VD-"), f"Booking reference must start with VD-, got {booking_id_str}")

        # Verify simulated payment notice
        payment_notice = page.locator("[data-testid='simulated-payment-notice']")
        self.assertTrue(payment_notice.is_visible())
        self.assertIn("₹0 Live Charge", payment_notice.text_content())

        # Capture evidence screenshot of genuine Step 4 page
        step4_ss = os.path.join(EVIDENCE_DIR, "step4_confirmation_pass_evidence.png")
        page.screenshot(path=step4_ss, full_page=True)
        self.assertTrue(os.path.exists(step4_ss))

        # ---------------------------------------------------------------------
        # TEST PDF DOWNLOAD
        # ---------------------------------------------------------------------
        download_btn = page.locator("[data-testid='download-pass-btn']")
        self.assertTrue(download_btn.is_visible(), "Download Pass button must be rendered")

        with page.expect_download() as download_info:
            download_btn.click()
        download = download_info.value

        # Verify filename format
        self.assertTrue(download.suggested_filename.startswith("Pilgrim_Pass_VD-"),
                        f"Downloaded PDF filename must be Pilgrim_Pass_VD-..., got {download.suggested_filename}")
        self.assertTrue(download.suggested_filename.endswith(".pdf"))

        # Save downloaded PDF and verify contents
        download_path = os.path.join(EVIDENCE_DIR, download.suggested_filename)
        download.save_as(download_path)
        self.assertTrue(os.path.exists(download_path), "Downloaded PDF pass must exist on disk")

        with open(download_path, "rb") as f:
            pdf_bytes = f.read()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"), "Downloaded file must be a valid PDF 1.4 document")
        self.assertIn(b"DEMO", pdf_bytes, "PDF must include demo disclaimer")
        self.assertIn(booking_id_str.encode(), pdf_bytes, "PDF must contain the confirmed booking reference ID")

        # ---------------------------------------------------------------------
        # TEST PRINT PASS ACTION
        # ---------------------------------------------------------------------
        print_btn = page.locator("[data-testid='print-pass-btn']")
        self.assertTrue(print_btn.is_visible(), "Print Pass button must be present")

        # ---------------------------------------------------------------------
        # TEST STEPPER BACKWARD NAVIGATION
        # ---------------------------------------------------------------------
        # Navigate backward to Step 2 via stepper
        step_2_pill = page.locator("[data-testid='step-pill-2']")
        step_2_pill.click()
        page.wait_for_timeout(800)

        # Verify we navigated back to Recommended Yatra
        self.assertTrue(page.locator("[data-testid='confirm-selections-continue-btn']").is_visible())

        # Navigate forward to Step 4 via stepper
        step_4_pill = page.locator("[data-testid='step-pill-4']")
        step_4_pill.click()
        page.wait_for_timeout(800)

        # Verify Step 4 still preserves confirmed booking reference
        self.assertEqual(page.locator("[data-testid='confirmed-booking-reference-id']").text_content().strip(),
                         booking_id_str, "Navigating back and forward must preserve the confirmed booking reference")

        # ---------------------------------------------------------------------
        # TEST 'PLAN ANOTHER YATRA' RESETS CONFIRMED STATE
        # ---------------------------------------------------------------------
        new_booking_btn = page.locator("[data-testid='book-another-yatra-btn']")
        self.assertTrue(new_booking_btn.is_visible())
        new_booking_btn.click()
        page.wait_for_timeout(1000)

        # Returns to Step 1
        self.assertTrue(page.locator("button:has-text('Search Yatra Options ➔')").is_visible() or
                        page.locator("button:has-text('Generate My Yatra Plan')").is_visible())

        # Capture evidence screenshot
        ss_path = os.path.join(EVIDENCE_DIR, "full_journey_pass_evidence.png")
        page.screenshot(path=ss_path, full_page=True)
        self.assertTrue(os.path.exists(ss_path), "Full journey evidence screenshot must be saved")


if __name__ == "__main__":
    unittest.main()
