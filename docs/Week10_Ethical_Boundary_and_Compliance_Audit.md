# Week 10: Ethical Boundary and Platform Compliance Audit
## Project: Tourism GPT with RPA — Maa Vaishno Devi Yatra Booking Agent

---

## Executive Summary

As part of the final-year engineering deliverables for **Week 10**, this audit evaluates the ethical boundaries, legal compliance, terms of service adherence, and user privacy safeguards of the **Maa Vaishno Devi Yatra Booking Agent**. 

The system incorporates natural language processing (Groq LLM/LangChain), automated availability checking, itinerary optimization, simulated robotic process automation (Playwright RPA), and optional passwordless authentication. Because pilgrimages to the Shri Mata Vaishno Devi Shrine involve high-volume religious sentiment, sensitive biometric/RFID identity controls, financial transactions, and official government regulations, automated interactions must adhere to strict ethical and legal boundaries.

This document formally details:
1. The **Dual-Track Architectural Boundary** separating mock sandbox automation from official platforms.
2. An exhaustive **Automated Interaction Inventory**.
3. A grounded **Terms of Service (ToS) & Regulatory Policy Assessment** across all external platforms.
4. **Data Handling & Privacy Risk Analyses** under Indian data protection law (DPDP Act 2023).
5. **Mitigation Measures, Safeguards, and Architectural Decisions** implemented in Week 10.
6. **Remaining Limitations** and operational boundaries.

---

## 1. Scope of the Review

The audit encompasses all automated, network-connected, and programmatic actions across the repository:

- **Browser Automation & RPA (`agents/rpa_agent.py`, `yatra_mock_portal.html`):** Headless Chromium execution, DOM inspection, availability checking, retry mechanisms, rate backoffs, and Human-in-the-Loop (HITL) checkpoints.
- **AI Agent Tool Execution (`agents/availability_agent.py`, `agents/coordinator.py`, `agents/mongodb_agent.py`):** Dynamic tool binding, query generation, LLM reasoning loops, parameter extraction, and deterministic fallbacks.
- **Authentication & User Data Flows (`agents/auth_service.py`, `backend/routes/auth.py`):** Passwordless email OTP issuance, cryptographic session token handling, CSRF defense, rate limiting, and database persistence.
- **External Network Services:** Groq Cloud API, MongoDB Atlas, Open-Meteo Weather API, Airtable, and official Shrine Board websites.
- **Persistence Layers:** Client localStorage, browser cookies, SQLite ACID stores (`sessions.db`, `auth_store.db`), and MongoDB collections.
- **Logging & Diagnostic Streams:** Starlette access logs, Python standard logging, Playwright trace logs, and frontend browser console output.

---

## 2. Shrine Board Portal Boundary: The Dual-Track Architecture

The fundamental ethical and legal safeguard of this project is the **Dual-Track Architecture**, establishing an impassable boundary between simulated engineering experimentation and official pilgrimage administration.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                DUAL-TRACK ARCHITECTURE BOUNDARY                        │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│  TRACK A: Local Simulated Sandbox        │  TRACK B: Official Shrine Board Live Portal │
│  (Engineered for Automation & Testing)   │  (Protected Religious & Governmental Body)  │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│ • Targets: file:///.../yatra_mock_portal.html│ • Domain: https://www.maavaishnodevi.org/   │
│ • Local isolated HTML/CSS/JS sandbox     │ • Live government & religious services     │
│ • Permitted: Full Playwright automation  │ • STRICTLY PROHIBITED: Automated scraping,   │
│ • Permitted: Headless slot extraction    │   headless booking, bot bypass, or OTP/    │
│ • Permitted: Retry testing & backoff     │   CAPTCHA interception                     │
│ • Permitted: State validation & error injection│ • Policy: Direct user redirection only │
│ • Prominently labeled as SIMULATED       │ • Mandatory human self-booking on official  │
│ • Zero financial transactions or charges │   counters / verified payment gateways      │
│ • Zero live Shrine Board server load     │ • Zero credentials or payments stored       │
└──────────────────────────────────────────┴─────────────────────────────────────────────┘
```

### Track A — Local Simulated Portal (Permitted Automation)
- **Controlled Environment:** Playwright automation runs against a dedicated local HTML simulation (`yatra_mock_portal.html`) loaded via local `file://` URIs or localhost.
- **Experimental Testing:** Automated availability checking, calendar navigation, slot extraction, transient network retry handling, structural DOM change detection, and simulated form completion are strictly contained within this local sandbox.
- **Clear User Labeling:** The UI and API responses prominently label all extracted slots and simulated bookings as **SIMULATED / TEST DATA**. At no point is mock availability misrepresented to pilgrims as live Shrine Board inventory.
- **Zero Live Server Impact:** Track A incurs exactly 0 HTTP requests against the live Shri Mata Vaishno Devi Shrine Board (SMVDSB) infrastructure.

### Track B — Official Shrine Board Portal (Ethical & Legal Safeguards)
- **Zero Bot Automation:** The official portal (`www.maavaishnodevi.org`) is **never** targeted by headless browser sessions, automated scripts, crawlers, or booking bots.
- **No Access Control Bypasses:** The application does not attempt to bypass CAPTCHA, SMS/Email OTPs, rate limits, Cloudflare bot protections, or user login screens of the official website.
- **Handoff & Deep Linking:** When a user wishes to make an official darshan, battery car, helicopter, or room reservation, the application directs them via official HTTPS links to `https://www.maavaishnodevi.org/`.
- **Manual Human Execution:** Pilgrims independently register, log in, verify identity (Aadhaar/Passport), solve CAPTCHAs, complete two-factor authentication, and execute verified bank payments directly on the official portal.
- **Zero Credential Persistence:** The application never solicits, inspects, transmits, or stores Shrine Board passwords, banking OTPs, credit/debit card numbers, UPI PINs, or government identity tokens.

---

## 3. Automated Interaction Inventory

The following table catalogs every programmatic and automated action performed across the project:

| ID | Automated Interaction | Trigger / Component | Automation Technology | Target Endpoint / Resource | Frequency / Rate | Ethical & Compliance Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **INT-01** | Simulated Yatra Availability Check | User selects date on UI / `POST /api/yatra/rpa/availability` | Playwright Chromium (Headless) | Local file: `yatra_mock_portal.html` | On-demand (User-initiated) | **Track A (Permitted):** Local simulation; zero external network load. |
| **INT-02** | Calendar Navigation & Slot Extraction | `check_yatra_slot_availability` in `rpa_agent.py` | Playwright Chromium DOM interaction | Local file: `yatra_mock_portal.html` | Max 3 attempts on transient failure | **Track A (Permitted):** Exponential backoff (0.5s–2.0s); halts on permanent DOM structural change. |
| **INT-03** | Human-in-the-Loop Workflow Pausing | Critical step (Payment / OTP simulation) in `rpa_agent.py` | Playwright `wait_for_selector` + state pause | Local file: `yatra_mock_portal.html` | On-demand | **Track A (Permitted):** Enforces human verification before proceeding; session expires in 15 min. |
| **INT-04** | Agent Tool Calling & Slot Checking | LangChain `AvailabilityAgent` / `check_slot_availability_rpa` | Python tool binding (`@tool`) | `rpa_agent.py` mock engine | On-demand during chat query | **Track A (Permitted):** Deterministic tool binding; sanitized parameters logged. |
| **INT-05** | Destination & Rule Retrieval | LangChain `MongoDBAgent` / `explore_data.py` | PyMongo / In-memory Pandas fallback | MongoDB Atlas cluster (`yatra_db`) | On-demand during itinerary queries | **Permitted:** Read-only queries against self-hosted student database; fallback to local JSON. |
| **INT-06** | Natural Language Inference | `ConversationAgent` & ChatGroq client | HTTPS REST API | `https://api.groq.com/openai/v1/chat/completions` | Per chat message / intake completion | **Permitted:** Standard commercial LLM API with authorized developer API keys. |
| **INT-07** | Live Katra Weather Forecast | `weather.py` / `fetch_weather_forecast` | HTTPS GET Request | `https://api.open-meteo.com/v1/forecast` | On-demand / cached | **Permitted:** Open-Meteo free non-commercial open API; complies with attribution guidelines. |
| **INT-08** | Passwordless Email OTP Dispatch | `auth_service.py` / `request_otp` | Python `smtplib` / `MockEmailProvider` | SMTP Host (or in-memory mock outbox) | Rate-limited (1 request / 60s per email) | **Permitted:** Standard transactional OTP verification; hashes stored on disk. |
| **INT-09** | Session State & Itinerary Persistence | `routes/auth.py` / `routes/yatra.py` | SQLite ACID / MongoDB Atlas | Local `data/sessions.db` & remote collections | Per user save action | **Permitted:** Isolated user data; strict ownership checks; guests isolated. |

---

## 4. Platform Terms of Service & Regulatory Policy Assessment

Each external platform or service utilized by or referenced in the application has been assessed against its published terms of service, acceptable use policies, and statutory frameworks.

> [!NOTE]
> This review documents engineering risk evaluations and implemented technical safeguards. It does not constitute formal legal counsel. Where official terms do not explicitly define technical API or bot access permissions, automated access is classified as **Requires clarification / written permission**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        TERMS & REGULATORY COMPLIANCE MATRIX                            │
├──────────────────────────┬─────────────────────────────────┬───────────────────────────┤
│ Platform / Entity        │ Official Policy Source          │ Interaction Classification│
├──────────────────────────┼─────────────────────────────────┼───────────────────────────┤
│ 1. Shri Mata Vaishno     │ Official SMVDSB Portal Terms    │ Live Portal Automation:   │
│    Devi Shrine Board     │ (maavaishnodevi.org/terms.aspx) │ Requires clarification /  │
│                          │                                 │ written permission;       │
│                          │                                 │ Track A Mock: PERMITTED   │
├──────────────────────────┼─────────────────────────────────┼───────────────────────────┤
│ 2. Groq Cloud Services   │ Groq Terms of Service & AUP     │ Authorized API:           │
│                          │ (groq.com/terms-of-service)     │ PERMITTED                 │
├──────────────────────────┼─────────────────────────────────┼───────────────────────────┤
│ 3. MongoDB Atlas         │ MongoDB Cloud Terms of Service  │ Customer Database Access: │
│                          │ (mongodb.com/legal/terms)       │ PERMITTED                 │
├──────────────────────────┼─────────────────────────────────┼───────────────────────────┤
│ 4. Open-Meteo Weather    │ Open-Meteo Terms of Use         │ Non-Commercial Free API:  │
│                          │ (open-meteo.com/en/terms)       │ PERMITTED (With Attribution│
├──────────────────────────┼─────────────────────────────────┼───────────────────────────┤
│ 5. IRCTC / Indian Rail   │ IRCTC Ticketing Conditions &    │ Live Ticketing Automation:│
│                          │ Sections 43/66 IT Act 2000      │ RESTRICTED / Requires     │
│                          │ (irctc.co.in/eticketing/terms)  │ written permission;       │
│                          │                                 │ Local CSV Data: PERMITTED │
├──────────────────────────┼─────────────────────────────────┼───────────────────────────┤
│ 6. Indian DPDP Act 2023  │ Ministry of Electronics & IT    │ Aligned with DPDP         │
│                          │ (Digital Personal Data Prot.)   │ Principles via Technical  │
│                          │                                 │ Privacy Measures          │
└──────────────────────────┴─────────────────────────────────┴───────────────────────────┘
```

### 1. Shri Mata Vaishno Devi Shrine Board (SMVDSB)
- **Official Source:** SMVDSB Official Portal Terms of Service & Guidelines (`https://www.maavaishnodevi.org/terms.aspx`, `https://www.maavaishnodevi.org/faq.aspx`).
- **Relevant Terms & Restrictions:**
  - Online booking services are offered for personal, non-commercial pilgrim registration.
  - While the website terms do not publish a technical web-crawler policy or `robots.txt` prohibiting general search indexing, automated bulk booking, ticket reselling, and circumventing security checkpoints (OTP/CAPTCHA) are unauthorized under ticketing regulations.
  - Automated interaction with the live SMVDSB infrastructure is therefore classified as: **Requires clarification / written permission**.
- **Application Interaction:** Zero automated requests hit `maavaishnodevi.org`. The application provides verified educational information (timings, dress codes, luggage rules, RFID counter locations) and deep-links pilgrims to the official website for self-directed booking.
- **Classification:** **Track A Local Simulation: Permitted** | **Live Portal Automation: Requires clarification / written permission**.
- **Compliance Action:** Maintain the strict Track A / Track B boundary. Do not automate `maavaishnodevi.org`. Display official disclaimer: *"This agent is an academic AI assistant. Official bookings must be performed directly by pilgrims on the official SMVDSB portal."*

### 2. Groq Cloud Services
- **Official Source:** Groq Cloud Terms of Service & Acceptable Use Policy (`https://groq.com/terms-of-service/`).
- **Relevant Terms & Restrictions:**
  - Prohibition on generating harmful, defamatory, or unlawful content; attempting to reverse-engineer model weights; or overloading inference infrastructure.
  - Prohibition on transmitting unencrypted sensitive biometric or high-risk financial data into prompts.
- **Application Interaction:** Text-only prompt completion using `llama-3.3-70b-versatile` for natural language chat, itinerary planning, and slot query parameter extraction via authorized developer API keys.
- **Classification:** **Permitted**.
- **Compliance Action:** Enforce prompt sanitization; truncate input strings; never pass email OTPs, passwords, or full credit card numbers to LLM completions. Deterministic fallback activates if Groq API returns 429/503.

### 3. MongoDB Atlas (Cloud NoSQL)
- **Official Source:** MongoDB Cloud Terms of Service (`https://www.mongodb.com/legal/terms-of-use`).
- **Relevant Terms & Restrictions:**
  - Customer responsibility for data stored, access control keys, and database credential security.
  - Ban on hosting malicious payloads or violating privacy rights.
- **Application Interaction:** Stores 29 public sightseeing records, verified yatra FAQs, and optional user-saved itineraries (`users`, `saved_itineraries`) using authenticated connection credentials.
- **Classification:** **Permitted**.
- **Compliance Action:** Connection string credentials managed strictly via `.env`; TLS 1.3 encryption in transit; database whitelisting; automatic in-memory JSON fallback if Atlas connection times out.

### 4. Open-Meteo Weather API
- **Official Source:** Open-Meteo Terms of Use (`https://open-meteo.com/en/terms`).
- **Relevant Terms & Restrictions:**
  - Free access permitted for non-commercial and research applications; attribution to Open-Meteo required.
  - Rate limit guidelines (< 10,000 requests/day; avoid rapid bursts).
- **Application Interaction:** Retrieves daily temperatures, precipitation probability, and wind speeds for Katra (`lat=32.99, lon=74.93`).
- **Classification:** **Permitted**.
- **Compliance Action:** Display *"Weather data powered by Open-Meteo"* in UI; cache responses to minimize network requests.

### 5. Indian Railway Catering and Tourism Corporation (IRCTC) / Indian Railways
- **Official Source:** IRCTC Terms of Service and Railway IT Security Policy (Sections 43 and 66 of the Information Technology Act, 2000).
- **Relevant Terms & Restrictions:**
  - Commercial bot automation, automated Tatkal script bookings, and unauthorized scraping of live ticketing systems are strictly restricted under IRCTC rules and the IT Act 2000.
  - Programmatic automated access to live IRCTC systems is therefore classified as: **Restricted / Requires written permission**.
- **Application Interaction:** The project does **NOT** automate, scrape, or connect to IRCTC servers. Static, publicly available train numbers (e.g., *Vande Bharat Express 22439*, *Shri Shakti Express 22461*) and indicative government fares are stored in static local CSV files (`trains.csv`) for budgeting estimation only.
- **Classification:** **Live Ticketing Automation: Restricted / Requires written permission** | **Local Educational Reference: Permitted**.
- **Compliance Action:** Display explicit notice: *"Train schedules and fares are indicative. Bookings must be made via official IRCTC app/website."*

### 6. Digital Personal Data Protection Act (DPDP Act 2023, India)
- **Official Source:** Ministry of Electronics and Information Technology (MeitY), Government of India — The Digital Personal Data Protection Act, 2023.
- **Relevant Principles:**
  - Purpose Limitation: Data must be collected solely for the stated purpose (yatra planning).
  - Data Minimization: Avoid collecting superfluous personal identifiers.
  - Reasonable Security Safeguards: Prevent unauthorized exposure of personal contact details and authentication tokens.
- **Application Interaction:** Guest Mode requires zero personal data. Registered users provide only an email address.
- **Classification:** **Aligned with DPDP Principles via Implemented Technical Measures** *(Note: Formal statutory compliance is a legal determination requiring independent organizational audit; the application implements standard technical privacy and data minimization controls)*.
- **Compliance Action:** Zero plain OTPs stored on disk; sensitive user data masked in all diagnostic logs; passwordless session tokens cryptographic and revokable.

---

## 5. Data Handling and Privacy Assessment

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DATA PRIVACY & STORAGE ARCHITECTURE                             │
├───────────────────────┬────────────────────────────────┬───────────────────────────────┤
│ Data Element          │ Persistence Mechanism          │ Privacy & Security Treatment  │
├───────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ 1. Guest Sessions     │ SQLite (`sessions.db`)         │ Ephemeral; zero PII required. │
│ 2. Email Address      │ SQLite / MongoDB Atlas         │ Masked in logs (p*****i@...). │
│ 3. 6-Digit Email OTP  │ Memory cache + SHA-256 hash    │ NEVER logged; [REDACTED];     │
│                       │                                │ Salted hash only; 5 min TTL.  │
│ 4. Session Tokens     │ SQLite / HTTP-only Bearer      │ Cryptographic (32-byte token);│
│                       │                                │ Masked in logs; Revokable.    │
│ 5. Saved Itineraries  │ SQLite / MongoDB Atlas         │ Scoped to authenticated user; │
│                       │                                │ Isolated tenant queries.      │
│ 6. API Keys & Secrets │ `.env` file only               │ Excluded from git; Regex      │
│                       │                                │ scrubber removes from logs.   │
│ 7. Payment Details    │ NOT COLLECTED                  │ Architectural prohibition;    │
│                       │                                │ Zero payment gateway code.    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Guest-First Invariant:** Over 90% of user activity (chat, exploring 29 destinations, generating itineraries, testing mock RPA) requires **zero registration, zero email, and zero tracking cookies**.
2. **Cryptographic OTP Storage:** When a user opts to save itineraries, verification OTPs are generated via `secrets.choice` and hashed using HMAC-SHA-256 before disk storage in `data/auth_store.db`. Raw OTPs are destroyed from memory upon verification or expiration (300 seconds).
3. **Session Revocation:** Logout immediately updates the SQLite/MongoDB record to `revoked = 1`, preventing token replay attacks.
4. **Data Isolation:** User saved itineraries are partitioned by `user_id`. Guest sessions cannot query or overwrite authenticated user records.

---

## 6. Identified Ethical Risks & Engineering Mitigations

| Risk ID | Identified Ethical Risk | Severity | Implemented Engineering Mitigation |
| :--- | :--- | :--- | :--- |
| **ETH-01** | **Misleading Pilgrims on Availability:** Users could mistake mock slots for real darshan/helicopter inventory, leading to missed pilgrimages. | **CRITICAL** | Prominent visual badge in UI: *"Simulated Environment — Track A Sandbox"*. Informational banner clarifying that official reservations must be confirmed at `maavaishnodevi.org`. |
| **ETH-02** | **Accidental Scraping of Live Shrine Portal:** Developers or users could configure RPA to target the live SMVDSB domain, violating terms and triggering IP bans. | **HIGH** | Strict hardcoded boundary in `agents/rpa_agent.py`: browser navigation is restricted to local `file://` mock portal paths. The agent raises an error if an external booking URL is passed to headless execution. |
| **ETH-03** | **PII and Secret Leakage in Logs:** Tracebacks, server logs, or error responses could expose pilgrim email addresses, OTP codes, or Groq API keys. | **HIGH** | Implemented `utils/masking.py` and `SanitizingFormatter` in `utils/logger.py`. Auto-scrubs all log streams: emails become `p*****i@example.com`, OTPs and tokens become `[REDACTED]`, and Groq keys `gsk_...` are erased. |
| **ETH-04** | **Credential Phishing & Misuse:** Untrusted third-party clones could solicit Shrine Board passwords from devotees under the guise of an "automated booking bot". | **HIGH** | The application never includes input fields for Shrine Board passwords, credit cards, CVVs, or bank logins. Authentication is strictly passwordless via the user's personal email. |
| **ETH-05** | **Over-Exertion & Physical Safety in Trek Schedules:** Pilgrims (including elderly family members) could be given dangerous itineraries scheduling distant mountain trips on trek days. | **HIGH** | Deterministic Feasibility Engine: Day 2 is strictly reserved as an exclusive holy trek day. Distant excursions (Patnitop, Sinthan Top) are programmatically rejected with duration advisories. |
| **ETH-06** | **Denial of Service via Uncontrolled RPA Retries:** Automated retry loops could overwhelm target servers if mock endpoints become unstable. | **MEDIUM** | Bounded exponential backoff: Maximum 3 retries. Immediate handover to human (`HumanInterventionRequired`) upon structural DOM mismatch; 15-minute workflow timeout. |

---

## 7. Compliance Decisions & Action Items

1. **Strict Preservation of Track A / Track B Separation:**
   - **Decision:** Keep the Playwright automation engine permanently anchored to `yatra_mock_portal.html`. Do not develop or deploy scrapers targeting `maavaishnodevi.org`.
   - **Rationale:** Ensures compliance with SMVDSB terms, prevents IP blocks, avoids legal liability under the IT Act 2000, and protects the integrity of the pilgrimage booking system.

2. **Universal Log Sanitization at the Root Logging Layer:**
   - **Decision:** Attach `SanitizingFormatter` to both console and file handlers in `backend/main.py` and `utils/logger.py`.
   - **Rationale:** Ensures that even unhandled third-party exceptions (Starlette, Uvicorn, LangChain, Groq) cannot leak sensitive user information into application logs.

3. **Voluntary Authentication (No Compulsory Login Walls):**
   - **Decision:** Maintain Guest Mode as the permanent default entry point.
   - **Rationale:** Comply with the Data Minimization principle of the DPDP Act 2023. Devotees seeking travel guidance should never be forced to surrender personal contact details.

4. **Transparent Error Disclosure:**
   - **Decision:** Backend logs record structured diagnostic metadata (`error_category`, `correlation_id`, `retry_attempt`) while user-facing clients receive friendly, actionable messages without internal stack traces.
   - **Rationale:** Prevents security reconnaissance by malicious actors while ensuring users understand operational issues (e.g., *"Verification code expired. Please request a new code."*).

---

## 8. Remaining Limitations

1. **Live Inventory Integration:**
   - Because SMVDSB does not currently publish a public, open REST API for real-time yatra quota checking, live darshan availability cannot be displayed inside the application without violating the anti-scraping policy. Pilgrims must check final availability directly on `maavaishnodevi.org`.
2. **Third-Party Email SMTP Quotas:**
   - In production deployments using real SMTP providers (SendGrid, AWS SES, Gmail SMTP), rate limits and anti-spam deliverability filters apply. The application provides `MockEmailProvider` for zero-dependency local academic evaluation.
3. **Local Machine Dependency for RPA Sandbox:**
   - The Playwright Chromium browser relies on a local GUI/headless display environment. In cloud serverless containers with minimal memory, Playwright must run with `--disable-gpu` and `--no-sandbox`.

---

## 9. Conclusion

The Maa Vaishno Devi Yatra Booking Agent implements robust ethical boundaries, respects platform terms of service, and incorporates engineering safeguards aligned with the data protection principles of the Indian DPDP Act 2023. By enforcing the **Dual-Track Architecture**, sensitive data masking, and structured transparent logging, the project demonstrates how modern agentic AI and RPA can be safely explored in high-stakes pilgrimage domains while strictly preventing unauthorized automation against official government or religious platforms.
