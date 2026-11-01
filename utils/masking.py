"""
utils/masking.py
Week 10: Reusable Sensitive Data Masking Utility.

Provides uniform masking and redaction functions across backend routes,
agents, and logging handlers to prevent accidental exposure of personally
identifiable information (PII) and security credentials.
"""

import re
from typing import Any, Dict, List, Union, Optional

# Pre-compiled regular expressions for string scrubbing
EMAIL_REGEX = re.compile(r"(?<!\*)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
GROQ_API_KEY_REGEX = re.compile(r"\bgsk_[A-Za-z0-9_]{8,}\b")
MONGO_URI_AUTH_REGEX = re.compile(r"mongodb(\+srv)?:\/\/[^:]+:[^@]+@")
BEARER_TOKEN_REGEX = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]{16,}\b")
COOKIE_TOKEN_REGEX = re.compile(r"(?i)yatra_auth_session=[A-Za-z0-9_\-\.]{16,}")
LABELED_OTP_REGEX = re.compile(r"(?i)\b(otp|otp_code|code|verification_code)\s*[:=\s]\s*(['\"]?)(\d{6})\2\b")
PHONE_REGEX = re.compile(r"\b(?:\+91[\s-]?)?[6789]\d{9}\b")

# Keys classified as sensitive across payloads and dictionaries
SENSITIVE_KEY_PATTERNS = {
    "otp": ("otp", "otp_code", "verification_code", "sms_code", "pin"),
    "token": ("token", "session_token", "auth_token", "access_token", "jwt", "yatra_auth_session", "authorization"),
    "secret": ("password", "secret", "api_key", "groq_api_key", "smtp_password", "auth_hmac_secret", "mongo_uri", "credential"),
    "email": ("email", "to_email", "user_email", "recipient_email"),
    "phone": ("phone", "mobile", "contact_number", "phone_number"),
    "name": ("user_name", "pax_name", "traveler_name", "full_name", "name"),
}


def mask_email(email: Optional[str]) -> str:
    """
    Masks an email address to protect user identity while preserving domain context for diagnostics.
    Example: 'pragati@example.com' -> 'p*****i@example.com'
    """
    if not email or not isinstance(email, str):
        return ""
    email = email.strip()
    if "@" not in email:
        return "[INVALID_EMAIL]"

    parts = email.split("@", 1)
    local, domain = parts[0], parts[1]

    if len(local) <= 1:
        masked_local = "*"
    elif len(local) == 2:
        masked_local = f"{local[0]}*{local[1]}"
    else:
        num_asterisks = len(local) - 2
        masked_local = f"{local[0]}{'*' * num_asterisks}{local[-1]}"

    return f"{masked_local}@{domain}"


def mask_otp(otp: Any) -> str:
    """
    Redacts OTP verification codes completely.
    Example: '123456' -> '[REDACTED]'
    """
    if otp is None or otp == "":
        return ""
    return "[REDACTED]"


def mask_token(token: Any) -> str:
    """
    Redacts session tokens, bearer tokens, and credentials completely.
    Example: 'abc12345...' -> '[REDACTED]'
    """
    if token is None or token == "":
        return ""
    return "[REDACTED]"


def mask_api_key(key: Any) -> str:
    """
    Redacts external service API keys and secrets completely.
    Example: 'gsk_...' -> '[REDACTED]'
    """
    if key is None or key == "":
        return ""
    return "[REDACTED]"


def mask_phone(phone: Optional[str]) -> str:
    """
    Masks telephone/mobile numbers while keeping area prefixes and trailing digits.
    Example: '9876543210' -> '98*****210'
    """
    if not phone or not isinstance(phone, str):
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return str(phone)
    prefix = phone[: len(phone) - 8] if len(phone) > 10 else phone[:2]
    suffix = phone[-3:]
    return f"{prefix}*****{suffix}"


def mask_name(name: Optional[str]) -> str:
    """
    Masks user personal names to protect pilgrim privacy in operational logs.
    Example: 'Pragati Sharma' -> 'P***** S*****'
    """
    if not name or not isinstance(name, str):
        return ""
    tokens = name.strip().split()
    masked_tokens = []
    for token in tokens:
        if len(token) <= 1:
            masked_tokens.append(token)
        else:
            masked_tokens.append(f"{token[0]}*****")
    return " ".join(masked_tokens)


def _matches_pattern(key: str, patterns: tuple) -> bool:
    key_lower = key.lower()
    return any(p in key_lower for p in patterns)


def mask_sensitive_data(data: Any, key_name: Optional[str] = None) -> Any:
    """
    Recursively scans and masks sensitive data within dictionaries, lists, or primitive values.
    Applies context-aware masking based on dictionary keys or content heuristics.
    """
    if data is None:
        return None

    # 1. Dictionary traversal (always preserve structure for nested objects)
    if isinstance(data, dict):
        masked_dict = {}
        for k, v in data.items():
            masked_dict[k] = mask_sensitive_data(v, key_name=str(k))
        return masked_dict

    # 2. List / Tuple / Set traversal
    if isinstance(data, (list, tuple, set)):
        masked_list = [mask_sensitive_data(item, key_name=key_name) for item in data]
        if isinstance(data, tuple):
            return tuple(masked_list)
        if isinstance(data, set):
            return set(masked_list)
        return masked_list

    # 3. Key-driven masking for primitive/scalar values
    if key_name:
        k = key_name.lower()
        if _matches_pattern(k, SENSITIVE_KEY_PATTERNS["otp"]):
            return mask_otp(data)
        if _matches_pattern(k, SENSITIVE_KEY_PATTERNS["token"]):
            return mask_token(data)
        if _matches_pattern(k, SENSITIVE_KEY_PATTERNS["secret"]):
            return mask_api_key(data)
        if _matches_pattern(k, SENSITIVE_KEY_PATTERNS["email"]):
            return mask_email(str(data))
        if _matches_pattern(k, SENSITIVE_KEY_PATTERNS["phone"]):
            return mask_phone(str(data))
        if _matches_pattern(k, SENSITIVE_KEY_PATTERNS["name"]):
            return mask_name(str(data))

    # 4. Freeform string scrubbing (if passed as scalar)
    if isinstance(data, str):
        return sanitize_log_message(data)

    return data


def sanitize_log_message(message: str) -> str:
    """
    Scrubs sensitive patterns (emails, API keys, OTPs, auth tokens) from freeform log strings.
    Ensures safe emission even if raw unmasked strings are passed to logging calls.
    """
    if not isinstance(message, str):
        message = str(message)

    # 1. Redact Groq API Keys
    scrubbed = GROQ_API_KEY_REGEX.sub("[REDACTED]", message)

    # 2. Redact MongoDB Credentials in URIs
    scrubbed = MONGO_URI_AUTH_REGEX.sub(r"mongodb\1://[REDACTED]:[REDACTED]@", scrubbed)

    # 3. Redact Bearer Tokens
    scrubbed = BEARER_TOKEN_REGEX.sub("Bearer [REDACTED]", scrubbed)

    # 4. Redact Cookie Session Tokens
    scrubbed = COOKIE_TOKEN_REGEX.sub("yatra_auth_session=[REDACTED]", scrubbed)

    # 5. Redact Labeled OTP codes (e.g. 'otp: 123456', 'code=654321', 'OTP 654321')
    scrubbed = LABELED_OTP_REGEX.sub(r"\1 [REDACTED]", scrubbed)

    # 6. Mask Plain Email Addresses
    def _email_replacer(match):
        return mask_email(match.group(0))

    scrubbed = EMAIL_REGEX.sub(_email_replacer, scrubbed)

    return scrubbed
