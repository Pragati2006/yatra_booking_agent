# Week 5 Assignment: RPA Workflow — Availability Checking and Data Extraction

## 1. Assignment Objective

The primary objective of Week 5 is to design and implement an automated, robust Robotic Process Automation (RPA) workflow using **Playwright** that:
1. **Navigates to an availability calendar** within the yatra booking portal.
2. **Extracts structured slot availability data** including dates, timings, categories, prices, remaining capacities, and normalized availability statuses.
3. **Synchronizes reliably with dynamic web elements** using Playwright's explicit waits rather than arbitrary fixed sleeps.
4. **Executes autonomously without manual intervention** while guaranteeing resource cleanup and maintaining strict security and ethical boundaries (i.e. checking availability is strictly read-only and never bypasses human authorization or auto-confirms bookings).

---

## 2. RPA Architecture & Navigation Logic

### Architecture Overview
The workflow integrates directly with the existing project's multi-agent architecture and local mock portal:
- **Mock Portal (`yatra_mock_portal.html`):** Generated in `agents/rpa_agent.py`, featuring a dual-tab architecture:
  - Tab 1 (`#tabBooking`): Week 4 safe mock checkout form (`#userName`, `#paxCount`, `#transportInfo`, `#yatraSlot`, `#submitBtn`, `#confirmation`).
  - Tab 2 (`#tabCalendar` / `#navAvailabilityCalendar`): Week 5 Darshan Slot Availability Calendar.
- **RPA Agent (`agents/rpa_agent.py`):** Houses the Playwright automation functions:
  - `navigate_to_availability_calendar()`
  - `extract_slot_availability()`
  - `check_yatra_slot_availability()`
- **Coordinator & API Integration:**
  - `agents/coordinator.py`: Exposes `check_slot_availability_rpa()`.
  - `backend/routes/yatra.py`: Exposes `POST /api/yatra/rpa/availability`.
  - `frontend/src/services/api.js`: Exposes `checkRPAAvailability()`.

### Navigation Workflow & Selectors
1. **Browser Initialization:** Launches a headless Chromium browser instance via Playwright `sync_playwright()`.
2. **Tab Navigation:** Locates `#tabCalendar` using `page.locator("#tabCalendar")`, waits for visibility, and clicks the tab.
3. **Calendar Section Preparation:** Explicitly waits for `#calendarSection` to be visible (`page.locator("#calendarSection").wait_for(state="visible")`).
4. **Parameter Injection:**
   - Date: `#calendarDate` (e.g. `2026-10-20`).
   - Category: `#slotCategoryFilter` (e.g. `Normal Darshan`, `VIP Darshan`, `Helicopter Darshan`, or All).
5. **Search Trigger:** Clicks `#btnCheckAvailability`.

---

## 3. Dynamic Element Handling & Explicit Waits

Rather than relying on brittle, fixed sleeps (`time.sleep`), the workflow employs Playwright's native explicit waits and locator synchronization:
1. **Loading State Synchronization:**
   - When `#btnCheckAvailability` is clicked, the portal renders a dynamic loading indicator (`#calendarLoading`).
   - The RPA script synchronizes using:
     ```python
     page.wait_for_selector("#calendarLoading", state="hidden", timeout=timeout_ms)
     ```
   - This ensures the script only proceeds once the dynamic slot calculation or fetch is completely resolved.
2. **Container Visibility:**
   - The script explicitly waits for the results container:
     ```python
     page.wait_for_selector("#slotsContainer", state="visible", timeout=timeout_ms)
     ```
3. **Delayed Rendering Resilience:**
   - Verified against simulated network and rendering delays up to 600ms without timing out or failing.

---

## 4. Structured Data Extraction

The extraction function `extract_slot_availability(page, requested_date)` inspects the rendered DOM using Playwright locators:
- Locates all `.slot-card` elements.
- Extracts attributes and text contents:
  - `slot_id`: from `.slot-id` or `data-slot-id`
  - `yatra_date`: from `data-date`
  - `slot_name`: from `.slot-category` (e.g., `Normal Darshan`, `VIP Darshan`, `Helicopter Darshan`)
  - `time`: from `.slot-time` (e.g., `06:00`, `09:00`, `12:00`, `15:00`, `18:00`)
  - `session`: from `.slot-session` (e.g., `Morning Aarti & Darshan`, `Evening VIP Aarti`)
  - `availability_status`: normalized into three canonical categories:
    - `available`: seats available > 0
    - `full`: seats available == 0
    - `unavailable`: closed, suspended, or maintenance
  - `remaining_capacity`: integer parsed from `data-capacity` or `.slot-capacity`
  - `price`: float parsed from `.slot-price`
  - `retrieved_at`: ISO 8601 timestamp

### Example Structured Output
```json
{
  "status": "SUCCESS",
  "date": "2026-10-20",
  "category_filter": null,
  "total_slots": 8,
  "available_count": 5,
  "full_count": 2,
  "unavailable_count": 1,
  "is_empty": false,
  "extracted_at": "2026-10-27T22:36:50.123456",
  "slots": [
    {
      "slot_id": "SLOT-101",
      "yatra_date": "2026-10-20",
      "slot_name": "Normal Darshan",
      "time": "06:00",
      "session": "Morning Aarti & Darshan",
      "availability_status": "available",
      "remaining_capacity": 220,
      "price": 0.0,
      "retrieved_at": "2026-10-27T22:36:50.124000"
    },
    {
      "slot_id": "SLOT-103",
      "yatra_date": "2026-10-20",
      "slot_name": "Normal Darshan",
      "time": "12:00",
      "session": "Afternoon Session",
      "availability_status": "full",
      "remaining_capacity": 0,
      "price": 0.0,
      "retrieved_at": "2026-10-27T22:36:50.124500"
    },
    {
      "slot_id": "SLOT-108",
      "yatra_date": "2026-10-20",
      "slot_name": "Helicopter Darshan",
      "time": "15:00",
      "session": "Afternoon Helicopter Flight 2",
      "availability_status": "unavailable",
      "remaining_capacity": 0,
      "price": 4640.0,
      "retrieved_at": "2026-10-27T22:36:50.125000"
    }
  ]
}
```

---

## 5. Error Handling & Edge Cases

1. **Empty Calendar Detection:**
   - If no slots exist for the requested date, `#emptyCalendarNotice` becomes visible.
   - The extractor distinguishes this from a network error, returning `status="SUCCESS", is_empty=True, total_slots=0, slots=[]`.
2. **Missing Elements & Timeouts:**
   - If expected selectors are missing from the DOM or corrupted, the workflow catches `PlaywrightTimeoutError` and returns `status="TIMEOUT"` with logs, avoiding uncaught process crashes.
3. **Malformed / Incomplete Data:**
   - Handles non-numeric prices, missing capacity badges, or empty session names safely with defaults (`remaining_capacity=None`, `price=0.0`).
4. **Guaranteed Resource Cleanup:**
   - Browser lifecycles are wrapped in `try ... finally: browser.close()`.
   - Browser processes are terminated even when unhandled exceptions occur.

---

## 6. Verification & Automated Test Results

All 10 required evaluation scenarios were implemented in [tests/test_rpa_availability_week5.py](file:///c:/Users/praga/OneDrive/Documents/Minor%20Project/yatra-booking-agent/tests/test_rpa_availability_week5.py) and executed:

| Scenario # | Description | Execution Result |
| :---: | :--- | :---: |
| **1** | Successful navigation to availability calendar | **PASSED** |
| **2** | Successful extraction of multiple slots with complete fields | **PASSED** |
| **3** | Accurate categorization of `available`, `full`, and `unavailable` statuses | **PASSED** |
| **4** | Handling a requested date with no available slots (all booked/full) | **PASSED** |
| **5** | Handling an empty calendar (date with 0 slots) | **PASSED** |
| **6** | Dynamic synchronization during delayed rendering (600ms simulated delay) | **PASSED** |
| **7** | Graceful error handling for missing calendar elements or timeouts | **PASSED** |
| **8** | Resilience against malformed or incomplete slot data | **PASSED** |
| **9** | Guaranteed browser cleanup after both successful runs and failure cases | **PASSED** |
| **10** | Regression verification of Week 4 booking checkout and FastAPI endpoint | **PASSED** |

**Overall Suite Result:** `10/10 PASSED` in 59.003s.

---

## 7. Limitations & Ethical Sandbox Boundaries

1. **Local Mock Portal Sandbox:** All calendar rendering, status evaluations, and seat counts operate strictly within an isolated local mock HTML portal (`yatra_mock_portal.html`) fed by realistic project CSV datasets.
2. **No Live Portal Automation:** The RPA agent does not interact with the official Shri Mata Vaishno Devi Shrine Board (SMVDSB) production servers, Indian Railways (IRCTC), or airline portals.
3. **No Security Bypass:** The workflow does not bypass CAPTCHA, OTP, biometric, or login barriers.
4. **Read-Only Availability:** Availability checking is purely informational and does not confirm bookings, allocate tickets, or bypass the mandatory Human-in-the-Loop authorization gate.
