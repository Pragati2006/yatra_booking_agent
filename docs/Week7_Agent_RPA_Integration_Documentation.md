# Week 7: Agent-RPA Integration Layer — Architectural Documentation

**Project:** Maa Vaishno Devi Yatra Booking Agent — Tourism GPT with RPA  
**Branch:** `feature/ui-redesign`  
**Deliverable:** Week 7 Assignment — Agent-RPA Integration Layer  
**Technology Stack:** React 19 + Vite, FastAPI, LangChain (1.4.2), Playwright, ChatGroq / GPT-OSS-20B, SQLite (Session Store)  

---

## 1. Executive Summary & Objective

The objective of Week 7 is to bridge the conversational LLM agent and the browser-automation infrastructure created in Week 5 (calendar navigation and slot extraction) and Week 6 (retry-and-escalate, state validation, and pause-and-handover error handling).

Prior to Week 7, availability checking existed either as a direct backend API endpoint (`/api/yatra/rpa/availability`) or standalone RPA functions (`rpa_agent.check_yatra_slot_availability`). In Week 7:
1. **LangChain Tool Exposure:** The availability checking workflow is encapsulated as a formal LangChain tool (`check_yatra_availability_tool` / `check_yatra_availability`).
2. **Parameter Extraction & Validation:** User natural language (e.g., *"Check VIP Darshan availability for 20 November 2026."*) is parsed to extract ISO dates (`YYYY-MM-DD`) and supported categories (`Normal Darshan`, `VIP Darshan`, `Helicopter Darshan`). Missing parameters trigger polite conversational clarifications without fabricating dates.
3. **End-to-End Orchestration:** The React chat interface, FastAPI `/api/chat` and `/api/yatra/` endpoints, LangChain agent tool binding, and Playwright Chromium sandbox automation operate as a single unified conversational pipeline.

---

## 2. Multi-Agent Architecture & Live Orchestration Flow

The solution uses a modular multi-agent system where specialized components cooperate under the coordination of `agents/orchestrator.py` and `agents/coordinator.py`:

```
                           +----------------------------+
                           |  React 19 + Vite Frontend  |
                           |   (AIChat.jsx, Home.jsx)   |
                           +--------------+-------------+
                                          | HTTP POST /api/chat
                                          v
                           +----------------------------+
                           |   FastAPI REST Backend     |
                           |    (backend/main.py)       |
                           +--------------+-------------+
                                          |
                                          v
                           +----------------------------+
                           | Conversational Orchestrator|
                           |  (agents/orchestrator.py)  |
                           +--------------+-------------+
                                          |
        +---------------------------------+---------------------------------+
        | Intent: AVAILABILITY            | Intent: TOURISM                 | Intent: BOOKING
        v                                 v                                 v
+-------------------------------+ +-------------------------------+ +-------------------------------+
|     AvailabilityAgent         | |   Content / Knowledge Agent   | |  Human-in-the-Loop Gate       |
|  (agents/availability_agent)  | |   (MongoDB / Curated CSVs)    | |  (Explicit Confirmation req)  |
+---------------+---------------+ +-------------------------------+ +---------------+---------------+
                |
                v
+---------------------------------------------------------------+
| Genuine LLM Tool-Calling Cycle (Groq / GPT-OSS-20B):          |
| 1. LLM receives tool schema via bind_tools()                  |
| 2. LLM emits tool_call with parsed date & category            |
| 3. Application validates parameters before execution          |
| 4. Dispatches LangChain tool: check_yatra_availability_tool   |
| 5. Playwright extracts slots from local mock portal           |
| 6. ToolMessage returned to LLM with structured result         |
| 7. LLM interprets results and generates final chat response   |
+-------------------------------+-------------------------------+
                |                               |
                | (If LLM/API offline or fails) |
                v                               v
+-------------------------------+ +-------------------------------+
| Deterministic Fallback Engine | | Playwright Chromium Sandbox   |
| - Regex ISO date parsing      | | - Calendar Navigation         |
| - Missing date prompts        | | - State Validation & Waits    |
| - Category validation         | | - Structured Slot Extraction  |
+-------------------------------+ +-------------------------------+
```

---

## 3. LangChain Tool Integration Details

### Tool Specifications

- **Name:** `check_yatra_availability_tool` (with alias `check_yatra_availability`)
- **Module:** `agents/tools.py` (exported via `langchain_tools.ALL_LANGCHAIN_TOOLS` and `agents.tools.get_all_tools()`)
- **Base Class:** `langchain_core.tools.BaseTool` / `langchain.tools.tool`
- **Schema & Arguments:**
  - `date: str` — Mandatory yatra date in ISO `YYYY-MM-DD` format (e.g., `"2026-11-20"`).
  - `category: Optional[str] = None` — Optional category filter: `"Normal Darshan"`, `"VIP Darshan"`, or `"Helicopter Darshan"`.
  - `headless: bool = True` — Headless browser execution flag (defaults to `True` for safe background execution).
- **Return Type:** Structured Python dictionary containing audit metadata and slot records:

```json
{
  "status": "SUCCESS",
  "date": "2026-11-20",
  "category_filter": "VIP Darshan",
  "total_slots": 2,
  "available_count": 2,
  "full_count": 0,
  "unavailable_count": 0,
  "slots": [
    {
      "slot_id": "SLOT-501",
      "yatra_date": "2026-11-20",
      "slot_name": "VIP Darshan",
      "time": "06:00",
      "session": "Morning VIP Aarti",
      "availability_status": "available",
      "remaining_capacity": 45,
      "price": 500.0,
      "retrieved_at": "2026-10-31T10:30:00"
    }
  ],
  "is_empty": false,
  "screenshot_path": "C:\\Users\\...\\AppData\\Local\\Temp\\rpa_availability_2026-11-20.png",
  "recovered": false,
  "handover_required": false
}
```

---

## 4. Natural-Language Parameter Extraction

The parameter passing pipeline is defined in `agents/conversation_agent.py`:

```
User Free-Text Input
       ↓
Intent Classification: detect_intent()
       ↓
extract_availability_parameters(user_text, context)
       ↓
├── parse_and_validate_yatra_date()
│   ├── Relative dates: "today", "tomorrow", "day after tomorrow"
│   ├── ISO formats: "YYYY-MM-DD", "YYYY/MM/DD"
│   ├── Regional formats: "DD-MM-YYYY", "DD/MM/YYYY"
│   ├── Natural language: "20 November 2026", "20th Nov 2026", "November 20, 2026"
│   ├── Calendar validation: datetime(year, month, day) — rejects invalid dates like Feb 31
│   └── Context resolution: retrieves prior date for follow-up turns ("on that date")
│
└── extract_and_validate_category()
    ├── "VIP Darshan" (keywords: vip)
    ├── "Normal Darshan" (keywords: normal, regular, general, standard)
    ├── "Helicopter Darshan" (keywords: helicopter, heli)
    └── Unsupported validation: flags unrecognized categories ("Super VIP", "Royal Darshan")
```

### Safety & Guardrails
1. **Zero Date Fabrication:** If the user sends *"Check availability."*, the extractor returns `missing_date: True`. The orchestrator yields a friendly clarification request rather than inventing a date.
2. **Strict Calendar Validation:** Impossible calendar dates (e.g., `2026-02-31`) trigger an immediate `INVALID_INPUT` response explaining that the date does not exist.
3. **Category Safeguards:** Requesting non-existent categories (e.g., *"Super VIP"*) prompts the user with the three recognized categories.
4. **Intent Isolation:** Pure informational tourism questions (*"What is Vaishno Devi Yatra?"*, *"What are the Aarti timings?"*) are routed to the MongoDB/knowledge agent and **never** launch Playwright browser instances unnecessarily.

---

## 5. End-to-End Execution Flow

```
1. User enters: "Check VIP Darshan availability for 20 November 2026." in React AIChat
2. AIChat dispatches POST /api/chat payload { message, session_id }
3. FastAPI invokes coordinator.route_message() -> orchestrator.orchestrate_conversational_turn()
4. orchestrator identifies intent == "AVAILABILITY"
5. conversation_agent extracts parameters: { date: "2026-11-20", category: "VIP Darshan" }
6. LangChain tool check_yatra_availability_tool.invoke() is dispatched
7. coordinator.check_slot_availability_rpa() executes Playwright Chromium automation:
   a. Browser launches in headless sandbox
   b. Navigates to yatra_mock_portal.html
   c. Selects Availability Calendar tab (#tabCalendar)
   d. Enters date (#calendarDate) and category filter (#slotCategoryFilter)
   e. Clicks #btnFetchSlots and waits explicitly for #slotsContainer
   f. Validates DOM state integrity and extracts .slot-card elements
   g. Captures audit screenshot
   h. Reliably closes browser via try...finally
8. conversation_agent.format_availability_reply() formats result into devotional markdown
9. Turn response is persisted to SQLite session_store and returned via FastAPI
10. React AIChat renders formatted slot cards with real-time capacity and pricing
```

---

## 6. Real Example Executions & Outputs

### Scenario 1: Successful Availability Query
**User Query:** `"Check VIP Darshan availability for 20 November 2026."`  
**Extracted Parameters:** `date: "2026-11-20"`, `category: "VIP Darshan"`  
**Playwright Result:** 2 slots extracted, 0 full, 0 unavailable.  
**Agent Natural Language Output:**
> 🙏 **Jai Mata Di! Yatra Slot Availability**
>
> Availability for **2026-11-20** for **VIP Darshan**: found **2** slots (2 available, 0 full, 0 unavailable):
>
> • **SLOT-501** — **VIP Darshan** • 🕒 06:00 • _Morning VIP Aarti_  
>   - Status: 🟢 **Available** (45 seats left) | Fare: **₹500**  
> • **SLOT-502** — **VIP Darshan** • 🕒 18:00 • _Evening VIP Aarti_  
>   - Status: 🟢 **Available** (18 seats left) | Fare: **₹500**  
>
> May Mata Vaishno Devi grant you a blessed and fulfilling yatra! Would you like to proceed with booking travel and stay for this date?

### Scenario 2: Missing Date Clarification
**User Query:** `"Check availability."`  
**Extracted Parameters:** `date: None`, `missing_date: True`  
**Agent Output:**
> 🙏 **Jai Mata Di!**
>
> To check live yatra darshan availability via our Playwright RPA agent, please specify your preferred date (e.g., **'20 November 2026'** or **'2026-10-20'**).
>
> You can also specify a category such as **Normal Darshan**, **VIP Darshan**, or **Helicopter Darshan**.

### Scenario 3: Empty Calendar / No Available Slots
**User Query:** `"Check availability for 2026-11-28."`  
**Extracted Parameters:** `date: "2026-11-28"`, `total_slots: 0`, `is_empty: True`  
**Agent Output:**
> 🙏 **Jai Mata Di! Availability Status**
>
> No yatra darshan slots are currently open for **2026-11-28**.
>
> ℹ️ *Note:* This is not a system error; the quota for this date is either fully allocated or not yet released by the Shrine Board.
>
> **Recommendation:** Please consider checking adjacent dates (e.g., 2026-10-20 or 2026-10-21) or an alternative darshan category.

### Scenario 4: Structural Page Change / Human Handover
**Portal Trigger:** Corrupted DOM structure / missing container.  
**Agent Output:**
> 🙏 **Jai Mata Di! Human Handover Notice**
>
> Automated availability checking for **2026-10-20** could not safely continue.
>
> • **Reason:** Automated checking could not safely verify page state.  
> • **Attempts Made:** 1  
> • **Safety Protocol:** Our RPA agent safely paused to avoid unverified or misleading availability claims.  
> • **Pilgrim Guidance:** Please verify slot availability directly on the Shrine Board portal.  
>
> _Our pilgrim support team has been notified. You may also check official Shrine Board offline counters at Katra._

---

## 7. Automated Test Suite & Coverage

The Week 7 test suite is implemented in `tests/test_agent_rpa_integration_week7.py`. Following the targeted integration connecting the LLM tool-calling agent to the live orchestrator, all 23 scenarios were executed and verified:

| Test ID | Scenario Description | Status |
|:---|:---|:---:|
| `test_01` | LangChain BaseTool registration and schema validation | ✅ PASS |
| `test_02` | Tool selection for natural-language query via bind_tools mock | ✅ PASS |
| `test_03` | Date parsing & ISO YYYY-MM-DD conversion across 7 formats | ✅ PASS |
| `test_04` | Category extraction & normalization (Normal, VIP, Helicopter) | ✅ PASS |
| `test_05` | Exact argument passing to underlying RPA functions | ✅ PASS |
| `test_06` | Missing date triggers clarification without date fabrication | ✅ PASS |
| `test_07` | Invalid calendar date rejection (e.g., 31 February) | ✅ PASS |
| `test_08` | Unsupported category rejection and guidance prompt | ✅ PASS |
| `test_09` | Successful slot extraction interpretation and formatting | ✅ PASS |
| `test_10` | Empty calendar reported properly without claiming system error | ✅ PASS |
| `test_11` | Week 6 handover presented transparently without false claims | ✅ PASS |
| `test_12` | General tourism queries route to knowledge and bypass RPA | ✅ PASS |
| `test_13` | Multi-turn follow-ups inherit date from conversation context | ✅ PASS |
| `test_14` | Week 4 Playwright mock booking workflow preserved | ✅ PASS |
| `test_15` | Week 5 direct availability navigation preserved | ✅ PASS |
| `test_16` | Week 6 retry and error-handling intact | ✅ PASS |
| `test_17` | Plan-version and human authorization gates strictly preserved | ✅ PASS |
| `test_18` | Orchestrator genuine tool-calling cycle with ToolMessage & LLM interpretation | ✅ PASS |
| `test_19` | Missing Groq credentials trigger deterministic fallback with metadata | ✅ PASS |
| `test_20` | API failure/exception during LLM call falls back to deterministic extraction | ✅ PASS |
| `test_21` | Malformed tool call with invalid date rejected before Playwright | ✅ PASS |
| `test_22` | Malformed tool call with unsupported category rejected before Playwright | ✅ PASS |
| `test_23` | Verification of single Playwright execution (no duplicate invocations) | ✅ PASS |

**Test Command:**
```powershell
& "..\venv\Scripts\python.exe" -m unittest tests/test_agent_rpa_integration_week7.py
```
**Outcome:** `Ran 23 tests in 30.164s — OK`

---

## 8. Limitations & Sandbox Boundaries

1. **Local Sandboxed Mock Portal Only:** In accordance with academic, ethical, and legal guidelines, the RPA agent operates strictly against the local mock portal (`yatra_mock_portal.html`). It does not scrape live Shrine Board servers, bypass live security controls, or automate live financial transactions.
2. **Read-Only Availability Auditing:** Availability checking is strictly read-only and does not mutate booking plans or increment `plan_version`.
3. **Deterministic Testing:** Offline deterministic fallbacks and mock LLM fixtures guarantee 100% reproducible test outcomes without consuming live Groq API tokens.
