# Maa Vaishno Devi Yatra Booking Agent (Tourism AI with RPA)

An intelligent, multi-agent AI travel companion and automated booking prototype for the sacred **Maa Vaishno Devi Pilgrimage (Katra, Jammu & Kashmir)**. The system combines natural language understanding (NLU), multi-modal transit optimization, deterministic itinerary scheduling, verified regional heritage knowledge, and Playwright-based Robotic Process Automation (RPA) guarded by an ethical Human-in-the-Loop authorization gate.

---

## 1. Project Overview & Problem Statement

### Pilgrimage Challenge
The pilgrimage to the holy cave shrine of Shri Mata Vaishno Devi Ji in the Trikuta Mountains of Katra involves unique logistical, physical, and timing demands:
- **High-Exertion Mountain Trek:** The 26 km round-trip trek between Katra base, Ardhkuwari, and Bhawan reaches an altitude of ~5,200 ft, demanding dedicated full-day focus and realistic post-trek recovery.
- **Strict Yatra Slots & Formalities:** Mandatory RFID yatra tracking cards, dedicated darshan time slots, and early helicopter reporting deadlines must align with incoming flights, trains, and buses.
- **Regional Feasibility & Travel Times:** Pilgrims frequently attempt to combine distant regional destinations (e.g., Patnitop, Shiv Khori, Sanasar) into short 2- or 3-day trips without accounting for mountainous transit times (85+ km on hill roads) or physical exhaustion.
- **Unverified & Misleading Plans:** Generic LLMs often hallucinate direct trains to Katra from non-existent origins, fabricate fictitious return fares, or schedule grueling excursions on the day of the holy trek.

### Architectural Solution
The Yatra Booking Agent resolves these challenges through a **hybrid deterministic and conversational architecture**:
1. **Choice-Driven Planning:** Pilgrims can plan either through a structured, accessible guided intake form or naturally via a conversational AI companion.
2. **Deterministic Feasibility Engine:** Evaluates user-selected destinations against ground-truth regional distances, terrain travel times, trip duration, and trek-day physical recovery constraints. Distant excursions on short trips are never silently discarded; they are flagged with clear explanations and duration recommendations.
3. **Isolated Trek & Recovery Scheduling:** Day 2 is strictly reserved as an exclusive holy trek day. Immediate post-trek days on longer journeys are protected for gentle Katra leisure.
4. **Transparent Cost Segregation:** Direct verified costs (transit tickets, shrine slots, certified hotels) are strictly separated from discretionary estimates (local taxis, meals) and excluded expenses (pony/palki charges, offerings).
5. **Server-Side Authorization & Idempotency:** Client-side flags cannot authorize bookings; bookings require server-recorded human consent tied to an exact plan version. Any material change revokes authorization and prevents double bookings.
6. **Simulated RPA Sandbox:** Automates form-filling and verification via headless Playwright automation in an isolated mock environment without touching live financial or government portals.

---

## 2. System Architecture & Request Flow

### Dual-Version System Architecture
The repository hosts two decoupled client implementations sharing a unified multi-agent and data intelligence backend:
1. **Version 1 (Streamlit Monolith — `app.py`):** Self-contained multi-tab prototype for quick exploratory validation and testing.
2. **Version 2 (React 19 + FastAPI Decoupled Stack):** Modern production-ready web application consisting of a React (Vite) frontend communicating with an asynchronous FastAPI REST backend.

```
                          ┌────────────────────────────────────────────────────────┐
                          │                   CLIENT INTERFACES                    │
                          └────────────────────────────────────────────────────────┘
                                      │                                │
                     Version 1        │                                │ Version 2
               ┌──────────────────────┴──────┐          ┌──────────────┴─────────────────┐
               │    Streamlit Application    │          │      React + Vite Frontend     │
               │          (app.py)           │          │   (frontend/src/ - Port 5173)  │
               └──────────────┬──────────────┘          └────────────────┬───────────────┘
                              │                                          │ HTTP Axios
                              │ Direct Python                            │ (frontend/src/services/api.js)
                              │ Function Calls                           ▼
                              │                         ┌────────────────────────────────┐
                              │                         │        FastAPI Backend         │
                              │                         │       (backend/main.py)        │
                              │                         │ Port 8000: /api/chat, /yatra,  │
                              │                         │            /weather, /tourism  │
                              │                         └────────────────┬───────────────┘
                              │                                          │
                              ▼                                          ▼
  ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
  │                                MULTI-AGENT ORCHESTRATION LAYER                                │
  │                                  (agents/coordinator.py)                                      │
  └───────────────────────────────┬───────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────┼──────────────────────────────┬──────────────────────────────┐
    ▼                             ▼                              ▼                              ▼
┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐
│   ConversationAgent    │  │     ItineraryAgent     │  │  RecommendationAgent  │  │   Playwright RPA       │
│(agents/conversation_   │  │ (agents/itinerary_     │  │ (agents/recommendation │  │   (agents/rpa_agent.py)│
│       agent.py)        │  │       agent.py)        │  │       _agent.py)       │  │                        │
│ - Multilingual NLU     │  │ - Feasibility engine   │  │ - Persona matching     │  │ - Browser form auto.   │
│ - Intent classification│  │ - Trek-day isolation   │  │ - Family/budget styles │  │ - Mock booking sandbox │
│ - Devotional phrasing  │  │ - Recovery scheduling  │  │ - Pace evaluation      │  │ - Audit screenshots   │
└────────────────────────┘  └────────────────────────┘  └────────────────────────┘  └────────────────────────┘
            │                                                        ▲
            ▼                                                        │
┌────────────────────────────────────────────────────────────────────┴───────────────────────────────────┐
│                                   SHARED CORE & DATA ENGINES                                           │
├────────────────────────────────┬───────────────────────────────────┬───────────────────────────────────┤
│    orchestrator.py & session   │       budget_engine.py            │     explore_data.py & yatra_info  │
│ - Multi-turn conversational flow│ - Decimal verified cost math      │ - 29 J&K destinations & history   │
│ - Replanning & version control │ - Room & night allocation logic   │ - Aarti timings, RFID, helplines  │
│ - SQLite ACID session store    │ - Budget overrun evaluation       │ - Video links, entry fees, taxi   │
└────────────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
                                                 │
                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              KNOWLEDGE RETRIEVAL & INTEGRATIONS                                        │
├────────────────────────────────┬───────────────────────────────────┬───────────────────────────────────┤
│    MongoDB Atlas + LangChain   │       Open-Meteo Weather          │        Airtable Fallback          │
│(mongo_db.py, mongodb_agent.py, │          (weather.py)             │       (airtable_store.py)         │
│ mongodb_tools.py, seed_mongo)  │ - Real-time forecast via API      │ - Optional cloud booking store    │
│ - Groq ChatGroq LLM fallback   │ - Seasonal monthly Katra averages │ - Activated when secrets present  │
└────────────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```

---

## 3. Supported User Workflows

### 1. Planning Mode Choice Screen & 4-Step Guided Journey
Pilgrims are greeted with a balanced choice screen offering two distinct planning modes:
- **Plan with a Form:** A streamlined, 4-step guided wizard:
  1. **Step 1: Preferences:** Intake form capturing departure city, travel date, pilgrim count, duration, darshan category, transport preference, stay level, and budget.
  2. **Step 2: Recommended Yatra:** Synthesizes verified transit schedules (e.g. Vande Bharat Express), certified Katra hotels, shrine darshan slots, and day-wise feasibility itineraries.
  3. **Step 3: Booking Review & RPA:** Displays final booking breakdown and enforces **compulsory passwordless email authentication** before booking. Authenticated devotees initiate Playwright browser automation against the sandboxed local mock portal, passing interactive Human-in-the-Loop OTP and CAPTCHA checkpoints.
  4. **Step 4: Confirmation & Download Pass:** Genuine final confirmation page displaying the official booking reference (e.g. `VD-RPA-991041`), prominent demo disclaimers, simulated payment status, printable pass view, and zero-dependency PDF pass download.
- **Chat with AI:** An interactive pilgrimage companion allowing conversational queries, live VIP slot checks, and seamless handoff to personalized booking cards.
- **Seamless Mode Switching:** Top switcher bar enables toggling between Form and Chat with zero loss of session ID, plan version, or itinerary state.

### 2. Interactive Jammu & Kashmir Sightseeing Browser
- **29 Grounded Destinations:** Katra local shrines, trek-route stops, regional hill stations (Patnitop, Sanasar), holy springs (Baba Dhansar), ancient cave shrines (Shiv Khori), and Kashmir excursions.
- **Real-Time Search & Category Filters:** Instant search by destination or region, filter by category with live count badges, and expand cards for rich heritage notes and local access instructions.
- **Interactive Selection Bar:** Sticky selection summary displaying selected places as quick-remove tags (`×`) and direct triggers to generate timelines or select *"Decide Later in Katra"*.

### 3. Realistic Itinerary & Feasibility Advisories
- **Strict Trek Day Exclusivity:** Day 2 is reserved exclusively for the Katra-Bhawan-Bhairavnath yatra. Distant excursions (Patnitop, Sinthan Top) are barred from Day 2.
- **Protected Recovery Time:** On 4+ day trips, Day 3 is safeguarded for gentle Katra leisure and recovery (`exertion_level: 'Light'`).
- **Grounded Feasibility Advisories:**
  - `feasible_places`: Listed with green verification badges and mapped to specific itinerary days.
  - `infeasible_places`: Displayed with transparent explanations (e.g., *"Patnitop is 85 km from Katra (~3 hrs each way) and cannot fit within a 3-day trip without physical exhaustion"*) and duration recommendations (*"Consider extending your trip to 4+ days"*).
  - Uncatalogued destinations (e.g., *"Eiffel Tower"*) are strictly rejected with an unverified catalogue advisory.

### 4. Human-in-the-Loop Authorization & Simulated RPA Execution
- **Compulsory Authentication Enforcement:** Guests can freely explore tourism knowledge and generate itineraries, but initiating automated booking strictly requires passwordless email OTP authentication.
- **Server-Side Authorization & Idempotency:** The backend validates session ownership, authorization flags, and exact plan versions before processing booking operations.
- **Playwright RPA Mock Booking Sandbox:** Launches a headless Chromium browser instance interacting exclusively with the sandboxed local mock portal (`mock_portal/index.html`).
- **Interactive HITL Checkpoints:** Automated execution pauses safely at the **OTP Checkpoint** and **CAPTCHA Checkpoint**, prompting the devotee through an interactive modal (`UserInterventionModal`) to authorize continuation.
- **Controlled Step 4 Transition:** Step 3 remains visible until the backend successfully receives and persists the confirmed booking; a prominent *"Continue to Confirmation"* button guides the devotee to Step 4.

### 5. Passwordless Authentication, PDF Pass & My Account History
- **Passwordless Security:** Single-use 6-digit cryptographic OTPs via `secrets.choice`, salted SHA-256 storage, 5-minute expiry, and a maximum of 5 failed attempts.
- **Zero-Dependency PDF Pilgrim Pass:** Client-side (`pdfGenerator.js`) and backend (`utils/pdf_generator.py`) generators emit well-formed standard PDF 1.4 documents with official reference IDs, devotee particulars, and prominent demo disclaimers without heavy third-party PDF dependencies.
- **My Account & Saved History Integration:**
  - Authenticated devotees can open `My Account` in the navigation bar to inspect `My Bookings`.
  - Displays all 14 required particulars: Booking Reference, Status, Devotee Name, Associated Email, Pilgrims Count, Yatra Date, Category, Slot Time, Route/Transit, Hotel, Simulated Total, Sandbox Payment Status, Timestamp, and Demo Warning Banners.
  - Interactive *"View Details"* modal and pass re-download.
  - **Multi-Session Persistence:** Bookings are persisted in SQLite (`data/auth_store.db`), surviving browser page reloads and complete logout/re-login cycles.

### 6. Ethical Boundary, Data Masking & Structured Logging Transparency (Week 10)
- **Dual-Track Shrine Board Boundary:** Playwright browser automation is strictly confined to Track A (local simulated sandbox `yatra_mock_portal.html`). The live Shrine Board portal (`maavaishnodevi.org`) is protected against automated scraping, bot bookings, and credential harvesting; real bookings are completed manually by pilgrims via official deep-links.
- **Centralized Data Masking (`utils/masking.py`):** Automatic scrubbing of sensitive inputs across backend logs and frontend UI. Emails are length-masked (`p*****i@example.com`), OTPs/tokens/passwords are replaced with `[REDACTED]`, and Groq API keys (`gsk_...`) are stripped from log streams.
- **Structured Error Logging (`utils/logger.py`):** Emits standardized JSON/key-value logs with ISO timestamps, log levels (`DEBUG` through `CRITICAL`), component, operation, request correlation ID (`X-Correlation-ID`), error category, retry count, workflow state, HITL flags, and sanitized parameter dictionaries.
- **Friendly Frontend Errors:** User interfaces suppress raw stack traces and database exceptions, presenting actionable guidance while capturing sanitized diagnostics internally.
- **Test Coverage:** Dedicated 23-test suite in `tests/test_week10_ethical_compliance.py` verifying masking algorithms, structured logging, correlation ID tracing, and compliance invariants.

---

## 4. Technology Stack & Component Responsibilities

| Technology | Version | Actual Architectural Role |
| :--- | :--- | :--- |
| **Python** | 3.12 | Backend core runtime, multi-agent orchestration, and deterministic engines |
| **FastAPI** | 0.143+ | Asynchronous REST API layer providing typed JSON endpoints and CORS middleware |
| **Uvicorn** | 0.53+ | ASGI web server running the FastAPI backend daemon |
| **React** | 19.0+ | Modern component-based frontend with modular state management and responsive UI |
| **Vite** | 8.3+ | Next-generation frontend bundler providing sub-second HMR and optimized production builds |
| **Playwright** | 1.63+ | Headless Chromium automation executing simulated RPA booking workflows and E2E browser tests |
| **SQLite (ACID)** | 3.x | Persistent server-side session store (`data/sessions.db`) with thread-safe process locks |
| **Groq / ChatGroq**| 0.37+ | LLM inference client powering natural language conversation and slot extraction |
| **LangChain** | 1.4+ | Agentic tool invocation framework binding MongoDB retrieval and coordinator tools |
| **MongoDB Atlas** | 4.18+ | Cloud NoSQL document store housing tourist attractions and yatra knowledge |
| **Open-Meteo API** | Live | Free external REST endpoint providing live Katra weather forecasts |
| **Pandas** | 3.0+ | CSV database engine managing transport schedules, hotel inventories, and booking ledgers |

---

## 5. API Endpoint Specifications

All endpoints are hosted on `http://127.0.0.1:8000`:

### `POST /api/yatra/` (Travel & Darshan Search)
Routes messages to the conversational orchestrator, resolving user requirements, selecting transport options, and initializing the server session.
* **Request:**
  ```json
  {
    "message": "2 people from Delhi to Katra on 2026-10-20 for 4 days with Normal Darshan",
    "session_id": null
  }
  ```
* **Response (Excerpt):**
  ```json
  {
    "intent": "TRIP_PLANNING",
    "session_id": "3974b81f-28c8-4036-9ec0-14cff2a83b46",
    "plan_version": 1,
    "status": "PLAN_READY",
    "plan": {
      "options": [
        {
          "transport": { "mode": "Train", "operator": "Vande Bharat Express", "price": 1660 },
          "slot": { "category": "Normal Darshan", "price": 0 },
          "total_price": 3320
        }
      ]
    }
  }
  ```

### `POST /api/yatra/sightseeing` (Destination Catalogue)
Returns all 29 grounded destinations with categories, regional proximity, entry fees, and heritage details.
* **Request:** `{"category": null}`
* **Response:** `{"status": "success", "count": 29, "places": [...]}`

### `POST /api/yatra/itinerary` (Deterministic Timeline Generator)
Generates day-by-day activities and evaluates sightseeing feasibility.
* **Request:**
  ```json
  {
    "option": { "transport": { "mode": "Train", "operator": "Vande Bharat Express" }, "slot": { "category": "Normal Darshan" } },
    "hotel": { "name": "Trikuta Guest House", "price_per_night": 1200 },
    "hotel_nights": 2,
    "sightseeing_places": ["Bhairavnath Temple", "Patnitop"],
    "request": { "duration_days": 3, "origin": "Delhi", "pax": 2 }
  }
  ```
* **Response:**
  ```json
  {
    "status": "success",
    "days": 3,
    "feasible_places": ["Bhairavnath Temple"],
    "infeasible_places": [
      {
        "place": "Patnitop",
        "reason": "Patnitop is 85 km from Katra (~3 hrs each way) and cannot fit within a 3-day trip without physical exhaustion.",
        "suggestion": "Consider extending your trip to 4+ days to comfortably visit Patnitop on a dedicated excursion day."
      }
    ],
    "itinerary": [...]
  }
  ```

### `POST /api/yatra/authorize` (Human Authorization Gate)
Records human consent on the active server session for a specific plan version.
* **Request:** `{"session_id": "3974b81f-...", "plan_version": 1, "user_confirmation": "Confirm booking"}`
* **Response:** `{"status": "success", "plan_version": 1, "message": "Server-side authorization recorded for Revision #1."}`

### `POST /api/yatra/confirm` (Simulated Booking Execution)
Verifies server-side authorization and issues confirmation credentials. Prevents duplicate confirmations.
* **Request:**
  ```json
  {
    "option": {...},
    "pax": 2,
    "user_name": "Guest-User",
    "hotel": {...},
    "hotel_nights": 2,
    "sightseeing_places": ["Bhairavnath Temple"],
    "human_authorized": true,
    "session_id": "3974b81f-...",
    "plan_version": 1
  }
  ```
* **Response:** `{"status": "success", "booking_id": "VD26753AC0", "plan_version": 1, "message": "May Mata Vaishno Devi grant you a safe and blessed yatra!"}`

### `POST /api/yatra/rpa` (Playwright Browser Automation)
Triggers headless Chromium form automation in the simulated sandbox.
* **Request:** `{"user_name": "Guest-User", "pax_count": 2, "transport_text": "Train from Delhi", "slot_text": "Normal Darshan", "total_price": 5720, "session_id": "...", "plan_version": 1, "human_authorized": true}`
* **Response:** `{"status": "success", "rpa": {"booking_id": "VD26753AC0", "status": "CONFIRMED", "details": "Automated simulated checkout verified."}}`

---

## 6. Setup, Installation & Startup Guide

> 💡 **Teammates:** For a complete, dedicated onboarding guide with Windows PowerShell walkthroughs, see [**TEAM_SETUP.md**](TEAM_SETUP.md).

### Prerequisites
- **Git:** Git for Windows/macOS/Linux
- **Python:** Python 3.12 (64-bit)
- **Node.js:** Node.js v18+ or v20+ with `npm`
- **Operating System:** Windows, macOS, or Linux

### Step 1: Clone the Repository & Configure Environment
1. Clone the active branch:
   ```powershell
   git clone -b feature/ui-redesign https://github.com/Pragati2006/yatra_booking_agent.git
   cd yatra_booking_agent
   ```
2. Copy `.env.example` to `.env`:
   ```powershell
   copy .env.example .env
   ```
3. Populate `.env` with your credentials:
   ```dotenv
   GROQ_API_KEY=your_groq_api_key_here
   MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   MONGO_DB_NAME=yatra_booking_agent
   ```
   *(Note: MongoDB Atlas and SMTP are optional; the application automatically engages local fallbacks if they are omitted).*

### Step 2: Python Environment & Dependencies
Create and activate your virtual environment, then install dependencies:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### Step 3: Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

---

## 7. How to Run the Applications

### Running Version 2 (React Frontend + FastAPI Backend)

Open two terminal windows:

#### Terminal 1 — Start the FastAPI Backend:
```powershell
# From repository root (yatra-booking-agent):
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Backend API:** `http://127.0.0.1:8000/`
- **Swagger Documentation:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/api/health`

#### Terminal 2 — Start the React Frontend:
```powershell
# From repository root:
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
- **React Frontend URL:** `http://127.0.0.1:5173/`

---

### Running Version 1 (Streamlit Monolith)
```powershell
# From repository root:
python -m streamlit run app.py
```
- **Streamlit Local URL:** `http://localhost:8501/`

---

## 8. Verified Testing & Quality Assurance

All test suites have been verified with genuine executions. Run any suite from the repository root:

### Core Automated Test Commands

| Test Suite | Command | Coverage | Status |
| :--- | :--- | :--- | :---: |
| **FastAPI REST Endpoints** | `python tests/test_fastapi_endpoints.py` | 8 core endpoints | **8/8 PASSED** |
| **Preference-Aware Planner** | `python -m unittest tests/test_preference_aware_planner.py` | Feasibility engine, trek isolation, patnitop | **14/14 PASSED** |
| **Server Auth Security** | `python -m unittest tests/test_server_authorization_security.py` | Stale versions, client flag bypass, locks | **9/9 PASSED** |
| **Booking Lifecycle Audit** | `python -m unittest tests/test_booking_lifecycle_audit.py` | History, idempotency, revision revocation | **4/4 PASSED** |
| **Intent Routing & Tourism** | `python tests/test_intent_routing.py` | Intent detection, slots, tourism guardrails | **81/81 PASSED** |
| **Budget Calculation Engine** | `python -m unittest tests/test_budget_engine.py` | Decimal math, cost tiers, room allocation | **16/16 PASSED** |
| **E2E Orchestrator Chat** | `python -m unittest tests/test_e2e_orchestrator_conversation.py` | 8-turn full conversational flow | **1/1 PASSED** |
| **SQLite Session Store** | `python -m unittest tests/test_session_store.py` | ACID transactions, process concurrency | **8/8 PASSED** |
| **Planning Mode Choice (Browser)** | `python -m unittest tests/test_planning_mode_choice_browser.py` | Choice screen, mode switcher, state sync | **5/5 PASSED** |
| **Sightseeing Browser (Browser)**| `python -m unittest tests/test_sightseeing_browser_browser.py` | 29 destinations, search, category filters | **5/5 PASSED** |
| **Feasibility UI (Browser)** | `python -m unittest tests/test_feasibility_ui_browser.py` | Feasible badges, infeasible advisories | **1/1 PASSED (5/5)** |
| **10-Step Browser E2E Journey** | `python -m unittest tests/test_browser_e2e_journey.py` | Complete real-browser user journey | **2/2 PASSED** |
| **Journey E Edge Cases (Browser)**| `python -m unittest tests/test_audit_journey_e_edge_cases.py` | Reload recovery, tab isolation, budget bounds | **5/5 PASSED** |
| **RPA Slot Availability (Playwright)** | `python -m unittest tests/test_rpa_availability_week5.py` | Calendar navigation, explicit waits, slot extraction | **10/10 PASSED** |
| **RPA Error Handling & Retry (Playwright)** | `python -m unittest tests/test_rpa_error_handling_week6.py` | Bounded retries, state validation, pause-and-handover | **14/14 PASSED** |
| **Agent-RPA Integration Layer (LangChain + Playwright)** | `python -m unittest tests/test_agent_rpa_integration_week7.py` | Tool registration, ISO date conversion, parameter passing, handover | **23/23 PASSED** |
| **User-Controlled Workflow & Checkpoints (HITL + RPA)** | `python -m unittest tests/test_user_controlled_workflow_week8.py` | OTP/CAPTCHA checkpoints, safe pause, SQLite persistence, cross-session isolation | **22/22 PASSED** |
| **E2E System Integration (Week 9)** | `python -m unittest tests/test_e2e_system_integration_week9.py` | 18 end-to-end integration scenarios (FastAPI -> Agent -> RPA -> Mock Portal) | **18/18 PASSED** |
| **Agent Tool-Calling Accuracy (Week 9)** | `python -m unittest tests/test_tool_calling_accuracy_week9.py` | Tool binding, argument extraction, duplicate prevention, deterministic fallback | **12/12 PASSED** |
| **MongoDB Retrieval Load Testing (Week 9)** | `python -m unittest tests/test_mongodb_load_week9.py` | Part A (Atlas status) & Part B (in-memory fallback concurrency 1, 5, 10, 20) | **9/9 PASSED** |
| **Passwordless Email Auth & Security (Week 9)** | `python -m unittest tests/test_passwordless_auth_week9.py` | HMAC-SHA256, constant-time compare, CSRF defense, 404 prod protection, session isolation | **31/31 PASSED** |
| **Browser Auth & Guest Experience (Week 9)** | `python -m unittest tests/test_browser_auth_guest_week9.py` | Default guest mode, full browser OTP authentication, saved trips modal | **2/2 PASSED** |
| **Ethical Compliance, Masking & Logging (Week 10)** | `python -m unittest tests/test_week10_ethical_compliance.py` | PII masking, token/OTP redaction, structured event logging, correlation ID, Track A/B isolation | **23/23 PASSED** |
| **Frontend Production Build** | `npm run build` (in `frontend/`) | Vite production assets | **PASSED (0 errors)** |
| **Frontend Lint** | `npm run lint` (in `frontend/`) | oxlint syntax & rules | **PASSED (0 errors, 0 warnings)** |

---

### Full-Project Regression Suite Run
To run all 164 automated tests across Weeks 5, 6, 7, 8, 9, and 10 in a single execution:
```powershell
python -m unittest tests.test_rpa_availability_week5 tests.test_rpa_error_handling_week6 tests.test_agent_rpa_integration_week7 tests.test_user_controlled_workflow_week8 tests.test_e2e_system_integration_week9 tests.test_tool_calling_accuracy_week9 tests.test_mongodb_load_week9 tests.test_passwordless_auth_week9 tests.test_browser_auth_guest_week9 tests.test_week10_ethical_compliance
```
*Result:* **164 tests ran — 0 failures, 0 errors.**

---

### Key Milestone Documentation
- **Pre-Demo End-to-End Acceptance Report (Final):** [`docs/FINAL_PRE_DEMO_END_TO_END_VERIFICATION_REPORT.md`](docs/FINAL_PRE_DEMO_END_TO_END_VERIFICATION_REPORT.md) — 100% Core Acceptance Criteria Verified (`READY FOR TOMORROW'S DEMO` ✅)
- **Team Onboarding & Setup Guide:** [`TEAM_SETUP.md`](TEAM_SETUP.md)
- **Week 5 Documentation:** [`docs/Week5_RPA_Availability_Documentation.md`](docs/Week5_RPA_Availability_Documentation.md)
- **Week 6 Documentation:** [`docs/Week6_RPA_Error_Handling_Documentation.md`](docs/Week6_RPA_Error_Handling_Documentation.md)
- **Week 7 Documentation:** [`docs/Week7_Agent_RPA_Integration_Documentation.md`](docs/Week7_Agent_RPA_Integration_Documentation.md)
- **Week 8 Documentation:** [`docs/Week8_User_Controlled_Workflow_Documentation.md`](docs/Week8_User_Controlled_Workflow_Documentation.md)
- **Shrine Board Feasibility & Dual-Track Architecture:** [`docs/Shrine_Board_RPA_Feasibility_Assessment.md`](docs/Shrine_Board_RPA_Feasibility_Assessment.md)
- **Week 9 E2E System Integration:** [`docs/Week9_System_Integration_and_E2E_Testing.md`](docs/Week9_System_Integration_and_E2E_Testing.md)
- **Week 9 MongoDB Load Testing:** [`docs/Week9_MongoDB_Load_Test_Report.md`](docs/Week9_MongoDB_Load_Test_Report.md)
- **Week 9 Passwordless Email Authentication:** [`docs/Passwordless_Email_Authentication.md`](docs/Passwordless_Email_Authentication.md)
- **Week 10 Ethical Boundary & Compliance Audit:** [`docs/Week10_Ethical_Boundary_and_Compliance_Audit.md`](docs/Week10_Ethical_Boundary_and_Compliance_Audit.md)
- **Week 10 Data Privacy & Logging Implementation:** [`docs/Week10_Data_Privacy_and_Logging_Implementation.md`](docs/Week10_Data_Privacy_and_Logging_Implementation.md)

---

## 9. Final Mentor Demonstration Checklist

### Step-by-Step Live Walkthrough (10 Steps)

1. **Service Verification:**
   - Launch FastAPI (`uvicorn backend.main:app --port 8000`) and React frontend (`npm run dev -- --port 5173`).
   - Open `http://127.0.0.1:8000/api/health` to confirm `{"status": "healthy"}`.
2. **Choice Screen Presentation:**
   - Navigate to `http://127.0.0.1:5173/` and click *"Plan Your Yatra"*.
   - Point out that neither mode is forced: Option 1 (*"Plan with a Form"*) and Option 2 (*"Chat with AI"*) are presented equally.
3. **Form-Based Structured Intake:**
   - Select *"Plan with a Form"*.
   - Configure: Departure City = Delhi, 2 Pilgrims, 3 Days, Train mode, Normal Darshan.
   - Click *"Search Yatra Options"*.
4. **Transport & Accommodation Selection:**
   - Select verified train (e.g. Vande Bharat Express) on Step 2.
   - Proceed to Step 3 and select certified guest house or skip hotel.
5. **Interactive Sightseeing Discovery:**
   - Step 4 displays all 29 destinations.
   - Demonstrate real-time search (type *"Patnitop"*), category tabs with live count badges, and expand *"View Heritage Details"*.
   - Select **Bhairavnath Temple** (trek route) and **Patnitop** (distant mountain excursion).
6. **Generating Feasibility Advisories (Journey A & D):**
   - Click *"Generate Day-Wise Itinerary"*.
   - Point out that **Bhairavnath Temple** is green-badged and scheduled on Day 2.
   - Point out the **Infeasible Advisory Banner** for **Patnitop**: explains that 85 km on mountain roads cannot fit into a 3-day trip without physical exhaustion, recommending 4+ days.
   - Verify Day 2 remains exclusively dedicated to the holy trek.
7. **Bi-Directional Mode Switching (Journey C):**
   - Click *"💬 Switch to Chat"* on the top switcher bar.
   - Observe that the chat loads with shared trip context (`📍 Delhi • 2 Pilgrims • 3 Days`), itinerary badges, and selected destinations.
8. **Conversational Revision & Guardrails (Journey B):**
   - Ask an informational query: *"What are the Aarti timings at Bhawan?"*.
   - Demonstrate that the bot returns rich spiritual timings without wiping trip details or resetting the plan.
   - Request a revision: *"Change our trip to 5 days and add Baba Dhansar"*.
   - Note that the plan updates to Revision #2 and re-evaluates feasibility.
9. **Authorization Gate & Tamper-Proofing (Journey D):**
   - Return to Form mode (*"📋 Switch to Form"*) and proceed to Step 6 (*"Authorization & RPA"*).
   - Point out the Human Confirmation Gate. Check the authorization box to record server-side authorization.
   - Click *"⚡ Run Playwright RPA Mock Verification"* to watch the headless browser agent execute form automation.
10. **Confirmation & Yatra Pass:**
    - Click *"Authorize & Confirm Booking"*.
    - Show the confirmed reference ID (e.g. `VD26753AC0`), divine blessing message, and Katra RFID reporting counter instructions.

---

### Emergency Fallback Procedures
- **If Port 8000 or 5173 is already in use:**
  ```powershell
  # Check and terminate conflicting processes on Windows:
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
  Get-Process -Id (Get-NetTCPConnection -LocalPort 5173).OwningProcess | Stop-Process -Force
  ```
- **If Groq API Key quota is exhausted or network is offline:**
  - The deterministic feasibility engine, travel search, hotel lookup, and sightseeing browser continue to operate 100% locally from CSV inventories and SQLite without external LLM calls.
  - Informational tourism questions gracefully fall back to local rule-based responses in `explore_data.py`.

---

## 10. Technical Limitations & Project Boundaries

1. **Curated & Grounded Data Catalogue:**
   - Schedules, fares, guest houses, and shrine slots are drawn from curated datasets in `data/`. No official public unauthenticated APIs exist for IRCTC train bookings or SMVDSB darshan slots.
2. **Mock RPA Automation Sandbox:**
   - The Playwright RPA agent operates strictly within a local mock checkout sandbox. It does **not** interface with live payment gateways, credit card processing, OTPs, CAPTCHAs, or government servers.
3. **Session Scope:**
   - Web session persistence uses `sessionStorage` (scoped to the individual browser tab) to prevent cart cross-contamination between tabs. Persistent server-side state is stored in local ACID SQLite (`data/sessions.db`).

---

## 11. Academic Disclaimer

This project is an academic prototype developed for educational demonstration purposes. It is not affiliated with, authorized, or endorsed by the Shri Mata Vaishno Devi Shrine Board (SMVDSB), Indian Railways (IRCTC), or any commercial transit provider.
