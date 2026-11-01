# Yatra Booking Agent — Frontend Web Application

A modern, responsive React 19 Single-Page Application (SPA) built with Vite for the **Maa Vaishno Devi Yatra Booking Agent (Tourism AI with RPA)**. The frontend provides pilgrims with an intuitive interface to plan their pilgrimage through either a structured multi-step intake wizard or an interactive conversational AI companion, customize travel and accommodation details, authorize plans through an ethical Human-in-the-Loop gate, trigger automated mock RPA checkout, and generate clean, print-optimized Yatra Pilgrim Passes.

---

## 1. Features & Capabilities

- **Dual Planning Modes:**
  - **Structured Form Wizard:** A 7-step guided planning workflow capturing departure city, dates, pilgrim count, transit preference, darshan slot timings, accommodation tier, budget limits, and regional excursions.
  - **Conversational AI Companion (`AIChat`):** Natural language multi-turn trip consultation with context-aware slot extraction, devotional responses, live package recommendation cards, and one-click transitions to booking review.
  - **Seamless Bidirectional Mode Switcher:** Switch between Form and Chat views at any point with zero loss of session ID, destination selections, or itinerary state.
- **Jammu & Kashmir Sightseeing Browser:**
  - Interactive directory of 29 curated regional destinations across Katra local shrines, trek-route stops, regional hill stations (Patnitop, Sanasar), holy springs (Baba Dhansar), and ancient cave shrines (Shiv Khori).
  - Real-time search, category filters, duration advisories, and quick-remove tags.
- **Interactive Itinerary Timeline:**
  - Day-by-day visualization strictly enforcing Day 2 holy trek exclusivity and safeguarding post-trek recovery periods.
  - Transparent feasibility advisories for distant excursions.
- **Secondary Booking Customization:**
  - Dynamic re-selection of transport modes and operators.
  - Real-time hotel room allocation and night adjustments.
  - Real-time budget recalculation segregating verified direct expenses from discretionary estimates.
  - Automatic plan version increments (`Revision #N`) with server-side stale authorization invalidation.
- **Human-in-the-Loop Authorization Gate:**
  - Mandatory user review step requiring explicit user consent recorded server-side before booking execution.
- **Simulated RPA Demonstration:**
  - Trigger Playwright-based headless browser automation filling out simulated checkout forms in an isolated mock portal sandbox.
- **Print-Optimized Yatra Pilgrim Pass:**
  - Official booking confirmation displaying unique reference codes (e.g., `VD26753AC0`), divine blessings, and Katra RFID reporting instructions.
  - Dedicated `@media print` CSS rules that suppress application headers, navigation bars, buttons, and footers for clean paper or PDF printing.

---

## 2. Prerequisites

Ensure the following runtimes and tools are installed:

- **Node.js:** `v18.0.0` or higher (Node 20+ recommended)
- **npm:** `v9.0.0` or higher
- **Backend Service:** The FastAPI backend daemon must be active on `http://127.0.0.1:8000` (requires Python 3.10+ / 3.12).
- **Web Browser:** Google Chrome, Microsoft Edge, Mozilla Firefox, or Apple Safari.

---

## 3. Installation & Setup

1. Open a terminal and navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

   Key dependencies installed:
   - `react` (`^19.2.8`) & `react-dom` (`^19.2.8`): UI component rendering.
   - `react-router-dom` (`^7.18.4`): Client-side routing.
   - `axios` (`^1.20.0`): HTTP client for backend REST communication.
   - `lucide-react` (`^1.55.0`): Icon library.
   - `vite` (`^8.3.0`): Bundler and local development server.
   - `oxlint` (`^1.81.0`): High-performance JavaScript/JSX linter.

---

## 4. Starting the Frontend

To launch the local development server:

```bash
npm run dev
```

To explicitly bind to `127.0.0.1`:
```bash
npm run dev -- --host 127.0.0.1
```

Once started, the application is accessible at:
- Local URL: `http://127.0.0.1:5173` (or `http://localhost:5173`)

---

## 5. Backend URL & Environment Configuration

### Default Configuration
By default, the frontend is configured to communicate with the FastAPI backend at `http://127.0.0.1:8000`:
- **Vite Proxy (`vite.config.js`):** Proxies any requests prefixed with `/api` directly to `http://127.0.0.1:8000` with `changeOrigin: true`.
- **Axios Base URL (`src/services/api.js`):**
  ```javascript
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
  ```

### Optional Environment Variables
If your backend is hosted on a different port, hostname, or container address, configure:
- **`VITE_API_URL`**: Defines the base URL for backend API requests (e.g., in a local `.env` file within the `frontend/` folder).

> **Note:** Never commit production credentials, secrets, or confidential URLs to repository configuration files.

---

## 6. Linting & Production Build Commands

### Linting
To check code quality and catch syntax or state synchronization issues using Oxlint:
```bash
npm run lint
```
*Current baseline: 0 errors, 0 warnings.*

### Production Build
To compile and bundle the React application into optimized static assets:
```bash
npm run build
```
Build output is generated in the `frontend/dist/` directory.

### Preview Production Build
To preview the compiled production bundle locally:
```bash
npm run preview
```

---

## 7. Application Architecture & Component Structure

```
frontend/
├── index.html                   # HTML entry point with responsive viewport settings
├── package.json                 # Project scripts and dependency declarations
├── vite.config.js               # Vite bundler settings and /api proxy configuration
└── src/
    ├── main.jsx                 # Application bootstrapping and React 19 root
    ├── App.jsx                  # Main router and top-level navigation layout
    ├── App.css                  # Global layout styles and navigation styling
    ├── index.css                # Base typography, theme tokens, and @media print rules
    ├── services/
    │   └── api.js               # Centralized Axios API service connecting to FastAPI
    ├── pages/
    │   ├── Home.jsx             # Hero landing page, feature highlights, and mode choice
    │   └── YatraBooking.jsx     # Core multi-step booking coordinator and wizard
    └── components/
        ├── Navbar.jsx           # Top navigation bar with branding and links
        ├── AIChat.jsx           # Conversational AI companion interface
        ├── TravelSearch.jsx     # Step 1: Guided multi-field intake form
        ├── RecommendedYatra.jsx # Step 2: Package recommendation and review
        ├── TransportCard.jsx    # Selectable flight, train, and bus transit cards
        ├── HotelCard.jsx        # Certified accommodation tier and room selector
        ├── SightseeingBrowser.jsx # Step 2.5: Interactive 29-place J&K destination catalog
        ├── SightseeingCard.jsx  # Individual attraction cards with duration & tags
        ├── ItineraryTimeline.jsx# Step 2.7: Dynamic day-by-day route timeline
        ├── Authorization.jsx    # Step 3: Cost breakdown & Human-in-the-Loop gate
        └── BookingConfirmation.jsx # Step 4: Official pass and clean print preview
```

---

## 8. End-to-End Booking Workflow

1. **Intake (Form or Chat):** The user enters departure origin, dates, number of pilgrims, transport preference, and darshan slot.
2. **Package Recommendation:** The backend matches travel schedules and shrine availability, returning an initial recommended plan (`Revision #1`).
3. **Customization:**
   - Transport can be re-selected among available train, flight, or bus options.
   - Hotel can be changed across Budget, Standard, or Deluxe tiers with automatic room count calculation.
   - Regional sightseeing spots can be added from the catalog of 29 destinations.
   - Every change increments the plan version (`plan_version`) and recalculates direct verified vs estimated costs.
4. **Human-in-the-Loop Authorization:**
   - The user reviews the complete plan and checks the authorization consent checkbox.
   - The frontend calls `POST /api/yatra/authorize` to record approval on the server session specifically for the current revision.
   - If subsequent customizations are made, the prior approval is immediately invalidated by the server.
5. **Execution (RPA Simulation or Direct Confirmation):**
   - The user can trigger `POST /api/yatra/rpa` to execute headless Playwright browser automation against the local mock portal sandbox.
   - Alternatively, direct confirmation via `POST /api/yatra/confirm` records the booking reference.
6. **Yatra Pilgrim Pass Issuance:**
   - Displays the confirmed booking reference (e.g., `VD26753AC0`), passenger details, and divine blessings.
   - Clicking **Print Pilgrim Pass** triggers the browser print dialog with all UI controls hidden.

---

## 9. Troubleshooting & Grounded Implementation Notes

### Backend Connection Errors (`ERR_CONNECTION_REFUSED` / Network Error)
- **Cause:** The FastAPI backend is not running or running on an unexpected port.
- **Remedy:** Ensure the FastAPI backend is running via:
  ```powershell
  & "..\venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
  ```
- Verify health by opening `http://127.0.0.1:8000/api/health` in your browser. It should return `{"status":"healthy","service":"Yatra Booking Agent"}`.

### Plan Version Mismatch / Stale Authorization Error
- **Symptom:** API returns `{"status": "authorization_required", "message": "Plan has been updated to Revision #X..."}`.
- **Cause:** Changes were made to transport, hotel, or sightseeing after granting authorization.
- **Remedy:** This is an intentional security safeguard. Proceed to the Authorization step and re-authorize the updated plan revision.

### Playwright RPA Execution Fails
- **Cause:** Playwright Chromium binaries are not installed in the Python environment.
- **Remedy:** Install Playwright browser binaries in your Python virtual environment:
  ```powershell
  & "..\venv\Scripts\python.exe" -m playwright install chromium
  ```

### Vite HMR Socket Interruption on Windows
- **Symptom:** Hot module replacement disconnects or browser tests fail with page load timeouts.
- **Remedy:** Terminate stalled node processes and restart the dev server with an explicit host flag:
  ```bash
  npm run dev -- --host 127.0.0.1
  ```

### Print Formatting Considerations
- If headers, footers, or background colors look washed out in print preview, check your browser's print dialog settings:
  - Check **Background graphics** to preserve devotional card accents.
  - Set margins to **Default** or **Minimum**.
