# Official Vaishno Devi Shrine Board Website — RPA Feasibility Assessment

**Project:** Tourism GPT with RPA — Yatra Booking Agent (Vaishno Devi)  
**Deliverable:** Pre-Week 8 Feasibility & Architectural Research Assessment  
**Document Path:** `docs/Shrine_Board_RPA_Feasibility_Assessment.md`  
**Target Entities:** 
- Official Informational Portal: [https://www.maavaishnodevi.org/](https://www.maavaishnodevi.org/)
- Official Online Services Portal: [https://online.maavaishnodevi.org/](https://online.maavaishnodevi.org/)
- Operating Authority: Shri Mata Vaishno Devi Shrine Board (SMVDSB), Katra, Jammu & Kashmir, India  
**Date of Assessment:** October 2026  
**Status:** Complete — Read-Only Architectural Feasibility Study  

---

## 1. Executive Summary

### 1.1 Project Context & Objective
The **Vaishno Devi Yatra Booking Agent** combines a conversational Multi-Agent LLM architecture (FastAPI, React 19, LangChain, ChatGroq / GPT-OSS-20B) with Robotic Process Automation (Playwright Chromium automation). Over Weeks 4 through 7, the project implemented:
1. **Week 4:** Safe mock checkout booking automation with human authorization safeguards.
2. **Week 5:** Playwright-based availability calendar navigation, dynamic wait synchronization, and structured slot extraction.
3. **Week 6:** Bounded retry-and-escalate policies, post-action DOM state validation, and pause-and-handover error handling.
4. **Week 7:** LangChain tool integration layer exposing availability checking as a callable tool for conversational AI.

Prior to commencing Week 8, this assessment was commissioned to evaluate whether our existing Playwright RPA architecture can be safely, legally, and reliably adapted to the live, official Shri Mata Vaishno Devi Shrine Board website (`maavaishnodevi.org` and `online.maavaishnodevi.org`).

### 1.2 Core Finding
Adapting unattended, automated Playwright scraping or RPA form submission directly against the live official Shrine Board website is **technically impractical, legally restricted, and architecturally ill-advised without explicit written authorization and dedicated API access from the Shrine Board**. 

The official booking ecosystem enforces mandatory mobile-number OTP authentication, alphanumeric CAPTCHA challenges, strict anti-agent booking policies, and Single-Page Application (SPA) session protections. Unauthenticated users cannot access real-time slot or room availability calendars. Furthermore, the Shrine Board's terms of service explicitly prohibit third-party travel agents and unauthorized automated booking mechanisms.

### 1.3 Executive Recommendation
**DO NOT AUTOMATE LIVE WEBSITE WITHOUT EXPLICIT WRITTEN PERMISSION.**  
The project must adopt a **Dual-Track Architecture**:
- **Track A (Automated Sandbox):** Retain our robust Playwright RPA workflow against the local mock portal (`yatra_mock_portal.html`) for algorithmic benchmarking, unit/integration testing, and academic defense of multi-agent and RPA synchronization techniques.
- **Track B (Official Advisory & Deep-Linking):** Utilize the conversational LLM agent to deliver verified static information (aarti timings, trekking routes, battery car rules, helicopter tariffs, weather advisories) and seamlessly guide pilgrims with deep links to official Shrine Board portals for manual, authenticated execution.
- **Clear Attribution:** All simulated availability responses must explicitly declare their mock sandbox provenance to ensure pilgrims are never misled into believing test data represents live government inventory.

---

## 2. Official Website Inspection & Technical Analysis

### 2.1 Architectural Topology
Inspection of the official Shrine Board digital estate reveals a two-tier decoupled architecture:

```
                            +-----------------------------------------------+
                            | Shri Mata Vaishno Devi Shrine Board (SMVDSB)  |
                            +-----------------------------------------------+
                                                    |
                      +-----------------------------+-----------------------------+
                      |                                                           |
                      v                                                           v
+-------------------------------------------+               +-------------------------------------------+
| Primary Informational CMS                 |               | Online Services & Transactional Portal    |
| Domain: https://www.maavaishnodevi.org/   |               | Domain: https://online.maavaishnodevi.org/|
| Platform: Drupal 9 (PHP / jQuery)         |               | Platform: Angular SPA (HTML5 History API) |
| Access: 100% Public & Unauthenticated     |               | Access: Mandatory Devotee Login (OTP)     |
| Purpose: Information, Guidelines, Notices |               | Purpose: Yatra Slips, Rooms, Helicopters  |
+-------------------------------------------+               +-------------------------------------------+
```

### 2.2 Publicly Accessible Information Identified
The informational portal (`https://www.maavaishnodevi.org/`) is completely accessible without authentication and provides static operational information:

| Information Category | Specific Data Elements Publicly Visible | Relevance to Tourism GPT Agent |
| :--- | :--- | :--- |
| **Holy Shrine Details** | History, Legend, Holy Cave layout, Aarti rituals, Charan Paduka, Adhkuwari, Sanjichhat, Bhawan. | High: Embedded in agent conversational RAG/fallback knowledge base. |
| **Aarti Timings** | Morning Aarti: 06:00 AM – 08:00 AM; Evening Aarti: 07:00 PM – 09:00 PM (varies slightly by season). | High: Used by Itinerary Agent to generate realistic daily schedules. |
| **Trekking Routes** | - Traditional Track (12.8 km): Katra $\rightarrow$ Banganga $\rightarrow$ Charan Paduka $\rightarrow$ Adhkuwari $\rightarrow$ Sanjichhat $\rightarrow$ Bhawan.<br>- Tarakote Marg (7.5 km to Adhkuwari): Cleaner, gentler gradient, battery car pathway, no animal traffic.<br>- Himkoti Track: Alternate scenic route to Bhawan. | High: Critical for customized pilgrim route recommendations based on age, fitness, and transport preference. |
| **Transport Services** | - Helicopter service tariffs and operational rules (Katra $\leftrightarrow$ Sanjichhat).<br>- Bhawan–Bhairon Ghati Passenger Ropeway (₹100, 3.75 min journey).<br>- Battery-operated vehicles between Adhkuwari and Bhawan (priority for senior citizens/differently-abled).<br>- Ponies, Pithus, and Palkis (notified government rates). | High: Informs budget generation and transport selection. |
| **Accommodations** | Location and descriptions of Shrine Board complexes: Niharika, Shakti Bhawan, Ashirwad, Trikuta Bhawan, Kalika Dham, Saraswati Dham, Vaishnavi Dham, Sanjichhat, and Bhawan. | High: Used for lodging recommendations and budget estimation. |
| **Yatra Guidelines & RFID** | Mandatory RFID Yatra Access Card issuance (free of cost), collection points (Railway Station, Bus Stand, Katra counters), penalty for non-compliance, plastic bans, medical precautions. | Critical: Must be communicated to users during yatra planning. |

### 2.3 Booking Categories & Services Offered
All transactional and quota-driven services reside on `https://online.maavaishnodevi.org/`:

1. **Yatra Parchi (Registration Slip):** Free advance travel permit required for all pilgrims above 5 years old.
2. **Room / Accommodation Reservations:** Rented guest houses, family rooms, and dormitory beds across Katra, Jammu, Adhkuwari, and Bhawan.
3. **Helicopter Services:** Sector tickets for Katra to Sanjichhat and return (operated by Global Vectra and Himalayan Heli).
4. **Attka Aarti & Special Poojan:** Individual Poojan, Shradha Suman Vishesh Poojan (SSVP), and morning/evening Attka Aarti participation.
5. **Battery Car Bookings:** Reserved online quota for eco-friendly transport on the Adhkuwari–Bhawan stretch.
6. **Prasad Seva & Online Donations:** Courier delivery of blessed prasad and financial contributions to Shrine Board trusts.

### 2.4 Availability Inspection: Can Availability Be Viewed Without Logging In?
**Findings:**
- **No real-time availability can be viewed without logging in.**
- When a user navigates to `https://online.maavaishnodevi.org/`, attempting to check room vacancies, helicopter seats, or Attka Aarti dates immediately redirects to the authentication gateway (`/#/guest/login` or `user/login`).
- Unlike public airline booking portals (e.g. Skyscanner or Google Flights) or train portals (IRCTC unauthenticated search), the SMVDSB portal does **not** expose a public, unauthenticated calendar or search interface.
- Quotas, available seat numbers, and date-wise status badges are rendered dynamically only *after* a verified devotee session token is attached to client-side API requests.

### 2.5 Dynamic Elements & Access Control Mechanisms
Inspection of the client-side technologies and protection layers on `online.maavaishnodevi.org` reveals substantial technical barriers to unattended automation:

1. **Angular Client-Side SPA Architecture:**
   - URL routing uses the client-side hash history fragment (`/#/`).
   - Page contents are not static HTML; they are compiled JavaScript bundles rendered dynamically upon route resolution.
2. **Mandatory Devotee Registration & Authentication:**
   - Devotees must create an account using First Name, Last Name, Gender, Date of Birth, Email ID, Valid Mobile Number, and Photo ID proof (Aadhaar, Passport, Voter ID, PAN).
3. **Two-Factor Authentication (OTP):**
   - Logging in requires entering a registered mobile number, requesting a One-Time Password (OTP), and entering the received SMS code.
   - For non-J&K prepaid mobile numbers, strict telecommunication restrictions in J&K necessitate alternate verification paths (e.g., email or WhatsApp OTP).
4. **CAPTCHA Challenges:**
   - Sign-in, registration, and transaction confirmation forms enforce distorted alphanumeric CAPTCHA images designed specifically to defeat headless automated browsers.
5. **Anti-Bot & Web Application Firewall (WAF) Protections:**
   - Rate limiting on API endpoints to prevent high-frequency polling.
   - Headless browser fingerprinting (detecting `navigator.webdriver`, missing browser plugins, or synthetic user interactions).
   - Ephemeral CSRF tokens and session timeout after brief inactivity.

---

## 3. RPA Compatibility Assessment: Mock Portal vs. Live Portal

### 3.1 Structural Comparison
The table below contrasts our current implementation with the live Shrine Board web environment:

| Dimension | Our Existing Implementation (`agents/rpa_agent.py` & `yatra_mock_portal.html`) | Live Official Portal (`online.maavaishnodevi.org`) | Adaptation Impact & Gap |
| :--- | :--- | :--- | :--- |
| **Hosting & Network** | Local sandboxed HTML file in temporary directory (`file://...`) or local server. Zero network dependencies. | Distributed cloud/datacenter web servers subject to latency, throttling, and outages. | Network latency, SSL handshakes, and potential server-side rate limits. |
| **Authentication Gate** | **None.** Immediate access to both booking form and availability calendar tabs. | **Mandatory.** Mobile OTP + Devotee Password + Photo ID verification. | Unattended RPA cannot authenticate without human OTP entry or credential storage. |
| **Bot Detection / CAPTCHA** | **None.** Clean, direct user-action emulation. | Alphanumeric CAPTCHA on login and checkout; WAF anti-scraping rules. | Headless Playwright will be blocked or challenged with CAPTCHAs. |
| **DOM Selectors** | Deterministic semantic IDs:<br>- `#tabCalendar`<br>- `#calendarDate`<br>- `#slotCategoryFilter`<br>- `#btnCheckAvailability`<br>- `#slotsContainer`<br>- `.slot-card` | Dynamic Angular component tags and obfuscated classes:<br>- `<mat-form-field>`<br>- `<mat-datepicker>`<br>- Dynamic dropdown overlays with generated GUIDs. | Complete rewrite of all Playwright locators; high brittleness upon frontend updates. |
| **Slot Data Model** | Unified mock dataset (`DEFAULT_MOCK_SLOTS`) containing: `slot_date`, `slot_time`, `session`, `category`, `price`, `seats_available`, `status`. | Separate, non-unified modules for Helicopters, Rooms, and Aarti; no single combined "darshan slot" view. | RPA would need multiple distinct multi-page navigation flows rather than a single form. |
| **Side Effects & Financials** | Safe mock submission returning simulated ID (`VD-RPA-XXXXXX`). Zero financial transactions. | Real payment gateway (BillDesk / SabPaisa) requiring bank OTP / UPI authentication. Real non-refundable debit. | Live booking submission must **never** be automated under any circumstances. |

### 3.2 Detailed Component Reusability Matrix
We analyzed our existing codebase across Weeks 5, 6, and 7 to assess reusability:

```
+---------------------------------------------------------------------------------------+
| COMPONENT REUSABILITY CLASSIFICATION                                                  |
+---------------------------------------------------------------------------------------+
|  [HIGHLY REUSABLE (Architectural / Logic Layer)]                                      |
|  - Week 6 Bounded Retry-and-Escalate Engine (retry_with_backoff)                      |
|  - Week 6 Post-Action State Validation Principles                                     |
|  - Week 6 Pause-and-Handover Trigger Framework (create_handover_result)               |
|  - Week 7 LangChain Tool Definition & Parameter Parsing (check_yatra_availability)    |
|  - Week 7 Orchestrator Intent Routing & Clarification Flow                            |
+---------------------------------------------------------------------------------------+
|  [PARTIALLY REUSABLE (Requires Configuration / Adapters)]                             |
|  - Data Normalization Schema (available / full / unavailable)                         |
|  - Data Integrity Validation (non-negative price, non-negative capacity)              |
|  - Audit Logging & Handover Screenshot Capture                                        |
+---------------------------------------------------------------------------------------+
|  [COMPLETELY INCOMPATIBLE (Must Be Replaced or Abandoned)]                            |
|  - Specific Playwright Locators (#calendarDate, #btnCheckAvailability, #slotsContainer)|
|  - Direct DOM Form Population without Session Tokens                                  |
|  - Automated Form Submission (Booking Checkout)                                       |
|  - Headless Unattended Execution without Human In-The-Loop                            |
+---------------------------------------------------------------------------------------+
```

#### Detailed Breakdown by Code Module:

1. **Week 5: Availability Navigation & Extraction (`agents/rpa_agent.py`):**
   - *Status:* **Incompatible at DOM Level; Reusable at Interface Level.**
   - The specific locators (`#tabCalendar`, `#calendarDate`, `#slotCategoryFilter`, `.slot-card`) are custom-built for our mock portal and do not exist on the live portal.
   - However, the function contract:
     ```python
     check_yatra_slot_availability(requested_date: str, category: Optional[str] = None) -> Dict[str, Any]
     ```
     is cleanly abstracted. If the Shrine Board ever provides an authorized REST API or authenticated webhook, this function's internals can be swapped with zero impact on the rest of the application.

2. **Week 6: Retry Strategy & State Validation:**
   - *Status:* **Highly Reusable.**
   - The exponential backoff engine (`retry_with_backoff`) correctly differentiates between transient recoverable errors (`PlaywrightTimeoutError`, slow loading spinners) and non-recoverable failures (`StructuralPageChangeError`, data integrity breaches).
   - In a production environment, bounded retries with jitter and clean session resets are industry best practices.
   - The **Pause-and-Handover** mechanism is especially relevant: encountering an OTP challenge or CAPTCHA on a real portal should immediately trigger `HANDOVER_REQUIRED`, alerting the human user to complete the verification step manually.

3. **Week 7: LangChain Integration Layer (`agents/availability_agent.py`, `agents/tools.py`, `langchain_tools.py`):**
   - *Status:* **100% Reusable.**
   - The tool definition `check_yatra_availability_tool` binds cleanly to ChatGroq / GPT-OSS-20B.
   - The LLM extracts the travel date and normalized category from conversational user input and validates ISO formatting before delegating.
   - The agent layer has zero direct awareness of browser locators, ensuring that changes to the underlying browser or API layer do not disrupt conversational AI behavior.

---

## 4. Legal, Policy, and Authorization Restrictions

### 4.1 Shrine Board Terms & Conditions Regarding Automation
The Shri Mata Vaishno Devi Shrine Board enforces explicit guidelines regarding booking authorization and system integrity:
1. **Exclusive Official Channel:**
   > *"The Shrine Board has not authorized any private travel agents, tour operators, or external websites to book services or issue yatra slips on its behalf. Devotees are cautioned against dealing with unauthorized entities."*
2. **Prohibition of Automated / Bot Reservations:**
   - In accordance with standard government e-governance policies and IT security guidelines, using automated bots, scrapers, or scripts to monitor, hold, or book pilgrimage quotas without prior written sanction is strictly prohibited.
   - Unsolicited high-frequency scraping can be treated as Denial of Service (DoS) or unauthorized system access under Section 43/66 of the Indian **Information Technology Act, 2000**.
3. **Mandatory In-Person RFID Collection:**
   - Even if a digital slip is secured, every individual pilgrim must physically present their original photo ID at Katra/Jammu counters to receive an RFID Yatra Access Card. Automated scripts cannot circumvent this physical validation.

### 4.2 Ethical and Academic Boundaries
For an undergraduate minor/capstone engineering project, attempting to bypass security controls on an active religious shrine portal carries grave ethical, legal, and academic risks:
- **No CAPTCHA Bypassing:** We must never integrate automated CAPTCHA solvers (e.g. 2Captcha, OCR bots) against government or public trust systems.
- **No OTP Interception:** We must never attempt to intercept or bypass SMS verification.
- **No Fake Devotee Accounts:** We must never script account creation or test real transactions using arbitrary citizen identities.
- **No Load Testing on Production:** We must never execute Playwright tests or scraping loops against live infrastructure.

---

## 5. Recommended Project Architecture: The Dual-Track Framework

To reconcile academic rigor with real-world legal and technical constraints, we recommend formalizing the **Dual-Track Project Architecture**:

```
                                  +---------------------------------------+
                                  |     React 19 Frontend (AIChat.jsx)    |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |     FastAPI Orchestrator Layer        |
                                  |       (agents/orchestrator.py)        |
                                  +-------------------+-------------------+
                                                      |
                         +----------------------------+----------------------------+
                         |                                                         |
                         v                                                         v
+-------------------------------------------------+       +-------------------------------------------------+
| TRACK A: Sandboxed Local RPA (Academic/Testing) |       | TRACK B: Official Advisory (Pilgrim Production) |
+-------------------------------------------------+       +-------------------------------------------------+
| • Target: yatra_mock_portal.html                |       | • Target: maavaishnodevi.org & online portal    |
| • Execution: Automated Playwright Chromium      |       | • Execution: Conversational Guidance + Deep Link|
| • Capabilities:                                 |       | • Capabilities:                                 |
|   - Slot availability extraction & filtering    |       |   - Route planning & distance calculations      |
|   - Dynamic wait synchronization testing        |       |   - Aarti & ritual schedules                    |
|   - Retry-and-escalate backoff benchmarking     |       |   - Official helicopter/battery car tariffs     |
|   - State validation & pause-and-handover       |       |   - RFID guidelines & document checklists       |
| • Safety: Isolated offline execution            |       | • Safety: Direct link to official login for     |
| • Status: FULLY OPERATIONAL (Weeks 4-7)         |       |   manual OTP, CAPTCHA, and real booking         |
+-------------------------------------------------+       +-------------------------------------------------+
```

### 5.1 Clear User Attribution & Truth in Advertising
To ensure users and academic evaluators are never misled into believing that mock sandbox responses represent real-time Shrine Board inventory:

1. **Transparent Agent Disclaimers:**
   Whenever the agent returns availability results via `check_yatra_availability_tool`, the response must include a standardized provenance badge:
   > **[Simulated Environment Notice]**  
   > *Availability results displayed above are generated from the local research sandbox (`DEFAULT_MOCK_SLOTS`) for demonstration and workflow verification. Live Shrine Board quotas require personal devotee authentication. To book confirmed real-world slots, please visit [online.maavaishnodevi.org](https://online.maavaishnodevi.org/).*

2. **UI Status Badges:**
   In the React frontend (`frontend/src/components/AIChat.jsx` and `YatraBooking.jsx`), slot cards generated via RPA must display a subtle visual indicator:
   - `Mock Portal Sandbox` (with an explanatory tooltip) rather than claiming to be a live feed.

3. **Intelligent Escalation to Official Links:**
   When a user asks: *"Book me a helicopter ticket for tomorrow on the official portal,"* the conversational agent should:
   - Recognize that live financial transactions cannot be automated.
   - Explain the official requirements (Aadhaar card, 60-day advance quota window, RFID card pickup).
   - Provide the exact official URL: [https://online.maavaishnodevi.org/#/guest/login](https://online.maavaishnodevi.org/#/guest/login).

---

## 6. Features That Must Remain Strictly Manual

The following operations must **never** be automated against the live Shrine Board portal and must remain strictly manual pilgrim actions:

```
+-----------------------------------------------------------------------------------------------+
| EXCLUSIVELY MANUAL FEATURES (NEVER TO BE AUTOMATED AGAINST LIVE SERVERS)                      |
+-----------------------------------------------------------------------------------------------+
| 1. Account Creation & Password Setup     | Requires personal identity and email validation.   |
| 2. Mobile OTP Verification               | Requires real-time SMS code delivered to handset. |
| 3. CAPTCHA Resolution                   | Security gate enforcing human interaction.         |
| 4. Citizen PII & Photo ID Upload         | Aadhaar, PAN, Passport numbers require consent.   |
| 5. Payment Gateway Execution             | Bank OTP, 3D Secure, UPI pin entry, card data.    |
| 6. Ticket Cancellation & Refund Requests | Irreversible financial side-effects.              |
| 7. Physical RFID Access Card Collection  | Physical presence at Katra/Jammu counters.         |
+-----------------------------------------------------------------------------------------------+
```

---

## 7. Comparative Assessment Summary Table

| Evaluation Criterion | Local Mock Portal (`yatra_mock_portal.html`) | Live Shrine Board Website (`maavaishnodevi.org`) | Project Verdict |
| :--- | :--- | :--- | :--- |
| **Availability Accessibility** | Publicly accessible without login via `#tabCalendar`. | Gated behind devotee login (Mobile OTP + Password). | Live automation blocked without credentials. |
| **Element Stability** | Stable, semantic IDs controlled in project codebase. | Subject to unannounced Angular rebuilds and class changes. | Live scraping highly fragile. |
| **Execution Speed** | Sub-second local file access (0.2s - 0.6s). | Subject to network latency, server queueing, and load. | Mock ideal for automated CI/CD tests. |
| **Bot Defenses** | None. Transparent for headless testing. | WAF, IP rate limits, CAPTCHA on submission. | Live headless browsers will fail or be blocked. |
| **Legal Compliance** | 100% compliant; internal academic testing sandbox. | Violates Terms of Service without written permission. | Live scraping prohibited. |
| **Cost & Risk** | Zero cost; zero risk of financial or data loss. | Financial charges; risk of account or IP blacklisting. | High risk on live portal. |

---

## 8. Final Recommendation & Path Forward

### 8.1 Definitive Recommendation:
**PROCEED ONLY WITH WRITTEN PERMISSION — DO NOT AUTOMATE LIVE SHRINE BOARD WEBSITE.**

1. **For Week 8 and Future Project Work:**
   - Continue enhancing the **Dual-Track Architecture**.
   - Keep Playwright RPA execution strictly bounded to the local mock portal sandbox (`yatra_mock_portal.html`).
   - Deepen the agent's advisory capabilities using publicly available Shrine Board information (Aarti schedules, trekking guides, weather tips, RFID policies).
2. **If Live Integration is Desired in Future:**
   - A formal proposal must be submitted to the **Shri Mata Vaishno Devi Shrine Board (SMVDSB)** requesting access to an official B2B/G2C API, sandbox endpoint, or approved RSS/JSON availability feed.
   - Automation must never proceed through "stealth scraping" or bypassing security controls.

### 8.2 Academic Justification for Project Defense
When presenting this project to mentors, examiners, or academic committees:
- **Highlight Engineering Excellence:** Emphasize that our multi-agent architecture (Week 7 LangChain tools, Week 6 bounded retry backoff, Week 5 dynamic wait synchronization) solves the real computer science challenges of browser automation and agent coordination.
- **Demonstrate Professional Ethics:** Defend the choice of a sandboxed mock portal as evidence of understanding real-world cybersecurity, legal compliance (IT Act 2000), and ethical AI deployment.
- **Showcase Practical Utility:** Point out that the conversational agent still provides immense real-world value by answering complex multi-modal tourism queries and navigating pilgrims directly to the correct official government procedures.
