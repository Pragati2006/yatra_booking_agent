# Week 6 Assignment: RPA Error Handling and Retry Strategy

## 1. Assignment Objective & Scope

The objective of Week 6 is to implement a robust, enterprise-grade error handling, state validation, and retry strategy for the Playwright-based Robotic Process Automation (RPA) workflow in the **Vaishno Devi Yatra Booking Agent** project.

Specifically, the workflow accomplishes three essential group tasks:
1. **Retry-and-Escalate Engine:** Bounded exponential backoff retries for transient, recoverable browser and network failures.
2. **Post-Action State Validation:** Explicit DOM checks after each browser interaction to guarantee expected state before proceeding.
3. **Pause-and-Handover Triggers:** Structured human handover when encountering non-recoverable anomalies (such as DOM structural degradation, data integrity violations, or exhausted retries).

---

## 2. Recoverable vs. Non-Recoverable Classification

To prevent infinite execution loops and avoid risky automated re-submissions, errors are classified into two strictly differentiated categories:

### A. Recoverable Errors (Eligible for Bounded Retry)
- **Transient Playwright Timeouts (`PlaywrightTimeoutError`):** Brief network delays or delayed DOM rendering where an element takes slightly longer than expected to become visible or attach.
- **Temporary Dynamic Loading Stalls (`RecoverableRPAError`):** Transient loading spinner (`#calendarLoading`) delay during high server latency.
- **Transient State Inconsistencies:** Ephemeral rendering race conditions where a retry with page refresh resolves the state.

### B. Non-Recoverable Errors (Immediate Fail-Fast & Handover)
- **Structural Page Changes (`StructuralPageChangeError`):** Missing core portal elements, renamed selectors (e.g. `#slotsContainer` or `#tabCalendar` missing), or portal DOM restructuring. Retrying cannot fix missing HTML code.
- **Data Integrity Violations (`DataIntegrityError`):** Extracted data violates business schema or physical sanity (e.g., negative remaining capacity, negative slot price, missing mandatory slot IDs).
- **Side-Effect Actions (Booking Submissions):** The Week 4 booking checkout form submission (`#submitBtn`) is **never** retried automatically upon confirmation timeout. Re-submitting an ambiguous booking request could cause duplicate reservations or double charges. Ambiguous states trigger immediate pause-and-handover.
- **Programming & Input Errors:** `TypeError`, `ValueError`, and invalid date formats fail immediately without wasting retry cycles.

---

## 3. Retry Policy & Bounded Backoff Architecture

The bounded retry engine is implemented via `retry_with_backoff` in `agents/rpa_agent.py`:

```python
def retry_with_backoff(
    action_callable: Callable[[int], Any],
    operation_name: str,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    backoff_multiplier: float = 2.0,
    max_delay_seconds: float = 2.0,
    recoverable_exceptions: tuple = (PlaywrightTimeoutError, RecoverableRPAError),
    logs: Optional[List[str]] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Any:
```

### Policy Rules:
1. **Configurable Upper Bound:** Default `max_attempts = 3`. Retries are guaranteed to terminate and cannot loop infinitely.
2. **Exponential Backoff:** Delay between attempt $n$ and $n+1$ follows:
   $$\text{delay} = \min(\text{base\_delay} \times (\text{multiplier})^{n-1}, \text{max\_delay})$$
   - Attempt 1 failure $\rightarrow$ 0.50s delay
   - Attempt 2 failure $\rightarrow$ 1.00s delay
   - Attempt 3 failure $\rightarrow$ Escalates immediately to `create_handover_result()`.
3. **Telemetry & Audit Logging:** Each attempt logs the failed operation name, attempt index, exception type, backoff delay, and whether an additional attempt will occur.
4. **Clean State Reset:** During retries, navigation resets the mock portal page context cleanly.

---

## 4. Post-Action State Validation Checkpoints

State validation helpers verify that the browser and DOM reached the expected state before subsequent actions are dispatched:

| Checkpoint | Helper Function | Validated Condition | Failure Classification |
|---|---|---|---|
| **1. Portal Loaded** | `validate_portal_loaded` | `.card`, `#portalNav`, `#tabBooking`, `#tabCalendar` present in DOM | `StructuralPageChangeError` |
| **2. Calendar Tab Active** | `validate_calendar_tab_active` | `#calendarSection` in DOM, visible, `#tabCalendar` active | `StructuralPageChangeError` / `StateValidationError` |
| **3. Date Input State** | `validate_date_input_state` | `#calendarDate.input_value() == requested_date` | `StateValidationError` |
| **4. Category Filter State** | `validate_category_filter_state` | `#slotCategoryFilter.input_value() == expected_category` | `StateValidationError` |
| **5. Calendar Readiness** | `validate_calendar_readiness` | `#calendarLoading` hidden AND (`.slot-card` count > 0 OR `#emptyCalendarNotice` visible) | `StructuralPageChangeError` (if container missing) / `StateValidationError` |
| **6. Data Integrity** | `validate_slot_record_integrity` | Non-empty `slot_id`, status $\in$ `[available, full, unavailable]`, capacity $\ge 0$, price $\ge 0.0$ | `DataIntegrityError` |
| **7. Booking Form Readiness** | `validate_booking_form_state` | `#bookingForm` visible, input fields `#userName`, `#paxCount`, `#submitBtn` present | `StructuralPageChangeError` |
| **8. Booking Confirmation** | `validate_booking_confirmation_state` | `#confirmation` visible, `#outBookingId` contains non-empty booking ID | `StateValidationError` |

### Critical Rule on Empty Calendars vs. Structural Failures:
When a requested pilgrimage date has no available slots (e.g. `2026-10-25`), the portal displays `#emptyCalendarNotice`.
`validate_calendar_readiness` explicitly recognizes this legitimate empty state (`return "EMPTY_CALENDAR"`), returning `status="SUCCESS"` with `is_empty=True` and `handover_required=False`. It is **never** misclassified as a structural failure or error.

---

## 5. Pause-and-Handover Workflow

When an unrecoverable failure occurs or bounded retries are exhausted, the workflow halts and invokes `create_handover_result`:

1. **Operation Halted:** The workflow stops immediately before any state mutation can occur.
2. **Safe Diagnostic Screenshot:** Captures a high-resolution screenshot to `tempfile` for human audit. If screenshot capture fails (e.g. disk or GPU issue), the error is logged into `diagnostics["screenshot_capture_error"]` and **never masks or replaces the original exception**.
3. **Resource Cleanup:** Guaranteed browser closure (`browser.close()`) in a `finally` block.
4. **Structured JSON Output:** Returns a machine-readable handover envelope to the caller.

### Handover Result Schema:
```json
{
  "status": "HANDOVER_REQUIRED",
  "handover_required": true,
  "retryable": false,
  "error_category": "STRUCTURAL_CHANGE",
  "failed_operation": "check_yatra_slot_availability",
  "attempt_count": 1,
  "message": "Human intervention required: Calendar section element (#calendarSection) is missing from DOM.",
  "error": "Calendar section element (#calendarSection) is missing from DOM.",
  "screenshot_path": "C:\\Users\\...\\AppData\\Local\\Temp\\rpa_availability_2026-10-20.png",
  "diagnostics": {
    "requested_date": "2026-10-20",
    "category": null
  },
  "logs": [
    "Launching Playwright Chromium browser instance...",
    "Navigating to mock portal URL: file:///...",
    "Portal root structure and navigation tabs successfully validated.",
    "Waiting for availability calendar tab locator (#tabCalendar)...",
    "[NON_RECOVERABLE] Non-recoverable failure in 'check_yatra_slot_availability' on attempt 1: StructuralPageChangeError: Calendar section element (#calendarSection) is missing from DOM.",
    "Audit handover screenshot captured: C:\\Users\\...",
    "Playwright browser instance closed cleanly."
  ]
}
```

---

## 6. Resource Cleanup & Safeguards Verification

- **Browser Lifecycles:** Guaranteed cleanup via `try ... finally: browser.close()`. Verified across both successful navigation runs and catastrophic failure simulations.
- **Read-Only Invariant:** Availability checking endpoints (`POST /api/yatra/rpa/availability`) do not mutate booking plan versions, do not touch session authorization records, and do not trigger financial or booking executions.
- **Side-Effect Protection:** In `execute_playwright_mock_booking`, form submissions are never retried. Ambiguous confirmation timeouts trigger handover to prevent duplicate bookings.

---

## 7. Automated Test Suite (`tests/test_rpa_error_handling_week6.py`)

A 14-scenario automated test suite was developed and executed:

| Test ID | Scenario | Result | Duration |
|---|---|---|---|
| `test_01` | Recoverable timeout succeeds on attempt 2 after backoff | **PASSED** | 0.15s |
| `test_02` | Persistent timeout exhausts all 3 attempts and escalates to handover | **PASSED** | 0.28s |
| `test_03` | Non-recoverable error fails fast on attempt 1 without retry | **PASSED** | 0.05s |
| `test_04` | State validation succeeds across all checkpoints on standard portal | **PASSED** | 0.85s |
| `test_05` | State validation detects missing required selector (`.card`) | **PASSED** | 0.42s |
| `test_06` | Legitimate empty availability day (`2026-10-25`) returns `SUCCESS` with `is_empty=True` | **PASSED** | 0.88s |
| `test_07` | Changed page structure (missing `#calendarSection`) triggers handover | **PASSED** | 0.82s |
| `test_08` | Malformed slot data (negative capacity / price) triggers `DataIntegrityError` handover | **PASSED** | 0.86s |
| `test_09` | Browser cleanup verified cleanly in both success and failure cases | **PASSED** | 1.68s |
| `test_10` | Screenshot capture failure does not mask primary exception | **PASSED** | 0.02s |
| `test_11` | Retry limits strictly terminate and prevent infinite loops | **PASSED** | 0.06s |
| `test_12` | Week 4 mock booking workflow remains functional with confirmation ID | **PASSED** | 1.45s |
| `test_13` | Week 5 availability extraction remains functional with 8 structured slots | **PASSED** | 0.89s |
| `test_14` | Booking authorization and plan-version safeguards remain completely intact | **PASSED** | 0.92s |

**Total Suite Result:** 14/14 tests passed in 10.75s.

---

## 8. Limitations of Local Mock Portal

- **Sandbox Scope:** The automation operates strictly against a local, sandboxed HTML mock portal (`yatra_mock_portal.html`) loaded from temporary files.
- **No Live External Scraping:** The system does not automate or scrape the real Shri Mata Vaishno Devi Shrine Board (`maavaishnodevi.org`) website, IRCTC, or commercial payment gateways.
- **Security Boundaries:** Real security controls (CAPTCHA, SMS OTP, biometric authentication, live banking 3D Secure gates) are never bypassed.
