# Team Collaboration & Onboarding Setup Guide
## Tourism GPT with RPA — Yatra Booking Agent (Vaishno Devi)

This guide provides step-by-step instructions for teammates cloning and running the repository on their own local machines (Windows / macOS / Linux).

---

## 1. System Prerequisites

Before starting, ensure your system has:

- **Git:** [Download Git for Windows](https://git-scm.com/download/win)
- **Python:** Python 3.12 (64-bit) — [Download Python 3.12](https://www.python.org/downloads/)
  *(Check "Add Python to PATH" during installation)*
- **Node.js:** Node.js v18+ or v20+ with `npm` — [Download Node.js](https://nodejs.org/)
- **Terminal:** Windows PowerShell (recommended for Windows users)

---

## 2. Clone the Repository

Open Windows PowerShell and clone the active feature branch:

```powershell
git clone -b feature/ui-redesign https://github.com/Pragati2006/yatra_booking_agent.git
cd yatra_booking_agent
```

Verify your current branch:
```powershell
git branch
# Output should show: * feature/ui-redesign
```

---

## 3. Environment Variables Configuration (`.env`)

Each teammate **must** configure their own local `.env` file. Never commit real secrets to GitHub.

1. Create your `.env` file from the provided template:
   ```powershell
   copy .env.example .env
   ```

2. Open `.env` in your text editor (e.g. VS Code or Notepad) and configure your credentials:
   ```dotenv
   # 1. Groq Cloud API Key (Required for AI Chat & slot classification)
   # Get a free key at: https://console.groq.com/keys
   GROQ_API_KEY=your_actual_groq_api_key_here

   # 2. MongoDB Atlas URI (Optional)
   # If left default or unreachable, the system automatically uses local curated CSV datasets.
   MONGO_URI=mongodb+srv://your_username:your_password@cluster.mongodb.net/?retryWrites=true&w=majority
   MONGODB_URI=mongodb+srv://your_username:your_password@cluster.mongodb.net/?retryWrites=true&w=majority
   MONGO_DB_NAME=yatra_booking_agent

   # 3. SMTP Email Configuration (Optional)
   # If unconfigured, the system automatically falls back to MockEmailProvider.
   # You can view generated OTPs directly in the backend terminal or via the dev endpoint.
   SMTP_HOST=your_smtp_host_here
   SMTP_PORT=587
   SMTP_USER=your_email_here
   SMTP_PASSWORD=your_smtp_password_here
   SMTP_FROM_EMAIL=noreply@yatra-booking-agent.org
   ```

---

## 4. Backend Environment & Dependency Setup

In your PowerShell terminal (at the project root `yatra_booking_agent`):

### Step 4.1: Create and Activate Python Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Allow script execution if restricted on Windows
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```
*(Your prompt will change to show `(venv)`)*

### Step 4.2: Install Python Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4.3: Install Playwright Chromium Browser
The local RPA mock booking agent and end-to-end tests use Playwright's headless browser engine:
```powershell
playwright install chromium
```

---

## 5. Frontend Setup

In a second terminal window (or before launching servers):

```powershell
cd frontend
npm install
cd ..
```

---

## 6. Running the Application Locally

You will run the backend and frontend in two separate terminals.

### Terminal 1: Start the FastAPI Backend
```powershell
# Make sure virtual environment is active:
.\venv\Scripts\Activate.ps1

# Start Uvicorn daemon on port 8000:
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Backend Health Check:** `http://localhost:8000/api/health`
- **FastAPI Interactive Docs (Swagger):** `http://localhost:8000/docs`

### Terminal 2: Start the React Frontend
```powershell
cd frontend
npm run dev
```
- **Web Application Portal:** `http://localhost:5173/`

Vite is preconfigured to proxy all `/api/*` network requests automatically to `http://127.0.0.1:8000`.

---

## 7. How to Test the Application

### A. Quick Health & Endpoint Verification
```powershell
python tests/test_fastapi_endpoints.py
```

### B. Core Security & Authentication Tests
```powershell
python -m unittest tests.test_server_authorization_security
python -m unittest tests.test_passwordless_auth_week9
```

### C. Frontend Production Build Check
```powershell
cd frontend
npm run build
cd ..
```

---

## 8. Development & Live Demo Tips

### Viewing Authentication OTPs Locally
When you sign in as a user with an email address:
- If SMTP credentials are not configured in `.env`, the system uses `MockEmailProvider`.
- Check the Terminal 1 console log for the printed OTP message.
- Or open: `http://localhost:8000/api/auth/test/latest-otp?email=your_email@example.com`

### Human-in-the-Loop Checkpoints (OTP & CAPTCHA)
- During the Playwright RPA booking execution, the system pauses at two checkpoints:
  - **OTP Checkpoint:** Enter `123456` (or click *"Continue Booking ➔"*).
  - **CAPTCHA Checkpoint:** Enter `M7K9P` (or click *"Continue Booking ➔"*).
- The payment stage is completely simulated (₹0 live charge).

---

## 9. Troubleshooting Common Issues

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`Activate.ps1 cannot be loaded because running scripts is disabled`** | Windows PowerShell execution policy restriction | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the current terminal. |
| **`Port 8000 or 5173 already in use`** | A dangling process is holding the port | Run `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess \| Stop-Process -Force` |
| **`playwright._impl._errors.Error: Executable doesn't exist`** | Playwright Chromium binary is not installed | Run `playwright install chromium` in your activated virtual environment. |
| **`MongoDB TLS error / SSL alert`** | Strict corporate firewall or missing Atlas IP whitelist | The application automatically switches to local curated CSVs. No action required. |
| **`Groq API authentication error`** | Missing or invalid `GROQ_API_KEY` in `.env` | Ensure your `.env` contains a valid key from [Groq Console](https://console.groq.com/keys). |

---

## 10. Git Contribution Guidelines

1. Never commit `.env`, `.env.local`, or any file containing private API keys or passwords.
2. Never commit `data/*.db` (local SQLite databases) or `frontend/dist/`.
3. Check `git status` before committing to ensure temporary files are ignored.
4. Keep all RPA automation strictly within the local mock booking sandbox. Do not target external government portals.

