"""
agents/session_store.py
Persistent trip-planning session state store backed by local SQLite.

Provides ACID transactional persistence for multi-turn conversational yatra planning.
Survives application and process restarts on a single host.

Architecture Note:
Local SQLite persistence provides reliable single-node persistence across server restarts.
It is NOT, by itself, a distributed multi-server session solution (such as Redis or a
managed database cluster). For single-node deployment (FastAPI / Streamlit), it ensures
session state is never lost when the backend server restarts.
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = "data"
DEFAULT_DB_NAME = "sessions.db"
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, DEFAULT_DB_NAME)

_session_locks: Dict[str, threading.Lock] = {}
_session_locks_guard = threading.Lock()


def get_session_lock(session_id: str) -> threading.Lock:
    """Returns a process-wide mutual exclusion lock for a session_id to guarantee idempotency and serial execution under concurrent requests."""
    with _session_locks_guard:
        if session_id not in _session_locks:
            _session_locks[session_id] = threading.Lock()
        return _session_locks[session_id]

# Default session state template
DEFAULT_STATE_TEMPLATE: Dict[str, Any] = {
    "requirements": {
        "origin": None,
        "destination": "Katra",
        "start_date": None,
        "end_date": None,
        "duration_days": None,
        "pax": 1,
        "total_budget": None,
        "currency": "INR",
        "mode_preference": None,
        "darshan_preference": None,
        "accommodation_preference": None,
        "sightseeing_requested": None,
        "group_type": None,
        "travel_style": None,
        "trip_focus": None,
    },
    "missing_fields": [],
    "selected_options": {
        "transport": None,
        "darshan_slot": None,
        "accommodation": None,
        "sightseeing": [],
    },
    "budget_evaluation": None,
    "itinerary": None,
    "plan_version": 1,
    "authorized_plan_version": None,
    "authorization": {
        "pending": False,
        "granted": False,
        "authorized_at": None,
        "authorized_for_version": None,
        "revoked_reason": None,
        "user_name": None,
    },
    "rpa_execution": {
        "status": "NOT_TRIGGERED",
        "booking_id": None,
        "screenshot_path": None,
        "logs": [],
    },
    "booking_history": [],
    "last_tourism_place": None,
    "last_itinerary_context": None,
    "pending_options": None,
}


def _get_utc_now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the SQLite session table if it does not already exist."""
    actual_db_path = db_path or DEFAULT_DB_PATH
    db_dir = os.path.dirname(actual_db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                state_json TEXT NOT NULL,
                user_id TEXT
            );
            """
        )
        # Safe migration: ensure user_id column exists if table was created previously
        cursor.execute("PRAGMA table_info(sessions)")
        col_names = [col[1] for col in cursor.fetchall()]
        if "user_id" not in col_names:
            cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_updated_at 
            ON sessions (updated_at);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id 
            ON sessions (user_id);
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_session_id_id 
            ON messages (session_id, id ASC);
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_workflows (
                workflow_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                state TEXT NOT NULL,
                step TEXT NOT NULL,
                operation TEXT NOT NULL,
                pending_action TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                checkpoint_data_json TEXT,
                resume_token TEXT
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_workflows_session_wf 
            ON user_workflows (session_id, workflow_id);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_workflows_expires 
            ON user_workflows (expires_at);
            """
        )
        conn.commit()


def create_session(
    session_id: Optional[str] = None,
    initial_state: Optional[Dict[str, Any]] = None,
    status: str = "INIT",
    user_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates and stores a new persistent session record.
    Generates a UUIDv4 session identifier if none is provided.
    Optionally associates with server-verified user_id.
    """
    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)
    sid = session_id.strip() if session_id and session_id.strip() else str(uuid.uuid4())
    uid = user_id.strip() if user_id and user_id.strip() else None
    now_iso = _get_utc_now_iso()

    # Build initial state dictionary
    state = json.loads(json.dumps(DEFAULT_STATE_TEMPLATE))
    if initial_state:
        # Merge top-level keys
        for k, v in initial_state.items():
            if isinstance(v, dict) and isinstance(state.get(k), dict):
                state[k].update(v)
            else:
                state[k] = v

    # Attach core envelope metadata
    session_record = {
        "session_id": sid,
        "status": status,
        "created_at": now_iso,
        "updated_at": now_iso,
        "user_id": uid,
        "state": state,
    }

    state_json = json.dumps(state, ensure_ascii=False)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (session_id, status, created_at, updated_at, state_json, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sid, status, now_iso, now_iso, state_json, uid),
        )
        conn.commit()

    return session_record


def get_session(
    session_id: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a session by identifier.
    Returns None if session does not exist or if corrupted.
    """
    if not session_id or not isinstance(session_id, str):
        return None

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_id, status, created_at, updated_at, state_json, user_id
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id.strip(),),
        )
        row = cursor.fetchone()

    if not row:
        return None

    sid, status, created_at, updated_at, state_json, user_id = row

    try:
        state = json.loads(state_json)
    except (json.JSONDecodeError, TypeError):
        # Malformed JSON handling: return safe degraded representation without raising
        return {
            "session_id": sid,
            "status": "CORRUPTED",
            "created_at": created_at,
            "updated_at": updated_at,
            "user_id": user_id,
            "state": json.loads(json.dumps(DEFAULT_STATE_TEMPLATE)),
            "_corrupted": True,
        }

    return {
        "session_id": sid,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "user_id": user_id,
        "state": state,
    }


def update_session(
    session_id: str,
    updates: Optional[Dict[str, Any]] = None,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Updates an existing session record by merging updates into its state.
    Preserves all existing unmentioned fields.
    Transactionally commits changes to SQLite.
    Returns the updated session dict or None if session does not exist.
    """
    if not session_id or not isinstance(session_id, str):
        return None

    actual_db_path = db_path or DEFAULT_DB_PATH
    existing = get_session(session_id, db_path=actual_db_path)
    if not existing:
        return None

    state = existing.get("state", {})
    now_iso = _get_utc_now_iso()
    new_status = status if status is not None else existing.get("status", "ACTIVE")
    new_user_id = user_id if user_id is not None else existing.get("user_id")

    if updates:
        for k, v in updates.items():
            if k == "user_id" and v is not None:
                new_user_id = str(v).strip()
            elif isinstance(v, dict) and isinstance(state.get(k), dict):
                # Deep merge for dictionary sub-trees (e.g. requirements, selected_options)
                state[k].update(v)
            else:
                state[k] = v

    state_json = json.dumps(state, ensure_ascii=False)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE sessions
            SET status = ?, updated_at = ?, state_json = ?, user_id = ?
            WHERE session_id = ?
            """,
            (new_status, now_iso, state_json, new_user_id, session_id.strip()),
        )
        conn.commit()

    return {
        "session_id": session_id.strip(),
        "status": new_status,
        "created_at": existing["created_at"],
        "updated_at": now_iso,
        "user_id": new_user_id,
        "state": state,
    }


def update_session_user(
    session_id: str,
    user_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Associates an active session with a server-verified user_id."""
    if not session_id or not user_id:
        return False
    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)
    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET user_id = ? WHERE session_id = ?",
            (user_id.strip(), session_id.strip()),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_sessions_by_user(
    user_id: str,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves all sessions tagged with user_id ordered by last update time."""
    if not user_id:
        return []
    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)
    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_id, status, created_at, updated_at, user_id
            FROM sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id.strip(), limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "session_id": r[0],
                "status": r[1],
                "created_at": r[2],
                "updated_at": r[3],
                "user_id": r[4],
            }
            for r in rows
        ]


def delete_session(
    session_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Deletes a session record. Returns True if deleted, False if not found."""
    if not session_id or not isinstance(session_id, str):
        return False

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id.strip(),),
        )
        sessions_deleted = cursor.rowcount > 0
        cursor.execute(
            "DELETE FROM messages WHERE session_id = ?",
            (session_id.strip(),),
        )
        conn.commit()
        return sessions_deleted


def list_sessions(
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lists recent session summaries ordered by last update time."""
    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_id, status, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    return [
        {
            "session_id": r[0],
            "status": r[1],
            "created_at": r[2],
            "updated_at": r[3],
        }
        for r in rows
    ]


def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Optional[int]:
    """
    Persists a dialogue message (user, assistant, or system) for a session.
    Returns the auto-incremented message ID, or None if session_id/content is invalid.
    """
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        return None
    if not content or not isinstance(content, str):
        return None
    if role not in ("user", "assistant", "system"):
        role = "user"

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)
    sid = session_id.strip()
    now_iso = _get_utc_now_iso()
    meta_json = json.dumps(metadata, ensure_ascii=False) if metadata is not None else None

    lock = get_session_lock(sid)
    with lock:
        with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sid, role, content, meta_json, now_iso),
            )
            msg_id = cursor.lastrowid
            conn.commit()
            return msg_id


def get_messages(
    session_id: str,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves chronological messages for a given session_id.
    Returns empty list if session_id is invalid or no messages exist.
    """
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        return []

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)
    sid = session_id.strip()

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, role, content, metadata_json, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (sid, limit),
        )
        rows = cursor.fetchall()

    messages = []
    for r in rows:
        meta = None
        if r[4]:
            try:
                meta = json.loads(r[4])
            except (json.JSONDecodeError, TypeError):
                meta = {}
        messages.append({
            "id": r[0],
            "session_id": r[1],
            "role": r[2],
            "content": r[3],
            "metadata": meta,
            "created_at": r[5],
        })
    return messages


def clear_messages(
    session_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Clears message history for a session."""
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        return False

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)
    sid = session_id.strip()

    lock = get_session_lock(sid)
    with lock:
        with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (sid,),
            )
            conn.commit()
            return cursor.rowcount >= 0


def delete_message(
    message_id: int,
    db_path: Optional[str] = None,
) -> bool:
    """
    Deletes a single message by ID.
    Used for rolling back uncompleted conversational turns when downstream processing fails.
    """
    if not message_id or not isinstance(message_id, int):
        return False

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()
        return cursor.rowcount > 0


# ==============================================================================
# WEEK 8: USER-CONTROLLED WORKFLOW PERSISTENCE & HUMAN-IN-THE-LOOP STATE MACHINE
# ==============================================================================

WORKFLOW_STATE_WAITING_FOR_USER = "WAITING_FOR_USER"
WORKFLOW_STATE_OTP_REQUIRED = "OTP_REQUIRED"
WORKFLOW_STATE_CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
WORKFLOW_STATE_MANUAL_CONFIRMATION_REQUIRED = "MANUAL_CONFIRMATION_REQUIRED"
WORKFLOW_STATE_USER_ACTION_COMPLETED = "USER_ACTION_COMPLETED"
WORKFLOW_STATE_RESUME_ALLOWED = "RESUME_ALLOWED"
WORKFLOW_STATE_HANDOVER_REQUIRED = "HANDOVER_REQUIRED"
WORKFLOW_STATE_CANCELLED = "CANCELLED"
WORKFLOW_STATE_EXPIRED = "EXPIRED"
WORKFLOW_STATE_COMPLETED = "COMPLETED"

ACTIVE_INTERVENTION_STATES = {
    WORKFLOW_STATE_WAITING_FOR_USER,
    WORKFLOW_STATE_OTP_REQUIRED,
    WORKFLOW_STATE_CAPTCHA_REQUIRED,
    WORKFLOW_STATE_MANUAL_CONFIRMATION_REQUIRED,
    WORKFLOW_STATE_USER_ACTION_COMPLETED,
    WORKFLOW_STATE_RESUME_ALLOWED,
}

RESUMABLE_STATES = {
    WORKFLOW_STATE_WAITING_FOR_USER,
    WORKFLOW_STATE_OTP_REQUIRED,
    WORKFLOW_STATE_CAPTCHA_REQUIRED,
    WORKFLOW_STATE_MANUAL_CONFIRMATION_REQUIRED,
    WORKFLOW_STATE_USER_ACTION_COMPLETED,
    WORKFLOW_STATE_RESUME_ALLOWED,
}

SENSITIVE_KEY_PATTERNS = {
    "otp", "password", "passcode", "pin", "cvv", "captcha", "secret", "card_number",
    "credit_card", "debit_card", "auth_token", "private_key", "payment_token"
}


def sanitize_checkpoint_data(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Strict security filter: removes any sensitive security attributes from checkpoint metadata.
    Guarantees OTPs, passwords, CAPTCHA solutions, or payment cards are NEVER stored in SQLite.
    """
    if not data or not isinstance(data, dict):
        return {}
    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        k_lower = str(k).lower()
        if any(p in k_lower for p in SENSITIVE_KEY_PATTERNS):
            continue
        if isinstance(v, dict):
            sanitized[k] = sanitize_checkpoint_data(v)
        elif isinstance(v, list):
            cleaned_list = []
            for item in v:
                if isinstance(item, dict):
                    cleaned_list.append(sanitize_checkpoint_data(item))
                elif isinstance(item, (str, int, float, bool)):
                    cleaned_list.append(item)
            sanitized[k] = cleaned_list
        elif isinstance(v, (str, int, float, bool)) or v is None:
            sanitized[k] = v
    return sanitized


def create_user_workflow(
    session_id: str,
    state: str,
    step: str,
    operation: str,
    pending_action: str,
    expires_in_seconds: int = 300,
    checkpoint_data: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates and persists a new user-controlled workflow record in SQLite.
    Guarantees that sensitive credentials (OTP, password, CAPTCHA solution) are stripped.
    Bounded expiration is enforced via expires_at.
    """
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id is required to create a workflow")

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)

    workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    expires_dt = now_dt + timedelta(seconds=max(30, int(expires_in_seconds)))
    expires_iso = expires_dt.isoformat()

    sanitized_cp = sanitize_checkpoint_data(checkpoint_data)
    cp_json = json.dumps(sanitized_cp, ensure_ascii=False)
    resume_token = str(uuid.uuid4())

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_workflows (
                workflow_id, session_id, state, step, operation,
                pending_action, created_at, updated_at, expires_at,
                checkpoint_data_json, resume_token
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                session_id.strip(),
                state,
                step,
                operation,
                pending_action,
                now_iso,
                now_iso,
                expires_iso,
                cp_json,
                resume_token,
            ),
        )
        conn.commit()

    return {
        "workflow_id": workflow_id,
        "session_id": session_id.strip(),
        "state": state,
        "step": step,
        "operation": operation,
        "pending_action": pending_action,
        "created_at": now_iso,
        "updated_at": now_iso,
        "expires_at": expires_iso,
        "checkpoint_data": sanitized_cp,
        "resume_token": resume_token,
    }


def get_user_workflow(
    workflow_id: str,
    session_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a persistent workflow record by workflow_id.
    Enforces cross-session isolation: if session_id is provided and does not match, returns None.
    Automatically checks and enforces expiration: transitions active workflows to EXPIRED if past expires_at.
    """
    if not workflow_id or not isinstance(workflow_id, str) or not workflow_id.strip():
        return None

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT workflow_id, session_id, state, step, operation,
                   pending_action, created_at, updated_at, expires_at,
                   checkpoint_data_json, resume_token
            FROM user_workflows
            WHERE workflow_id = ?
            """,
            (workflow_id.strip(),),
        )
        row = cursor.fetchone()

        if not row:
            return None

        (
            wf_id,
            s_id,
            state,
            step,
            operation,
            pending_action,
            created_at,
            updated_at,
            expires_at,
            cp_json,
            resume_token,
        ) = row

        # Cross-session isolation check
        if session_id and session_id.strip() != s_id:
            logger.warning(
                "Cross-session access rejected: workflow %s belongs to session %s, not %s",
                wf_id,
                s_id,
                session_id,
            )
            return None

        # Expiration check
        now_dt = datetime.now(timezone.utc)
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        except Exception:
            exp_dt = now_dt

        if now_dt > exp_dt and state in ACTIVE_INTERVENTION_STATES:
            # Mark expired in DB
            new_updated_at = _get_utc_now_iso()
            cursor.execute(
                """
                UPDATE user_workflows
                SET state = ?, updated_at = ?, pending_action = ?
                WHERE workflow_id = ?
                """,
                (
                    WORKFLOW_STATE_EXPIRED,
                    new_updated_at,
                    "Workflow expired due to inactivity",
                    wf_id,
                ),
            )
            conn.commit()
            state = WORKFLOW_STATE_EXPIRED
            updated_at = new_updated_at
            pending_action = "Workflow expired due to inactivity"

    try:
        cp_data = json.loads(cp_json) if cp_json else {}
    except Exception:
        cp_data = {}

    return {
        "workflow_id": wf_id,
        "session_id": s_id,
        "state": state,
        "step": step,
        "operation": operation,
        "pending_action": pending_action,
        "created_at": created_at,
        "updated_at": updated_at,
        "expires_at": expires_at,
        "checkpoint_data": cp_data,
        "resume_token": resume_token,
    }


def update_user_workflow(
    workflow_id: str,
    session_id: Optional[str] = None,
    state: Optional[str] = None,
    step: Optional[str] = None,
    pending_action: Optional[str] = None,
    checkpoint_data: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Updates a user-controlled workflow record transactionally.
    Guarantees:
    1. Cross-session isolation if session_id is provided.
    2. Cancelled and expired workflows cannot be modified or resumed.
    3. Checkpoint data is sanitized to prevent sensitive data persistence.
    """
    actual_db_path = db_path or DEFAULT_DB_PATH
    current = get_user_workflow(workflow_id, session_id=session_id, db_path=actual_db_path)
    if not current:
        return None

    # Cancelled or expired workflows must NOT resume or be updated to active
    if current["state"] in (WORKFLOW_STATE_CANCELLED, WORKFLOW_STATE_EXPIRED):
        raise ValueError(f"Cannot update or resume workflow in terminal state: {current['state']}")

    new_state = state if state is not None else current["state"]
    new_step = step if step is not None else current["step"]
    new_pending = pending_action if pending_action is not None else current["pending_action"]

    merged_cp = dict(current.get("checkpoint_data", {}))
    if checkpoint_data:
        merged_cp.update(sanitize_checkpoint_data(checkpoint_data))
    new_cp_json = json.dumps(merged_cp, ensure_ascii=False)
    now_iso = _get_utc_now_iso()

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE user_workflows
            SET state = ?, step = ?, pending_action = ?, checkpoint_data_json = ?, updated_at = ?
            WHERE workflow_id = ?
            """,
            (new_state, new_step, new_pending, new_cp_json, now_iso, workflow_id.strip()),
        )
        conn.commit()

    current["state"] = new_state
    current["step"] = new_step
    current["pending_action"] = new_pending
    current["checkpoint_data"] = merged_cp
    current["updated_at"] = now_iso
    return current


def cancel_user_workflow(
    workflow_id: str,
    session_id: str,
    reason: str = "User cancelled workflow",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Safely transitions a workflow to CANCELLED state.
    Enforces cross-session security.
    """
    actual_db_path = db_path or DEFAULT_DB_PATH
    current = get_user_workflow(workflow_id, session_id=session_id, db_path=actual_db_path)
    if not current:
        return {
            "status": "error",
            "message": "Workflow not found or session mismatch.",
            "workflow_id": workflow_id,
        }

    now_iso = _get_utc_now_iso()
    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE user_workflows
            SET state = ?, pending_action = ?, updated_at = ?
            WHERE workflow_id = ?
            """,
            (
                WORKFLOW_STATE_CANCELLED,
                f"CANCELLED: {reason}",
                now_iso,
                workflow_id.strip(),
            ),
        )
        conn.commit()

    return {
        "status": "success",
        "workflow_id": workflow_id,
        "state": WORKFLOW_STATE_CANCELLED,
        "message": f"Workflow successfully cancelled: {reason}",
    }


def list_user_workflows(
    session_id: str,
    active_only: bool = False,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lists persistent workflows associated with a specific session_id."""
    if not session_id or not isinstance(session_id, str):
        return []

    actual_db_path = db_path or DEFAULT_DB_PATH
    init_db(actual_db_path)

    with sqlite3.connect(actual_db_path, timeout=10.0) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT workflow_id, session_id, state, step, operation,
                   pending_action, created_at, updated_at, expires_at,
                   checkpoint_data_json, resume_token
            FROM user_workflows
            WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id.strip(),),
        )
        rows = cursor.fetchall()

    results = []
    for r in rows:
        wf = {
            "workflow_id": r[0],
            "session_id": r[1],
            "state": r[2],
            "step": r[3],
            "operation": r[4],
            "pending_action": r[5],
            "created_at": r[6],
            "updated_at": r[7],
            "expires_at": r[8],
            "checkpoint_data": json.loads(r[9]) if r[9] else {},
            "resume_token": r[10],
        }
        if active_only and wf["state"] not in ACTIVE_INTERVENTION_STATES:
            continue
        results.append(wf)
    return results



