# Week 10: Data Privacy and Structured Logging Implementation
## Project: Tourism GPT with RPA — Maa Vaishno Devi Yatra Booking Agent

---

## Executive Summary

This document describes the technical architecture, implementation details, and verification results of the **Data Privacy, Sensitive Input Masking, and Transparent Structured Logging System** implemented in Week 10 of the **Maa Vaishno Devi Yatra Booking Agent** project.

The system ensures that:
1. Sensitive pilgrim inputs (emails, 6-digit verification OTPs, session tokens, API keys, phone numbers, and full names) are systematically classified and masked across both backend logging streams and frontend user interfaces.
2. The logging architecture provides transparent, traceable, and structured observability for automated RPA workflows, LangChain agent tool invocations, and authentication operations without leaking confidential data or internal stack traces.
3. Technical data protection safeguards aligned with the data minimization and security principles of the **Digital Personal Data Protection (DPDP) Act 2023** are implemented across all user-facing and backend flows.

---

## 1. Sensitive Data Classification

Not all data collected by a pilgrimage assistant is equally confidential. To ensure operational observability without compromising privacy, user data is categorized into four distinct sensitivity tiers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             DATA SENSITIVITY CLASSIFICATION                            │
├─────────────┬────────────────────────────────┬──────────────────────────┬──────────────┤
│ Tier        │ Data Elements                  │ Logging Treatment        │ Storage Form │
├─────────────┼────────────────────────────────┼──────────────────────────┼──────────────┤
│ **TIER 1**  │ • 6-Digit Verification OTP     │ NEVER LOGGED             │ Salted HMAC- │
│ (Critical   │ • Session Bearer Tokens        │ Replaced with            │ SHA256 Hash  │
│ Secrets)    │ • Groq API Keys (`gsk_...`)    │ `[REDACTED]`             │ Only         │
│             │ • Passwordless CSRF Secrets    │                          │              │
├─────────────┼────────────────────────────────┼──────────────────────────┼──────────────┤
│ **TIER 2**  │ • Pilgrim Email Address        │ Masked:                  │ Plaintext in │
│ (Personal   │ • Mobile Phone Number          │ `p*****i@example.com`    │ ACID user    │
│ Identifiers)│ • Pilgrim Full Name            │ `98*****210`             │ store for    │
│             │                                │ `P***** S*****`          │ notifications│
├─────────────┼────────────────────────────────┼──────────────────────────┼──────────────┤
│ **TIER 3**  │ • Travel Dates & Durations     │ Included in structured   │ JSON payload │
│ (Operational│ • Requested Darshan Slots      │ log details for          │ in session   │
│ Context)    │ • Destination Selections       │ operational debugging    │ store        │
│             │ • Number of Pilgrims (Pax)     │                          │              │
├─────────────┼────────────────────────────────┼──────────────────────────┼──────────────┤
│ **TIER 4**  │ • Correlation IDs              │ Emitted with all log     │ Ephemeral    │
│ (System     │ • Workflow States & Errors     │ events for distributed   │ context      │
│ Diagnostics)│ • Retry Counters & Outcomes    │ request tracing          │ variables    │
└─────────────┴────────────────────────────────┴──────────────────────────┴──────────────┘
```

---

## 2. Masking Architecture and Utilities (`utils/masking.py`)

Rather than scattering ad-hoc redaction logic across different files, a centralized, reusable masking engine was constructed in `utils/masking.py`.

### Masking Algorithms and Rules

1. **Email Masking (`mask_email`):**
   - Retains the first and last character of the mailbox name, replacing the intermediate characters with asterisks matching the exact length: `local[0] + ('*' * (len(local) - 2)) + local[-1] + '@' + domain`.
   - Short mailbox names (`<= 2` characters) mask all characters except the first.
   - Example: `pragati@example.com` $\rightarrow$ `p*****i@example.com` (5 asterisks for 7 characters).
   - Example: `devotee@gmail.com` $\rightarrow$ `d*****e@gmail.com`.

2. **OTP Redaction (`mask_otp`):**
   - Strictly returns `[REDACTED]` for any non-empty input.
   - Empty or `None` inputs return empty strings.
   - Example: `123456` $\rightarrow$ `[REDACTED]`.

3. **Session Token Redaction (`mask_token`):**
   - Replaces 32-byte hexadecimal and alphanumeric tokens with `[REDACTED]`.
   - Example: `sess_4a8f9c1b7e2d0987...` $\rightarrow$ `[REDACTED]`.

4. **API Key Redaction (`mask_api_key`):**
   - Replaces API secrets with `[REDACTED]`.
   - Example: `gsk_4kM91Lq89v...` $\rightarrow$ `[REDACTED]`.

5. **Phone Number Masking (`mask_phone`):**
   - Retains the first 2 digits and last 3 digits of a 10-digit mobile number, masking the middle 5 digits: `digits[:2] + '*****' + digits[-3:]`.
   - Example: `9876543210` $\rightarrow$ `98*****210`.

6. **Full Name Masking (`mask_name`):**
   - Masks each whitespace-separated name token individually, preserving initial and terminal characters.
   - Example: `Pragati Sharma` $\rightarrow$ `P*****i S****a`.

7. **Recursive Dictionary & Request Metadata Masking (`mask_sensitive_data`):**
   - Deep-traverses nested dictionaries, lists, and tuples.
   - Automatically detects sensitive key names (`email`, `otp`, `token`, `password`, `secret`, `api_key`, `phone`, `auth`) and applies appropriate masking.
   - Non-sensitive operational keys (`date`, `category`, `plan_version`, `status`, `duration`) are preserved intact.

8. **Universal Freeform String Scrubber (`sanitize_log_message`):**
   - Uses compiled regular expressions with negative lookbehinds to scrub secrets and PII embedded inside arbitrary error messages, tracebacks, or external service responses.
   - Groq API keys: `r"\bgsk_[A-Za-z0-9_]{8,}\b"`.
   - MongoDB URIs: `r"mongodb(\+srv)?:\/\/[^:]+:[^@]+@\S+"`.
   - Labeled OTPs: `r"(?i)\b(?:otp|verification[\s_-]?code)[\s:=]+['\"]?(\d{4,8})['\"]?\b"`.
   - Email regex with negative lookbehind `(?<!\*)` prevents re-masking already masked addresses: `r"(?<!\*)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"`.

### Before-and-After Masking Verification

| Input Context | Original Value | Masked Output |
| :--- | :--- | :--- |
| User Email | `pragati@example.com` | `p*****i@example.com` |
| 6-Digit Email OTP | `849201` | `[REDACTED]` |
| Bearer Session Token | `sess_982bfb19d45e4d5` | `[REDACTED]` |
| Groq Cloud Secret | `gsk_abC123XyZ789012345` | `[REDACTED]` |
| Database Connection String | `mongodb+srv://admin:SecretPass123@cluster.mongodb.net` | `mongodb+srv://[REDACTED_AUTH]@cluster.mongodb.net` |
| Mobile Phone | `+91 9812345678` | `98*****678` |
| Pilgrim Name | `Amit Kumar` | `A**t K***r` |
| Nested Request Body | `{"email": "user@test.com", "otp": "654321", "date": "2026-10-20"}` | `{"email": "u**r@test.com", "otp": "[REDACTED]", "date": "2026-10-20"}` |

---

## 3. Structured Logging Architecture (`utils/logger.py`)

To eliminate unstructured and opaque log files, Week 10 introduces a structured logging system built upon Python's standard `logging` library.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              LOGGING ARCHITECTURE OVERVIEW                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                  Application Code                                      │
│        (rpa_agent.py, availability_agent.py, auth_service.py, backend routes)          │
│                                       │                                                │
│                                       ▼                                                │
│                        StructuredEventLogger.log_event()                               │
│            Formats event with timestamp, level, component, operation,                  │
│               correlation_id, error_category, state, outcome, details                  │
│                                       │                                                │
│                                       ▼                                                │
│                             SanitizingFormatter                                        │
│          Applies regex scrubbing & masking to message, args, and exc_info              │
│                                       │                                                │
│                   ┌───────────────────┴───────────────────┐                            │
│                   ▼                                       ▼                            │
│           Console (sys.stdout)                 Log Files (logs/*.log)                  │
│      Color-coded diagnostic output           Persistent structured audit trail         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Standard Structured Log Fields

Every structured log record emitted via `log_event()` contains standard audit fields:

1. **`timestamp`:** ISO-8601 formatted datetime string (`YYYY-MM-DD HH:MM:SS,mmm`).
2. **`level`:** Standard Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
3. **`component`:** The architectural subsystem generating the event (e.g., `rpa_agent`, `agent.availability`, `auth_service`, `api.yatra`).
4. **`operation`:** The specific functional operation in progress (e.g., `RPA_SLOT_EXTRACTION_COMPLETED`, `AGENT_TOOL_SELECTED`, `API_AUTH_VERIFY_OTP`).
5. **`correlation_id`:** Request tracing identifier (`cid:req-xxxxxxxx` or `cid:sys-init`) propagated across async requests via Python `contextvars`.
6. **`error_category`:** Standardized classification of the fault (if applicable), e.g., `RECOVERABLE_RPA_ERROR`, `STRUCTURAL_CHANGE`, `AUTHENTICATION_ERROR`, `RATE_LIMIT`.
7. **`retry_attempt`:** Integer indicating the current attempt number in an automated retry sequence.
8. **`workflow_state`:** RPA or conversation state (e.g., `RUNNING`, `PAUSED`, `HANDOVER_REQUIRED`, `COMPLETED`).
9. **`human_intervention_required`:** Boolean flag (`True`/`False`) indicating whether human oversight or manual takeover is mandatory.
10. **`final_outcome`:** Outcome status (`SUCCESS`, `FAILED`, `ABORTED`, `PENDING`).
11. **`details`:** Sanitized JSON dictionary containing contextual parameters without secrets.

### Example Structured Log Entries

**1. Successful RPA Availability Extraction:**
```text
[2026-10-31 19:41:11,796] [INFO] [rpa_agent] [RPA_WORKFLOW_COMPLETED] [cid:test-corr-08] RPA availability check completed successfully with 4 slots | outcome=SUCCESS | details={"total_slots": 4}
```

**2. RPA Bounded Retry on Transient Network Hiccup:**
```text
[2026-10-31 19:38:51,563] [WARNING] [rpa_agent] [RPA_RETRY_INITIATED] [cid:sys-init] Recoverable error in 'MockPortalTransientTest' (attempt 1/3): RecoverableRPAError. Retrying in 0.01s... | error_category=RECOVERABLE_RPA_ERROR | retry=1 | details={"operation": "MockPortalTransientTest", "error_type": "RecoverableRPAError", "delay_seconds": 0.01}
```

**3. Human-in-the-Loop Handover Triggered by DOM Structural Change:**
```text
[2026-10-31 19:38:52,551] [ERROR] [rpa_agent] [RPA_HUMAN_HANDOVER] [cid:sys-init] Human intervention required for failed operation: check_yatra_slot_availability | error_category=STRUCTURAL_CHANGE | retry=1 | state=HANDOVER_REQUIRED | HITL=True | outcome=FAILED | details={"failed_operation": "check_yatra_slot_availability", "attempt_count": 1, "error_type": "StructuralPageChangeError"}
```

**4. LangChain Agent Tool Selection & Masked Parameter Log:**
```text
[2026-10-31 19:41:11,798] [INFO] [agent.availability] [AGENT_TOOL_SELECTED] [cid:test-corr-08] LangChain agent selected tool: check_slot_availability_rpa | details={"tool": "check_slot_availability_rpa", "parameters": {"date": "2026-10-20"}}
```

**5. Authentication Failure Logging (Zero Raw OTPs Exposed):**
```text
[2026-10-31 19:40:11,849] [WARNING] [agents.auth_service] [AUTH_OTP_VERIFY] [cid:req-2ee9d230] Incorrect OTP verification code entered | error_category=AUTHENTICATION_ERROR | outcome=FAILED | details={"email": "p**************c@example.com", "error_code": "INCORRECT_CODE", "remaining_attempts": 4}
```

---

## 4. Frontend Privacy and User-Facing Error Messages

The frontend React application (`frontend/src/components/AuthModal.jsx`, `UserInterventionModal.jsx`, and `services/api.js`) was audited to eliminate confidential data exposure:

1. **Elimination of Stack Trace Leakage:**
   - Raw backend exception messages (e.g., `sqlite3.OperationalError`, `KeyError: 'secret'`) are caught and mapped to user-friendly advisories:
     - Invalid OTP $\rightarrow$ *"Invalid or expired verification code. Please try again."*
     - Rate limit exceeded $\rightarrow$ *"Too many verification attempts. Please wait 60 seconds before requesting a new code."*
     - Network timeout $\rightarrow$ *"Unable to connect to service. Please check your internet connection."*
2. **Browser Console Sanitization:**
   - `console.error` calls were updated from logging complete Axios response objects (which contain request headers, tokens, and payload payloads) to logging only sanitized high-level error strings (`err?.message || 'Network error'`).
3. **OTP Input Protection:**
   - The OTP verification field in `AuthModal.jsx` utilizes HTML attributes `type="text"`, `inputMode="numeric"`, `autoComplete="one-time-code"`, and `maxLength={6}` to prevent browser password managers from erroneously harvesting verification codes as persistent account passwords.

---

## 5. Verification and Test Suite Coverage (`tests/test_week10_ethical_compliance.py`)

A comprehensive 23-test suite was authored in `tests/test_week10_ethical_compliance.py`. All 23 tests pass cleanly in 12.285 seconds:

```
----------------------------------------------------------------------
Ran 23 tests in 12.285s

OK
```

### Detailed Test Inventory

| Test Name | Verified Functionality | Status |
| :--- | :--- | :--- |
| `test_01_email_masking` | Verifies length-aware email masking for standard and variable-length names. | **PASSED** |
| `test_02_otp_redaction` | Confirms OTPs are unconditionally replaced with `[REDACTED]`. | **PASSED** |
| `test_03_session_token_redaction` | Confirms bearer session tokens are replaced with `[REDACTED]`. | **PASSED** |
| `test_04_api_key_redaction` | Confirms Groq API keys (`gsk_...`) are replaced with `[REDACTED]`. | **PASSED** |
| `test_05_masking_nested_dictionaries` | Confirms recursive dictionary traversal masks sensitive keys while preserving non-sensitive data. | **PASSED** |
| `test_06_handling_missing_and_malformed_values` | Tests empty strings, `None`, invalid emails, and malformed inputs without crashing. | **PASSED** |
| `test_07_confirming_sensitive_values_never_appear_in_logs` | Attaches a log capture handler and verifies raw emails, OTPs, and keys are scrubbed by `SanitizingFormatter`. | **PASSED** |
| `test_08_successful_rpa_workflow_logging` | Verifies structured event emission for successful Playwright slot checks (`outcome=SUCCESS`). | **PASSED** |
| `test_09_failed_rpa_workflow_logging` | Verifies structured event emission for failed RPA workflows (`outcome=FAILED`, `error_category`). | **PASSED** |
| `test_10_retry_logging` | Verifies structured logging of retry attempts and backoff delay seconds. | **PASSED** |
| `test_11_human_handover_logging` | Verifies structured logging of `HANDOVER_REQUIRED` state and `HITL=True` flag on structural DOM change. | **PASSED** |
| `test_12_langchain_tool_execution_logging` | Verifies agent tool selection and result event logging with sanitized parameters. | **PASSED** |
| `test_13_authentication_failure_logging` | Verifies `AUTH_VERIFY_FAILED` structured log emission with masked email and redacted code. | **PASSED** |
| `test_14_safe_exception_logging` | Confirms unhandled exceptions with embedded secrets are scrubbed before reaching log handlers. | **PASSED** |
| `test_15_correlation_id_propagation` | Verifies that context variable correlation IDs (`cid:req-xxxxxxxx`) are injected into all log records. | **PASSED** |
| `test_16_correct_log_levels` | Verifies appropriate log levels across `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`. | **PASSED** |
| `test_17_official_shrine_board_portal_not_targeted` | Verifies that RPA agent rejects external live URLs (`maavaishnodevi.org`) and restricts targets to local mock HTML. | **PASSED** |
| `test_18_local_mock_portal_availability_checking_works` | End-to-end execution of Playwright automation against `yatra_mock_portal.html`, validating extracted slot count. | **PASSED** |
| `test_19_guest_access_continues_without_mandatory_auth` | Verifies that core endpoints (`/api/chat`, `/api/yatra/plan`, `/api/tourism/destinations`) work for unauthenticated guests. | **PASSED** |
| `test_20_authenticated_user_data_remains_isolated` | Confirms User A cannot view or access saved itineraries belonging to User B. | **PASSED** |
| `test_21_otp_values_never_logged_or_exposed_in_db` | Confirms verification codes are stored only as cryptographic HMAC-SHA256 hashes in `data/auth_store.db`. | **PASSED** |
| `test_22_logout_and_session_revocation_continue_to_work` | Confirms calling `/api/auth/logout` invalidates the session and revokes access to protected endpoints. | **PASSED** |
| `test_23_existing_human_authorization_safeguards_active` | Verifies that booking workflow cannot be triggered without explicit human plan approval (`plan_version` guard). | **PASSED** |

---

## 6. Regression Testing Summary across Weeks 5–10

All previous milestone test suites were executed to ensure complete backwards compatibility:

| Test Suite File | Milestone Focus | Test Count | Result | Execution Duration |
| :--- | :--- | :--- | :--- | :--- |
| `tests.test_rpa_availability_week5` | Playwright slot extraction & calendar navigation | 10 | **PASSED (OK)** | 29.695s |
| `tests.test_rpa_error_handling_week6` | Retry backoff, error categorization, and failover | 14 | **PASSED (OK)** | 17.784s |
| `tests.test_agent_rpa_integration_week7` | LangChain agent tool binding & query dispatch | 23 | **PASSED (OK)** | 29.168s |
| `tests.test_user_controlled_workflow_week8` | HITL pause, plan-version approval, state recovery | 22 | **PASSED (OK)** | 34.337s |
| `tests.test_e2e_system_integration_week9` | Multi-turn planning, guest mode, end-to-end flow | 18 | **PASSED (OK)** | 56.098s |
| `tests.test_tool_calling_accuracy_week9` | Groq tool calling, prompt accuracy, LLM fallback | 12 | **PASSED (OK)** | 14.497s |
| `tests.test_passwordless_auth_week9` | Passwordless OTPs, CSRF, rate limits, session store | 31 | **PASSED (OK)** | 10.988s |
| `tests.test_mongodb_load_week9` | Atlas connection check (skipped when unreachable) & in-memory fallback load test | 9 | **PASSED (8 passed, 1 skipped)** | 19.123s |
| `tests.test_browser_auth_guest_week9` | Playwright real-browser Guest Mode & OTP login flow | 2 | **PASSED (OK)** | 9.756s |
| `tests.test_week10_ethical_compliance` | Ethical boundary, data masking, structured logs | 23 | **PASSED (OK)** | 12.285s |
| **TOTAL (Combined Regression Run)** | **Weeks 5–10 Comprehensive Regression Suite** | **164** | **163 PASSED, 1 SKIPPED, 0 FAILED (100% Pass Rate)** | **258.477s** |

---

## 7. Frontend Quality Verification

1. **Frontend Lint (`npm run lint` via Oxlint):**
   - Result: `Found 0 warnings and 0 errors. Finished in 86ms on 20 files with 104 rules using 16 threads.`
2. **Frontend Production Build (`npm run build` via Vite):**
   - Result: `vite build` completed in `521ms`.
   - Generated client bundle: `dist/index.html` (0.65 kB), `dist/assets/index-4NRlvKAA.css` (10.44 kB), `dist/assets/index-CjPcEVsU.js` (470.00 kB). Zero compile or bundling errors.

---

## 8. Known Limitations and Future Recommendations

1. **SMS Gateway Support:**
   - Currently, passwordless verification uses email OTPs (`auth_service.py`). In Indian pilgrimage demographics, SMS-based verification is widely used. Integrating TRAI-registered DLT SMS gateways (e.g., Gupshup, Fast2SMS) would expand reach to non-email users while applying identical OTP masking rules.
2. **Distributed Log Aggregation:**
   - Structured logs are currently emitted to `sys.stdout` and local daily rotating files. In enterprise production, logs should be forwarded to centralized telemetry stacks (e.g., Grafana Loki, OpenTelemetry Collector, AWS CloudWatch) where the standardized JSON format can be indexed by `correlation_id` and `error_category`.
3. **Automated PII Scanning in CI/CD:**
   - Future pipeline enhancements should integrate automated pre-commit scanners (such as GitGuardian or TruffleHog) to detect any inadvertent hardcoding of API keys or test credentials in repository commits.
