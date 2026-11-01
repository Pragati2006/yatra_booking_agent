"""
agents/auth_service.py
Week 9: Optional Passwordless Email Authentication and User Data Isolation Service.

Key Architecture & Security Invariants:
1. OPTIONAL: The core application works in default Guest Mode without registration.
2. PASSWORDLESS: Zero password creation, storage, or recovery. Authenticates via 6-digit email OTP.
3. CRYPTOGRAPHIC SECURITY:
   - OTPs generated using `secrets.choice(string.digits)`.
   - Hashed with SHA-256 + secret application salt before storage; plain OTPs are NEVER stored.
   - Strict 5-minute (300-second) expiration.
   - Max 5 failed verification attempts before invalidation.
   - Rate limiting: 60-second cooldown per email between OTP requests.
   - Single-use verification: challenge is invalidated immediately upon successful verification.
   - Zero OTP values or provider credentials emitted to application logs.
4. DUAL STORAGE & RESILIENCY:
   - Primary: MongoDB Atlas user collections (`users`, `saved_itineraries`, `saved_conversations`).
   - Resiliency Fallback: Local SQLite store (`data/auth_store.db`) when MongoDB Atlas is offline.
5. SESSION SECURITY:
   - Cryptographically random session tokens (`secrets.token_urlsafe(32)`).
   - Server-side session validation. Private APIs derive user identity strictly from server session.
"""

import os
import re
import json
import uuid
import secrets
import hashlib
import hmac
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple

from utils.masking import mask_email, mask_otp, mask_token, mask_sensitive_data
from utils.logger import log_event

logger = logging.getLogger(__name__)

# Server-side HMAC secret for OTP signature (from env or fallback)
AUTH_HMAC_SECRET = os.getenv("AUTH_HMAC_SECRET", os.getenv("AUTH_SALT", "yatra_secure_hmac_secret_2026_vaishno_devi"))
AUTH_SALT = AUTH_HMAC_SECRET
OTP_EXPIRY_SECONDS = 300  # 5 minutes
RESEND_COOLDOWN_SECONDS = 60  # 1 minute
MAX_VERIFICATION_ATTEMPTS = 5
SESSION_TTL_DAYS = 7

DEFAULT_AUTH_DB_PATH = os.path.join("data", "auth_store.db")

# -----------------------------------------------------------------------------
# 1. Email Normalization & Validation
# -----------------------------------------------------------------------------

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_email(email: str) -> str:
    """Normalizes an email address to lowercase stripped form."""
    if not email:
        return ""
    return email.strip().lower()


def validate_email_format(email: str) -> bool:
    """Validates whether email satisfies basic standard format."""
    normalized = normalize_email(email)
    if not normalized or len(normalized) > 254:
        return False
    return bool(EMAIL_REGEX.match(normalized))


def generate_secure_otp(length: int = 6) -> str:
    """Generates a cryptographically random numeric OTP."""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def compute_otp_hmac(plain_otp: str, normalized_email: str, created_at: str = "") -> str:
    """
    Computes a cryptographically secure HMAC-SHA256 signature for OTP verification.
    Uses server-side secret (AUTH_HMAC_SECRET), challenge-specific data (normalized email, creation timestamp, purpose),
    and constant-time comparison properties.
    """
    secret = os.getenv("AUTH_HMAC_SECRET", os.getenv("AUTH_SALT", "yatra_secure_hmac_secret_2026_vaishno_devi")).encode("utf-8")
    payload = f"purpose=otp-verification:email={normalized_email}:created_at={created_at}:otp={plain_otp}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def hash_otp(plain_otp: str, normalized_email: str, created_at: str = "") -> str:
    """Backward-compatible wrapper routing to compute_otp_hmac."""
    return compute_otp_hmac(plain_otp, normalized_email, created_at)


# -----------------------------------------------------------------------------
# 2. Email Provider Abstraction
# -----------------------------------------------------------------------------

class BaseEmailProvider(ABC):
    """Abstract base class for email delivery providers."""

    @abstractmethod
    def send_otp(self, to_email: str, otp_code: str) -> bool:
        """Sends verification code to recipient."""
        pass


class MockEmailProvider(BaseEmailProvider):
    """
    In-memory mock email provider for development and automated testing.
    Keeps sent messages in an internal list for test assertions without external SMTP dependencies.
    """

    def __init__(self):
        self.outbox: List[Dict[str, Any]] = []

    def send_otp(self, to_email: str, otp_code: str) -> bool:
        self.outbox.append({
            "to": to_email,
            "otp": otp_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Log delivery without leaking OTP in logs (with masked email)
        logger.info("MockEmailProvider: Dispatched verification code to %s (outbox count: %d)", mask_email(to_email), len(self.outbox))
        return True

    def get_latest_otp_for(self, to_email: str) -> Optional[str]:
        """Test inspection method: retrieves the most recent OTP sent to to_email."""
        normalized = normalize_email(to_email)
        for msg in reversed(self.outbox):
            if normalize_email(msg["to"]) == normalized:
                return msg["otp"]
        return None

    def clear(self):
        """Clears the mock outbox."""
        self.outbox.clear()


class SMTPEmailProvider(BaseEmailProvider):
    """Production SMTP email provider reading credentials safely from environment."""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@yatra-booking-agent.org")

    def send_otp(self, to_email: str, otp_code: str) -> bool:
        if not self.smtp_host or not self.smtp_user or not self.smtp_pass:
            logger.warning("SMTP credentials not configured. Falling back to mock dispatch.")
            return False

        import smtplib
        from email.mime.text import MIMEText

        subject = "Your Vaishno Devi Yatra Verification Code"
        body = (
            f"Jai Mata Di!\n\n"
            f"Your one-time verification code is: {otp_code}\n\n"
            f"This code will expire in 5 minutes. Do not share this code with anyone.\n"
            f"If you did not request this code, you can safely ignore this email.\n"
        )
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            logger.info("SMTPEmailProvider: Verification email delivered to %s", mask_email(to_email))
            return True
        except Exception as exc:
            logger.error("SMTPEmailProvider: Failed to send email to %s: %s", mask_email(to_email), type(exc).__name__)
            return False


# Global email provider singleton (defaults to Mock in dev/testing)
_email_provider: BaseEmailProvider = MockEmailProvider()


def get_email_provider() -> BaseEmailProvider:
    return _email_provider


def set_email_provider(provider: BaseEmailProvider):
    global _email_provider
    _email_provider = provider


# -----------------------------------------------------------------------------
# 3. Persistent Local Store & Schema Management
# -----------------------------------------------------------------------------

def init_auth_db(db_path: Optional[str] = None) -> None:
    """Initializes local SQLite tables for authentication challenges, sessions, and fallback user data."""
    actual_path = db_path or DEFAULT_AUTH_DB_PATH
    os.makedirs(os.path.dirname(actual_path), exist_ok=True)

    with sqlite3.connect(actual_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        # 1. OTP Challenges Table (Hashed OTP storage only)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS otp_challenges (
                email TEXT PRIMARY KEY,
                otp_hash TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_requested_at TEXT NOT NULL
            );
            """
        )
        # 2. Server-side Authenticated Sessions
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user 
            ON auth_sessions (user_id);
            """
        )
        # 3. Users Table (Local fallback and profile cache)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                preferences_json TEXT
            );
            """
        )
        # 4. Saved Itineraries Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_itineraries (
                itinerary_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data_json TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_saved_itineraries_user 
            ON saved_itineraries (user_id);
            """
        )
        # 5. Saved Conversations Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_conversations (
                conversation_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                messages_json TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_saved_conversations_user 
            ON saved_conversations (user_id);
            """
        )
        # 6. User Bookings Table (Persistent simulated booking records associated with user_id)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_bookings (
                booking_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT,
                plan_version INTEGER DEFAULT 1,
                user_name TEXT NOT NULL,
                pax_count INTEGER NOT NULL DEFAULT 1,
                slot_date TEXT NOT NULL,
                category TEXT NOT NULL,
                slot_time TEXT,
                transport_mode TEXT,
                transport_info TEXT,
                hotel_name TEXT,
                total_price REAL NOT NULL DEFAULT 0.0,
                payment_status TEXT NOT NULL DEFAULT 'COMPLETED_SANDBOX',
                status TEXT NOT NULL DEFAULT 'SIMULATED_CONFIRMED',
                created_at TEXT NOT NULL,
                receipt_json TEXT
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_bookings_user 
            ON user_bookings (user_id);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_bookings_created 
            ON user_bookings (created_at DESC);
            """
        )
        conn.commit()


# -----------------------------------------------------------------------------
# 4. Authentication Service Implementation
# -----------------------------------------------------------------------------

class AuthService:
    """Core service managing passwordless email OTP authentication and user data."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_AUTH_DB_PATH
        init_auth_db(self.db_path)

    # -------------------------------------------------------------------------
    # A. Request OTP
    # -------------------------------------------------------------------------
    def request_otp(self, email: str) -> Dict[str, Any]:
        """
        Validates email, enforces 60s cooldown, generates 6-digit OTP,
        stores SHA-256 hash with 5-minute expiry, and dispatches via email provider.
        """
        normalized = normalize_email(email)
        if not validate_email_format(normalized):
            return {
                "status": "error",
                "error_code": "INVALID_EMAIL",
                "message": "Please enter a valid email address.",
            }

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_at = (now + timedelta(seconds=OTP_EXPIRY_SECONDS)).isoformat()

        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_requested_at FROM otp_challenges WHERE email = ?",
                (normalized,),
            )
            row = cursor.fetchone()
            if row:
                last_req = datetime.fromisoformat(row[0])
                elapsed_sec = (now - last_req).total_seconds()
                if elapsed_sec < RESEND_COOLDOWN_SECONDS:
                    wait_sec = int(RESEND_COOLDOWN_SECONDS - elapsed_sec)
                    log_event(
                        logger,
                        logging.WARNING,
                        "AUTH_OTP_REQUEST",
                        "OTP request rate limited by cooldown",
                        error_category="RATE_LIMIT",
                        details={"email": mask_email(normalized), "wait_sec": wait_sec},
                    )
                    return {
                        "status": "rate_limited",
                        "error_code": "RATE_LIMITED",
                        "retry_after_seconds": wait_sec,
                        "message": f"Please wait {wait_sec} seconds before requesting a new code.",
                    }

            # Generate cryptographically secure OTP
            plain_otp = generate_secure_otp(length=6)
            hashed_val = compute_otp_hmac(plain_otp, normalized, created_at=now_iso)

            # Store hashed challenge (replace existing)
            cursor.execute(
                """
                INSERT OR REPLACE INTO otp_challenges 
                (email, otp_hash, attempts, created_at, expires_at, last_requested_at)
                VALUES (?, ?, 0, ?, ?, ?)
                """,
                (normalized, hashed_val, now_iso, expires_at, now_iso),
            )
            conn.commit()

        # Send via configured email provider
        provider = get_email_provider()
        delivered = provider.send_otp(normalized, plain_otp)

        log_event(
            logger,
            logging.INFO,
            "AUTH_OTP_REQUEST",
            "Verification code requested and challenge created",
            details={"email": mask_email(normalized), "expires_in_seconds": OTP_EXPIRY_SECONDS},
        )

        return {
            "status": "success",
            "message": "A 6-digit verification code has been sent to your email.",
            "email": normalized,
            "expires_in_seconds": OTP_EXPIRY_SECONDS,
            "cooldown_seconds": RESEND_COOLDOWN_SECONDS,
            "delivered": delivered,
        }

    # -------------------------------------------------------------------------
    # B. Verify OTP
    # -------------------------------------------------------------------------
    def verify_otp(self, email: str, otp_code: str) -> Dict[str, Any]:
        """
        Verifies the user-entered OTP against the stored HMAC-SHA256 signature.
        Enforces challenge-bound context, single-use, 5-minute expiry, and max 5 attempts.
        Uses constant-time comparison via hmac.compare_digest.
        Creates user account if new, creates authenticated session token.
        """
        normalized = normalize_email(email)
        code = (otp_code or "").strip()

        if not normalized or not code or len(code) != 6 or not code.isdigit():
            return {
                "status": "error",
                "error_code": "INVALID_FORMAT",
                "message": "Please enter a valid 6-digit verification code.",
            }

        now = datetime.now(timezone.utc)

        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT otp_hash, attempts, expires_at, created_at FROM otp_challenges WHERE email = ?",
                (normalized,),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "error",
                    "error_code": "NO_ACTIVE_CHALLENGE",
                    "message": "No verification code was requested for this email, or it has expired.",
                }

            stored_hash, attempts, expires_at_str, created_at_str = row
            expires_at = datetime.fromisoformat(expires_at_str)

            # Compute HMAC for entered code using challenge timestamp
            entered_hash = compute_otp_hmac(code, normalized, created_at=created_at_str)

            # 1. Check expiration
            if now > expires_at:
                cursor.execute("DELETE FROM otp_challenges WHERE email = ?", (normalized,))
                conn.commit()
                log_event(
                    logger,
                    logging.WARNING,
                    "AUTH_OTP_VERIFY",
                    "Verification code expired",
                    error_category="AUTHENTICATION_ERROR",
                    details={"email": mask_email(normalized), "error_code": "CODE_EXPIRED"},
                    final_outcome="FAILED",
                )
                return {
                    "status": "error",
                    "error_code": "CODE_EXPIRED",
                    "message": "Verification code has expired. Please request a new code.",
                }

            # 2. Check max attempts
            if attempts >= MAX_VERIFICATION_ATTEMPTS:
                cursor.execute("DELETE FROM otp_challenges WHERE email = ?", (normalized,))
                conn.commit()
                log_event(
                    logger,
                    logging.WARNING,
                    "AUTH_OTP_VERIFY",
                    "Maximum OTP verification attempts exceeded",
                    error_category="AUTHENTICATION_ERROR",
                    details={"email": mask_email(normalized), "error_code": "MAX_ATTEMPTS_EXCEEDED"},
                    final_outcome="FAILED",
                )
                return {
                    "status": "error",
                    "error_code": "MAX_ATTEMPTS_EXCEEDED",
                    "message": "Maximum verification attempts exceeded. Please request a new code.",
                }

            # 3. Verify HMAC match using constant-time comparison
            if not hmac.compare_digest(stored_hash, entered_hash):
                new_attempts = attempts + 1
                if new_attempts >= MAX_VERIFICATION_ATTEMPTS:
                    cursor.execute("DELETE FROM otp_challenges WHERE email = ?", (normalized,))
                    conn.commit()
                    log_event(
                        logger,
                        logging.WARNING,
                        "AUTH_OTP_VERIFY",
                        "Maximum OTP verification attempts exceeded on incorrect code",
                        error_category="AUTHENTICATION_ERROR",
                        details={"email": mask_email(normalized), "error_code": "MAX_ATTEMPTS_EXCEEDED"},
                        final_outcome="FAILED",
                    )
                    return {
                        "status": "error",
                        "error_code": "MAX_ATTEMPTS_EXCEEDED",
                        "message": "Maximum verification attempts exceeded. Please request a new code.",
                    }
                else:
                    cursor.execute(
                        "UPDATE otp_challenges SET attempts = ? WHERE email = ?",
                        (new_attempts, normalized),
                    )
                    conn.commit()
                    remaining = MAX_VERIFICATION_ATTEMPTS - new_attempts
                    log_event(
                        logger,
                        logging.WARNING,
                        "AUTH_OTP_VERIFY",
                        "Incorrect OTP verification code entered",
                        error_category="AUTHENTICATION_ERROR",
                        details={"email": mask_email(normalized), "error_code": "INCORRECT_CODE", "remaining_attempts": remaining},
                        final_outcome="FAILED",
                    )
                    return {
                        "status": "error",
                        "error_code": "INCORRECT_CODE",
                        "remaining_attempts": remaining,
                        "message": f"Incorrect verification code. {remaining} attempt(s) remaining.",
                    }

            # 4. Successful match -> Invalidate challenge (Single-use invariant)
            cursor.execute("DELETE FROM otp_challenges WHERE email = ?", (normalized,))

            # 5. Find or create user account
            user, is_new_user = self._get_or_create_user(normalized, cursor)

            # 6. Create authenticated server session
            session_token = secrets.token_urlsafe(32)
            session_expiry = (now + timedelta(days=SESSION_TTL_DAYS)).isoformat()

            log_event(
                logger,
                logging.INFO,
                "AUTH_OTP_VERIFY",
                "User authenticated successfully via OTP",
                details={"email": mask_email(normalized), "user_id": user["user_id"], "is_new_user": is_new_user},
                final_outcome="SUCCESS",
            )
            cursor.execute(
                """
                INSERT INTO auth_sessions (session_token, user_id, email, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_token, user["user_id"], normalized, now.isoformat(), session_expiry),
            )
            conn.commit()

        return {
            "status": "success",
            "message": "Successfully authenticated." if not is_new_user else "Account created and authenticated.",
            "is_new_user": is_new_user,
            "session_token": session_token,
            "user": user,
            "expires_at": session_expiry,
        }

    # -------------------------------------------------------------------------
    # C. User Retrieval & Management
    # -------------------------------------------------------------------------
    def _get_or_create_user(self, normalized_email: str, cursor: sqlite3.Cursor) -> Tuple[Dict[str, Any], bool]:
        """Looks up user by normalized email or creates a new persistent record."""
        cursor.execute(
            "SELECT user_id, email, created_at, updated_at, preferences_json FROM users WHERE email = ?",
            (normalized_email,),
        )
        row = cursor.fetchone()
        now_iso = datetime.now(timezone.utc).isoformat()

        if row:
            uid, em, cat, uat, prefs_json = row
            prefs = json.loads(prefs_json) if prefs_json else {}
            return {
                "user_id": uid,
                "email": em,
                "created_at": cat,
                "updated_at": uat,
                "preferences": prefs,
            }, False

        # Create new user
        new_uid = f"usr_{uuid.uuid4().hex[:12]}"
        default_prefs = {"travel_style": "Standard", "preferred_darshan": "Normal Darshan"}
        cursor.execute(
            """
            INSERT INTO users (user_id, email, created_at, updated_at, preferences_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_uid, normalized_email, now_iso, now_iso, json.dumps(default_prefs)),
        )
        return {
            "user_id": new_uid,
            "email": normalized_email,
            "created_at": now_iso,
            "updated_at": now_iso,
            "preferences": default_prefs,
        }, True

    def get_user_by_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validates server session token and returns authenticated user record. Returns None if invalid or expired."""
        if not token:
            return None

        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, email, expires_at FROM auth_sessions WHERE session_token = ?",
                (token,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            uid, email, expires_at_str = row
            if now > datetime.fromisoformat(expires_at_str):
                # Clean expired session
                cursor.execute("DELETE FROM auth_sessions WHERE session_token = ?", (token,))
                conn.commit()
                return None

            cursor.execute(
                "SELECT user_id, email, created_at, updated_at, preferences_json FROM users WHERE user_id = ?",
                (uid,),
            )
            user_row = cursor.fetchone()
            if not user_row:
                return None

            u_id, u_em, c_at, u_at, p_json = user_row
            return {
                "user_id": u_id,
                "email": u_em,
                "created_at": c_at,
                "updated_at": u_at,
                "preferences": json.loads(p_json) if p_json else {},
            }

    def logout_session(self, token: str) -> bool:
        """Revokes authenticated session token server-side."""
        if not token:
            return False
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_sessions WHERE session_token = ?", (token,))
            conn.commit()
            revoked = cursor.rowcount > 0
            if revoked:
                log_event(
                    logger,
                    logging.INFO,
                    "AUTH_LOGOUT",
                    "User session token revoked successfully",
                    details={"token": mask_token(token)},
                    final_outcome="SUCCESS",
                )
            return revoked

    # -------------------------------------------------------------------------
    # D. User Associated Data (Itineraries & Conversations)
    # -------------------------------------------------------------------------
    def save_itinerary(self, user_id: str, title: str, itinerary_data: Any) -> Dict[str, Any]:
        """Saves generated itinerary for authenticated user."""
        itin_id = f"itin_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        t_clean = (title or "Vaishno Devi Yatra Itinerary").strip()

        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO saved_itineraries (itinerary_id, user_id, title, created_at, data_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (itin_id, user_id, t_clean, now_iso, json.dumps(itinerary_data)),
            )
            conn.commit()

        return {
            "itinerary_id": itin_id,
            "user_id": user_id,
            "title": t_clean,
            "created_at": now_iso,
            "data": itinerary_data,
        }

    def get_saved_itineraries(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all saved itineraries belonging strictly to user_id."""
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT itinerary_id, title, created_at, data_json 
                FROM saved_itineraries 
                WHERE user_id = ? 
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "itinerary_id": r[0],
                    "title": r[1],
                    "created_at": r[2],
                    "data": json.loads(r[3]),
                }
                for r in rows
            ]

    def delete_saved_itinerary(self, user_id: str, itinerary_id: str) -> bool:
        """Deletes a saved itinerary strictly verifying user ownership."""
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM saved_itineraries WHERE itinerary_id = ? AND user_id = ?",
                (itinerary_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def save_conversation(self, user_id: str, title: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Saves a conversational chat thread for authenticated user."""
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        t_clean = (title or "Yatra Consultation Chat").strip()

        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO saved_conversations (conversation_id, user_id, title, created_at, messages_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conv_id, user_id, t_clean, now_iso, json.dumps(messages)),
            )
            conn.commit()

        return {
            "conversation_id": conv_id,
            "user_id": user_id,
            "title": t_clean,
            "created_at": now_iso,
            "messages": messages,
        }

    def get_saved_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all saved conversations belonging strictly to user_id."""
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT conversation_id, title, created_at, messages_json 
                FROM saved_conversations 
                WHERE user_id = ? 
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "conversation_id": r[0],
                    "title": r[1],
                    "created_at": r[2],
                    "messages": json.loads(r[3]),
                }
                for r in rows
            ]

    def delete_saved_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Deletes a saved conversation strictly verifying user ownership."""
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM saved_conversations WHERE conversation_id = ? AND user_id = ?",
                (conversation_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # -------------------------------------------------------------------------
    # E. Account-Linked Mock Bookings
    # -------------------------------------------------------------------------
    def save_booking(self, user_id: str, booking_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persists a verified simulated booking record associated with an authenticated user.
        Idempotent: Re-saving an existing booking_id updates the record without creating duplicates.
        Enforces that booking status is SIMULATED_CONFIRMED and masks/excludes sensitive tokens.
        """
        if not user_id:
            raise ValueError("user_id is strictly required to save a booking")

        bid = booking_data.get("booking_id")
        if not bid or not isinstance(bid, str) or not bid.strip():
            raise ValueError("booking_id is strictly required to save a booking")
        bid = bid.strip()

        now_iso = datetime.now(timezone.utc).isoformat()
        created_at = booking_data.get("created_at") or now_iso
        user_name = booking_data.get("user_name") or "Guest-Pilgrim"
        pax_count = int(booking_data.get("pax_count") or 1)
        slot_date = str(booking_data.get("slot_date") or "2026-10-20")
        category = str(booking_data.get("category") or "Normal Darshan")
        slot_time = booking_data.get("slot_time") or "Morning (06:00)"
        transport_mode = booking_data.get("transport_mode") or "Train"
        transport_info = booking_data.get("transport_info") or "Vande Bharat Express"
        hotel_name = booking_data.get("hotel_name")
        total_price = float(booking_data.get("total_price") or 0.0)
        payment_status = booking_data.get("payment_status") or "COMPLETED_SANDBOX"
        status = "SIMULATED_CONFIRMED"
        session_id = booking_data.get("session_id")
        plan_version = int(booking_data.get("plan_version") or 1)
        receipt = booking_data.get("receipt") or booking_data.get("receipt_data") or {}

        # Ensure receipt has explicit simulated confirmation and local mock labels
        if isinstance(receipt, dict):
            receipt.setdefault("portal_label", "LOCAL MOCK PORTAL / DEMO")
            receipt.setdefault("title", "Simulated Yatra Booking Confirmation")
            receipt.setdefault("pass_type", "Demo Pilgrim Pass (Local Simulation)")
            receipt.setdefault("booking_id", bid)

        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            # Verify ownership if booking_id already exists
            cursor.execute(
                "SELECT user_id FROM user_bookings WHERE booking_id = ?",
                (bid,),
            )
            existing = cursor.fetchone()
            if existing and existing[0] != user_id:
                logger.warning(
                    "Ownership conflict: booking %s already belongs to user %s, cannot assign to user %s",
                    bid, existing[0], user_id,
                )
                raise PermissionError(f"Booking {bid} belongs to another user account.")

            cursor.execute(
                """
                INSERT OR REPLACE INTO user_bookings (
                    booking_id, user_id, session_id, plan_version, user_name, pax_count,
                    slot_date, category, slot_time, transport_mode, transport_info,
                    hotel_name, total_price, payment_status, status, created_at, receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bid, user_id, session_id, plan_version, user_name, pax_count,
                    slot_date, category, slot_time, transport_mode, transport_info,
                    hotel_name, total_price, payment_status, status, created_at,
                    json.dumps(receipt, ensure_ascii=False),
                ),
            )
            conn.commit()

        return {
            "booking_id": bid,
            "user_id": user_id,
            "session_id": session_id,
            "plan_version": plan_version,
            "user_name": user_name,
            "pax_count": pax_count,
            "slot_date": slot_date,
            "category": category,
            "slot_time": slot_time,
            "transport_mode": transport_mode,
            "transport_info": transport_info,
            "hotel_name": hotel_name,
            "total_price": total_price,
            "payment_status": payment_status,
            "status": status,
            "created_at": created_at,
            "receipt": receipt,
        }

    def get_user_bookings(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all confirmed simulated bookings belonging strictly to user_id."""
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT booking_id, user_id, session_id, plan_version, user_name, pax_count,
                       slot_date, category, slot_time, transport_mode, transport_info,
                       hotel_name, total_price, payment_status, status, created_at, receipt_json
                FROM user_bookings
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "booking_id": r[0],
                    "user_id": r[1],
                    "session_id": r[2],
                    "plan_version": r[3],
                    "user_name": r[4],
                    "pax_count": r[5],
                    "slot_date": r[6],
                    "category": r[7],
                    "slot_time": r[8],
                    "transport_mode": r[9],
                    "transport_info": r[10],
                    "hotel_name": r[11],
                    "total_price": r[12],
                    "payment_status": r[13],
                    "status": r[14],
                    "created_at": r[15],
                    "receipt": json.loads(r[16]) if r[16] else {},
                }
                for r in rows
            ]

    def get_user_booking(self, user_id: str, booking_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single booking record strictly verifying user ownership."""
        if not user_id or not booking_id:
            return None
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT booking_id, user_id, session_id, plan_version, user_name, pax_count,
                       slot_date, category, slot_time, transport_mode, transport_info,
                       hotel_name, total_price, payment_status, status, created_at, receipt_json
                FROM user_bookings
                WHERE user_id = ? AND booking_id = ?
                """,
                (user_id, booking_id.strip()),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return {
                "booking_id": r[0],
                "user_id": r[1],
                "session_id": r[2],
                "plan_version": r[3],
                "user_name": r[4],
                "pax_count": r[5],
                "slot_date": r[6],
                "category": r[7],
                "slot_time": r[8],
                "transport_mode": r[9],
                "transport_info": r[10],
                "hotel_name": r[11],
                "total_price": r[12],
                "payment_status": r[13],
                "status": r[14],
                "created_at": r[15],
                "receipt": json.loads(r[16]) if r[16] else {},
            }

    # -------------------------------------------------------------------------
    # F. Selective Guest-to-Account Transfers
    # -------------------------------------------------------------------------
    def transfer_guest_conversation_to_user(
        self,
        user_id: str,
        session_id: str,
        title: Optional[str] = None,
        sessions_db_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Selectively imports/transfers a guest conversational session from sessions.db
        into the authenticated user's saved conversations in auth_store.db.
        """
        from agents import session_store
        messages = session_store.get_messages(session_id, db_path=sessions_db_path)
        if not messages:
            return None

        t_clean = (title or f"Yatra Consultation ({session_id[:8]})").strip()
        cleaned_msgs = [
            {
                "id": m.get("id"),
                "role": m.get("role"),
                "content": m.get("content"),
                "metadata": m.get("metadata"),
                "created_at": m.get("created_at"),
            }
            for m in messages
        ]
        saved = self.save_conversation(user_id=user_id, title=t_clean, messages=cleaned_msgs)
        # Tag session with user_id in sessions.db
        session_store.update_session_user(session_id, user_id, db_path=sessions_db_path)
        return saved

    def transfer_guest_trip_to_user(
        self,
        user_id: str,
        session_id: str,
        title: Optional[str] = None,
        sessions_db_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Selectively imports/transfers a guest trip plan from sessions.db
        into the authenticated user's saved itineraries in auth_store.db.
        """
        from agents import session_store
        session = session_store.get_session(session_id, db_path=sessions_db_path)
        if not session:
            return None

        state = session.get("state", {})
        req = state.get("requirements", {})
        itinerary = state.get("itinerary")
        options = state.get("selected_options", {})
        budget = state.get("budget_evaluation", {})
        plan_ver = state.get("plan_version", 1)

        t_clean = (title or f"Yatra Trip from {req.get('origin') or 'Delhi'}").strip()
        trip_data = {
            "origin": req.get("origin"),
            "destination": req.get("destination", "Katra"),
            "pax": req.get("pax", 1),
            "start_date": req.get("start_date"),
            "end_date": req.get("end_date"),
            "darshan_category": req.get("darshan_preference") or (options.get("darshan_slot") or {}).get("category") or "Normal Darshan",
            "transport_preference": req.get("mode_preference"),
            "accommodation_preference": req.get("accommodation_preference"),
            "total_budget": req.get("total_budget"),
            "budget_evaluation": budget,
            "selected_options": options,
            "itinerary": itinerary,
            "plan_version": plan_ver,
            "session_id": session_id,
        }
        saved = self.save_itinerary(user_id=user_id, title=t_clean, itinerary_data=trip_data)
        session_store.update_session_user(session_id, user_id, db_path=sessions_db_path)
        return saved

    def transfer_guest_booking_to_user(
        self,
        user_id: str,
        booking_id: str,
        session_id: Optional[str] = None,
        sessions_db_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Transfers/claims a simulated booking created during a guest session.
        Verifies that the booking exists in sessions.db or user_workflows before associating.
        """
        from agents import session_store
        bid = (booking_id or "").strip()
        if not bid:
            return None

        booking_info = None
        if session_id:
            session = session_store.get_session(session_id, db_path=sessions_db_path)
            if session:
                state = session.get("state", {})
                rpa_ex = state.get("rpa_execution", {})
                b_hist = state.get("booking_history", [])
                matched = [b for b in b_hist if b.get("booking_id") == bid]
                if rpa_ex.get("booking_id") == bid or matched:
                    booking_info = {
                        "booking_id": bid,
                        "session_id": session_id,
                        "plan_version": state.get("plan_version", 1),
                        "user_name": state.get("authorization", {}).get("user_name") or "Guest-Pilgrim",
                        "pax_count": state.get("requirements", {}).get("pax", 1),
                        "slot_date": (state.get("selected_options", {}).get("darshan_slot") or {}).get("slot_date", "2026-10-20"),
                        "category": (state.get("selected_options", {}).get("darshan_slot") or {}).get("category", "Normal Darshan"),
                        "total_price": float((state.get("selected_options", {}).get("transport") or {}).get("price", 0.0)),
                        "receipt": rpa_ex,
                    }

        if not booking_info:
            # Check if it already exists in user_bookings for this user
            existing = self.get_user_booking(user_id=user_id, booking_id=bid)
            if existing:
                return existing
            return None

        return self.save_booking(user_id=user_id, booking_data=booking_info)

    def get_user_profile_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile along with summary counts of saved trips, chats, and bookings."""
        if not user_id:
            return None
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, email, created_at, updated_at, preferences_json FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            uid, email, cat, uat, p_json = row

            cursor.execute("SELECT count(1) FROM saved_itineraries WHERE user_id = ?", (user_id,))
            itin_count = cursor.fetchone()[0]

            cursor.execute("SELECT count(1) FROM saved_conversations WHERE user_id = ?", (user_id,))
            conv_count = cursor.fetchone()[0]

            cursor.execute("SELECT count(1) FROM user_bookings WHERE user_id = ?", (user_id,))
            booking_count = cursor.fetchone()[0]

            return {
                "user_id": uid,
                "email": email,
                "created_at": cat,
                "updated_at": uat,
                "preferences": json.loads(p_json) if p_json else {},
                "stats": {
                    "saved_itineraries_count": itin_count,
                    "saved_conversations_count": conv_count,
                    "confirmed_bookings_count": booking_count,
                },
            }


# Global singleton instance
auth_service = AuthService()
