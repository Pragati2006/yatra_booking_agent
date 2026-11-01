import os
import tempfile

from playwright.sync_api import sync_playwright


# ============================================================
# MOCK YATRA BOOKING PORTAL
# ============================================================

MOCK_PORTAL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Vaishno Devi Yatra - Week 4 RPA Test</title>
</head>

<body>

    <h1>Vaishno Devi Yatra Booking</h1>

    <form id="bookingForm">

        <label for="userName">Pilgrim Name</label>
        <input
            type="text"
            id="userName"
            name="userName"
            placeholder="Enter pilgrim name"
        >

        <label for="paxCount">Number of Pilgrims</label>
        <input
            type="number"
            id="paxCount"
            name="paxCount"
        >

        <label for="transportInfo">Transport Choice</label>
        <input
            type="text"
            id="transportInfo"
            name="transportInfo"
        >

        <label for="yatraSlot">Yatra Darshan Slot</label>
        <input
            type="text"
            id="yatraSlot"
            name="yatraSlot"
        >

        <button type="button" id="submitBtn">
            Confirm Booking
        </button>

    </form>

    <div id="confirmation" style="display:none;">
        <h2>Booking Confirmed</h2>
        <p id="confirmationMessage"></p>
    </div>

    <script>
        document.getElementById("submitBtn").addEventListener("click", function() {

            const name = document.getElementById("userName").value;

            document.getElementById("bookingForm").style.display = "none";

            document.getElementById("confirmationMessage").textContent =
                "Booking successfully processed for " + name;

            document.getElementById("confirmation").style.display = "block";
        });
    </script>

</body>
</html>
"""


# ============================================================
# WEEK 4 PLAYWRIGHT TEST
# ============================================================

def run_week4_test():

    temp_dir = tempfile.gettempdir()

    html_path = os.path.join(
        temp_dir,
        "week4_yatra_portal.html"
    )

    screenshot_path = os.path.join(
        temp_dir,
        "week4_playwright_confirmation.png"
    )

    # Create temporary mock portal
    with open(html_path, "w", encoding="utf-8") as file:
        file.write(MOCK_PORTAL_HTML)

    html_url = "file:///" + html_path.replace(os.sep, "/")

    print("=" * 70)
    print("WEEK 4 - PLAYWRIGHT RPA TEST")
    print("=" * 70)

    with sync_playwright() as p:

        # ----------------------------------------------------
        # 1. Launch browser
        # ----------------------------------------------------

        print("\n[1] Launching Chromium...")

        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        print("    Browser launched successfully.")

        # ----------------------------------------------------
        # 2. Navigate to portal
        # ----------------------------------------------------

        print("\n[2] Navigating to Yatra booking portal...")

        page.goto(html_url)

        print("    Page loaded:", page.title())

        # ----------------------------------------------------
        # 3. Verify page
        # ----------------------------------------------------

        print("\n[3] Verifying page content...")

        heading = page.locator("h1")

        assert heading.is_visible()

        assert "Vaishno Devi Yatra Booking" in heading.inner_text()

        print("    Page verification: PASSED")

        # ----------------------------------------------------
        # 4. Resilient locators
        # ----------------------------------------------------

        print("\n[4] Testing form locators...")

        name_input = page.locator("#userName")
        pax_input = page.locator("#paxCount")
        transport_input = page.locator("#transportInfo")
        slot_input = page.locator("#yatraSlot")
        submit_button = page.locator("#submitBtn")

        assert name_input.is_visible()
        assert pax_input.is_visible()
        assert transport_input.is_visible()
        assert slot_input.is_visible()
        assert submit_button.is_visible()

        print("    All required elements located: PASSED")

        # ----------------------------------------------------
        # 5. Fill booking form
        # ----------------------------------------------------

        print("\n[5] Filling booking details...")

        name_input.fill("Pragati")
        pax_input.fill("4")
        transport_input.fill("Train")
        slot_input.fill("Morning")

        print("    Form filling: PASSED")

        # ----------------------------------------------------
        # 6. Verify entered values
        # ----------------------------------------------------

        print("\n[6] Verifying entered values...")

        assert name_input.input_value() == "Pragati"
        assert pax_input.input_value() == "4"
        assert transport_input.input_value() == "Train"
        assert slot_input.input_value() == "Morning"

        print("    Input verification: PASSED")

        # ----------------------------------------------------
        # 7. Submit booking
        # ----------------------------------------------------

        print("\n[7] Submitting booking...")

        submit_button.click()

        # ----------------------------------------------------
        # 8. Verify confirmation
        # ----------------------------------------------------

        print("\n[8] Verifying booking confirmation...")

        confirmation = page.locator("#confirmation")

        confirmation.wait_for(
            state="visible",
            timeout=5000
        )

        assert confirmation.is_visible()

        message = page.locator("#confirmationMessage").inner_text()

        assert "Pragati" in message

        print("    Booking confirmation: PASSED")
        print("    Confirmation:", message)

        # ----------------------------------------------------
        # 9. Take screenshot
        # ----------------------------------------------------

        print("\n[9] Taking screenshot...")

        page.screenshot(
            path=screenshot_path,
            full_page=True
        )

        print("    Screenshot saved:")
        print("   ", screenshot_path)

        # ----------------------------------------------------
        # 10. Close browser
        # ----------------------------------------------------

        browser.close()

    print("\n" + "=" * 70)
    print("WEEK 4 PLAYWRIGHT TEST: SUCCESS")
    print("=" * 70)


if __name__ == "__main__":
    run_week4_test()