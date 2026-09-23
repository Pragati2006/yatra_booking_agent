"""
agents/rpa_agent.py
Playwright-based Robotic Process Automation (RPA) Agent.
Demonstrates automated booking form filling and verification in a safe,
mock environment. Does NOT interact with real payment portals, OTP, or CAPTCHA.
"""

import os
import time
import tempfile
from playwright.sync_api import sync_playwright


MOCK_PORTAL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Vaishno Devi Yatra - RPA Mock Booking Portal</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #FDF6EC; margin: 0; padding: 30px; color: #3B1F1F; }
        .card { background: white; border-radius: 16px; padding: 24px; max-width: 600px; margin: 0 auto; box-shadow: 0 8px 24px rgba(110,20,35,0.15); border: 2px solid #E8C874; }
        h2 { color: #6E1423; margin-top: 0; }
        .field { margin-bottom: 16px; }
        label { display: block; font-weight: bold; margin-bottom: 6px; font-size: 0.9rem; color: #8A6857; }
        input, select { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #CCC; box-sizing: border-box; font-size: 1rem; }
        .btn { background: linear-gradient(135deg, #C2374A, #6E1423); color: white; border: none; padding: 14px 20px; font-size: 1rem; font-weight: bold; border-radius: 10px; width: 100%; cursor: pointer; margin-top: 10px; }
        .success { background: #E8F8F5; border: 2px solid #2ECC71; color: #145A32; padding: 16px; border-radius: 10px; display: none; margin-top: 20px; text-align: center; }
        .badge { background: #E8C874; color: #3B1F1F; font-size: 0.8rem; font-weight: bold; padding: 4px 8px; border-radius: 6px; display: inline-block; }
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">🤖 Playwright RPA Automated Booking Demo</span>
        <h2>🛕 Safe Mock Booking Checkout</h2>
        <form id="bookingForm" onsubmit="event.preventDefault(); submitBooking();">
            <div class="field">
                <label for="userName">Pilgrim Name</label>
                <input type="text" id="userName" name="userName" required placeholder="Enter pilgrim name">
            </div>
            <div class="field">
                <label for="paxCount">Number of Pilgrims</label>
                <input type="number" id="paxCount" name="paxCount" required min="1">
            </div>
            <div class="field">
                <label for="transportInfo">Transport Choice</label>
                <input type="text" id="transportInfo" name="transportInfo">
            </div>
            <div class="field">
                <label for="yatraSlot">Yatra Darshan Slot</label>
                <input type="text" id="yatraSlot" name="yatraSlot">
            </div>
            <div class="field">
                <label for="totalAmount">Total Amount (₹)</label>
                <input type="text" id="totalAmount" name="totalAmount">
            </div>
            <div class="field">
                <label for="paymentMethod">Mock Payment Token</label>
                <input type="text" id="paymentMethod" name="paymentMethod" value="MOCK_TEST_AUTH_PASSED">
            </div>

            <button type="button" id="submitBtn" onclick="submitBooking()" class="btn">Confirm & Authorize Mock Booking</button>
        </form>


        <div id="confirmation" class="success">
            <h3>✅ Booking Confirmed via RPA!</h3>
            <p>Confirmation ID: <strong id="outBookingId"></strong></p>
            <p>Status: <strong>CONFIRMED (Mock)</strong></p>
            <p style="font-size: 0.85rem; color: #27AE60;">🙏 Wishing you a blessed and peaceful yatra!</p>
        </div>
    </div>

    <script>
        function submitBooking() {
            document.getElementById('bookingForm').style.display = 'none';
            const bookingId = "VD-RPA-" + Math.floor(100000 + Math.random() * 900000);
            document.getElementById('outBookingId').textContent = bookingId;
            document.getElementById('confirmation').style.display = 'block';
        }
    </script>
</body>
</html>
"""


def execute_playwright_mock_booking(user_name: str, pax_count: int, transport_text: str, slot_text: str, total_price: float, headless: bool = True) -> dict:
    """Runs a Playwright RPA automation step against a temporary mock booking form page.
    Returns details of execution including screenshot path and booking confirmation status."""
    temp_dir = tempfile.gettempdir()
    html_path = os.path.join(temp_dir, "yatra_mock_portal.html")
    screenshot_path = os.path.join(temp_dir, "rpa_booking_confirmation.png")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(MOCK_PORTAL_HTML)

    html_url = f"file:///{html_path.replace(os.sep, '/')}"

    rpa_result = {
        "status": "FAILED",
        "booking_id": None,
        "screenshot_path": None,
        "logs": [],
    }

    try:
        with sync_playwright() as p:
            rpa_result["logs"].append("Launching Playwright Chromium browser...")
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()

            rpa_result["logs"].append(f"Navigating to safe mock portal: {html_url}")
            page.goto(html_url)

            # Fill passenger details via RPA selectors
            rpa_result["logs"].append("Filling pilgrim name and passenger count via RPA...")
            page.fill("#userName", user_name)
            page.fill("#paxCount", str(pax_count))
            page.fill("#transportInfo", transport_text)
            page.fill("#yatraSlot", slot_text)
            page.fill("#totalAmount", f"₹{total_price}")

            time.sleep(0.5)

            rpa_result["logs"].append("Submitting form via RPA trigger...")
            page.click("#submitBtn")

            page.wait_for_selector("#confirmation", state="visible", timeout=5000)

            booking_id = page.text_content("#outBookingId")
            rpa_result["logs"].append(f"RPA Mock Booking completed successfully. Booking ID: {booking_id}")

            page.screenshot(path=screenshot_path)
            rpa_result["status"] = "SUCCESS"
            rpa_result["booking_id"] = booking_id
            rpa_result["screenshot_path"] = screenshot_path

            browser.close()

    except Exception as e:
        rpa_result["logs"].append(f"RPA execution error: {str(e)}")
        rpa_result["error"] = str(e)

    return rpa_result
