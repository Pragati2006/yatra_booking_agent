"""
backend/routes/auth.py
Week 9: Optional Passwordless Email Authentication and User Data REST API.

Endpoints:
- POST /api/auth/request-otp          : Requests a 6-digit OTP to user's email
- POST /api/auth/verify-otp           : Verifies OTP, sets HttpOnly cookie & creates session
- GET  /api/auth/me                   : Retrieves authenticated user state (or Guest Mode)
- POST /api/auth/logout               : Revokes server session and clears cookie
- POST /api/auth/save-itinerary       : Saves generated itinerary to user account
- GET  /api/auth/saved-itineraries    : Lists saved itineraries for authenticated user
- DELETE /api/auth/saved-itinerary/{id}: Deletes saved itinerary with ownership check
- POST /api/auth/save-conversation    : Saves chat conversation to user account
- GET  /api/auth/saved-conversations  : Lists saved conversations for authenticated user
- DELETE /api/auth/saved-conversation/{id}: Deletes saved conversation with ownership check
- GET  /api/auth/test/latest-otp      : Test-only inspection endpoint (mock provider only)
"""

import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Response, Header, Cookie, HTTPException
from pydantic import BaseModel, Field

from utils.masking import mask_email, mask_otp, mask_token, mask_sensitive_data
from utils.logger import log_event

logger = logging.getLogger(__name__)

from agents.auth_service import (
    auth_service,
    get_email_provider,
    MockEmailProvider,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

AUTH_COOKIE_NAME = "yatra_auth_session"


def is_dev_test_mode_enabled() -> bool:
    """
    Checks if development/test endpoints are explicitly permitted.
    Returns False in production mode or if explicitly disabled.
    """
    env = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower()
    if env in ("production", "prod", "live"):
        return False
    if os.getenv("ENABLE_DEV_TEST_ENDPOINTS", "true").lower() in ("false", "0", "no"):
        return False
    return True


def is_cookie_secure(request: Request) -> bool:
    """Determines if the session cookie should have the Secure flag set."""
    env = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower()
    if env in ("production", "prod", "live"):
        return True
    return request.url.scheme == "https" or os.getenv("COOKIE_SECURE", "false").lower() == "true"


def verify_csrf_protection(request: Request):
    """
    Guards state-changing endpoints (/save-itinerary, /saved-itinerary/{id}, /save-conversation, etc.)
    against Cross-Site Request Forgery (CSRF).
    - Requests bearing explicit Authorization headers (Bearer tokens) are immune to CSRF.
    - Cookie-authenticated requests must have a matching Origin or Referer from allowed hosts,
      or include custom headers (e.g. X-Requested-With or X-CSRF-Token).
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # 1. Bearer token requests are immune to CSRF because browsers never automatically attach them
    auth_hdr = request.headers.get("Authorization")
    if auth_hdr and auth_hdr.lower().startswith("bearer "):
        return

    # 2. Check if authenticated via ambient cookie
    if AUTH_COOKIE_NAME in request.cookies:
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        custom_header = request.headers.get("X-Requested-With") or request.headers.get("X-CSRF-Token")
        if custom_header:
            return

        if origin:
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            netloc = parsed.netloc.lower()
            allowed_hosts = {
                "localhost:5173", "127.0.0.1:5173",
                "localhost:8000", "127.0.0.1:8000",
                "localhost:3000", "127.0.0.1:3000",
            }
            if netloc in allowed_hosts or netloc.startswith("localhost:") or netloc.startswith("127.0.0.1:"):
                return
            log_event(
                logger,
                logging.WARNING,
                "AUTH_CSRF_BLOCK",
                f"CSRF check blocked request from origin: {origin}",
                error_category="CSRF_VIOLATION",
                details={"origin": origin},
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF validation failed: cross-origin submission forbidden.",
            )


def extract_session_token(
    request: Request,
    authorization: Optional[str] = None,
    cookie_token: Optional[str] = None,
) -> Optional[str]:
    """
    Extracts session token from Authorization Bearer header or HttpOnly cookie.
    Prioritizes explicit Authorization header before ambient cookie.
    """
    # 1. Check explicit parameter or header
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    auth_hdr = request.headers.get("Authorization")
    if auth_hdr and auth_hdr.lower().startswith("bearer "):
        return auth_hdr[7:].strip()
    # 2. Check explicit cookie param or request cookies
    if cookie_token:
        return cookie_token
    if AUTH_COOKIE_NAME in request.cookies:
        return request.cookies[AUTH_COOKIE_NAME]
    return None


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------

class RequestOTPRequest(BaseModel):
    email: str = Field(..., description="User's email address")


class VerifyOTPRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    otp_code: str = Field(..., description="6-digit verification code")


class SaveItineraryRequest(BaseModel):
    title: str = Field(default="My Vaishno Devi Yatra", description="Title of saved itinerary")
    itinerary: Any = Field(..., description="Itinerary data payload")


class SaveConversationRequest(BaseModel):
    title: str = Field(default="Yatra Consultation Chat", description="Title of chat thread")
    messages: List[Dict[str, Any]] = Field(..., description="List of chat messages")


class SaveBookingRequest(BaseModel):
    booking_id: str = Field(..., description="Simulated booking reference")
    pax_count: int = Field(default=1, description="Number of pilgrims")
    slot_date: str = Field(default="2026-10-20", description="Darshan slot date")
    category: str = Field(default="Normal Darshan", description="Darshan category")
    slot_time: Optional[str] = Field(default=None, description="Darshan slot time")
    transport_mode: Optional[str] = Field(default="Train", description="Transport mode")
    transport_info: Optional[str] = Field(default=None, description="Transport particulars")
    hotel_name: Optional[str] = Field(default=None, description="Hotel name")
    total_price: float = Field(default=0.0, description="Total price")
    session_id: Optional[str] = Field(default=None, description="Associated session ID")
    plan_version: Optional[int] = Field(default=1, description="Associated plan version")
    receipt: Optional[Dict[str, Any]] = Field(default=None, description="Receipt payload")


class TransferConversationRequest(BaseModel):
    session_id: str = Field(..., description="Active guest session ID to transfer")
    title: Optional[str] = Field(default=None, description="Optional title for saved chat")


class TransferTripRequest(BaseModel):
    session_id: str = Field(..., description="Active guest session ID containing itinerary")
    title: Optional[str] = Field(default=None, description="Optional title for saved trip")


class TransferBookingRequest(BaseModel):
    booking_id: str = Field(..., description="Simulated booking reference to transfer")
    session_id: Optional[str] = Field(default=None, description="Associated guest session ID")


# -----------------------------------------------------------------------------
# 1. Public Authentication Endpoints
# -----------------------------------------------------------------------------

@router.post("/request-otp")
def request_otp_endpoint(payload: RequestOTPRequest):
    """
    Requests a one-time verification code sent to user's email.
    Enforces 60-second cooldown and email format validation.
    """
    log_event(
        logger,
        logging.INFO,
        "API_AUTH_REQUEST_OTP",
        "Client submitted OTP request",
        details={"email": mask_email(payload.email)},
    )
    res = auth_service.request_otp(payload.email)
    if res.get("status") == "rate_limited":
        raise HTTPException(
            status_code=429,
            detail=res,
        )
    if res.get("status") == "error":
        raise HTTPException(
            status_code=400,
            detail=res,
        )
    return res


@router.post("/verify-otp")
def verify_otp_endpoint(payload: VerifyOTPRequest, request: Request, response: Response):
    """
    Verifies 6-digit verification code.
    If valid, creates account (if new) or logs in existing user.
    Sets secure HttpOnly cookie and returns session token.
    """
    log_event(
        logger,
        logging.INFO,
        "API_AUTH_VERIFY_OTP",
        "Client submitted OTP verification code",
        details={"email": mask_email(payload.email), "otp_code": mask_otp(payload.otp_code)},
    )
    res = auth_service.verify_otp(payload.email, payload.otp_code)
    if res.get("status") == "error":
        err_code = res.get("error_code")
        status_code = 400
        if err_code in ("CODE_EXPIRED", "NO_ACTIVE_CHALLENGE", "MAX_ATTEMPTS_EXCEEDED"):
            status_code = 400
        elif err_code == "INCORRECT_CODE":
            status_code = 401
        raise HTTPException(
            status_code=status_code,
            detail=res,
        )

    # Set secure HttpOnly cookie
    token = res.get("session_token")
    if token:
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            max_age=7 * 24 * 3600,
            httponly=True,
            samesite="lax",
            secure=is_cookie_secure(request),
        )
    return res


@router.get("/me")
def get_current_user_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None),
    yatra_auth_session: Optional[str] = Cookie(None),
):
    """
    Returns current authentication status.
    Default Guest Mode: If no session or invalid, returns status='guest' with user=None (200 OK).
    Never blocks unauthenticated guests from browsing.
    """
    token = extract_session_token(request, authorization, yatra_auth_session)
    if not token:
        return {
            "status": "guest",
            "authenticated": False,
            "user": None,
        }

    user = auth_service.get_user_by_session_token(token)
    if not user:
        return {
            "status": "guest",
            "authenticated": False,
            "user": None,
        }

    return {
        "status": "authenticated",
        "authenticated": True,
        "user": user,
    }


@router.post("/logout")
def logout_endpoint(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(None),
    yatra_auth_session: Optional[str] = Cookie(None),
):
    """
    Revokes server-side session and clears the HttpOnly cookie.
    Transitions interface back to Guest Mode.
    """
    log_event(
        logger,
        logging.INFO,
        "API_AUTH_LOGOUT",
        "Client submitted logout request",
    )
    token = extract_session_token(request, authorization, yatra_auth_session)
    if token:
        auth_service.logout_session(token)

    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=is_cookie_secure(request),
    )
    return {
        "status": "success",
        "message": "Successfully logged out. Returned to Guest Mode.",
    }


# -----------------------------------------------------------------------------
# 2. Authenticated Personal Data Endpoints (Strict User Isolation)
# -----------------------------------------------------------------------------

def require_authenticated_user(request: Request) -> Dict[str, Any]:
    """Helper verifying that caller is an authenticated user; raises 401 otherwise."""
    verify_csrf_protection(request)

    token = extract_session_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access personal saved records. Please sign in.",
        )
    user = auth_service.get_user_by_session_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Session has expired or is invalid. Please sign in again.",
        )
    return user


@router.post("/save-itinerary")
def save_itinerary_endpoint(payload: SaveItineraryRequest, request: Request):
    """Saves generated itinerary for authenticated user."""
    user = require_authenticated_user(request)
    saved = auth_service.save_itinerary(
        user_id=user["user_id"],
        title=payload.title,
        itinerary_data=payload.itinerary,
    )
    return {
        "status": "success",
        "message": "Itinerary saved to your account.",
        "itinerary": saved,
    }


@router.get("/saved-itineraries")
def get_saved_itineraries_endpoint(request: Request):
    """Lists saved itineraries for authenticated user."""
    user = require_authenticated_user(request)
    itineraries = auth_service.get_saved_itineraries(user_id=user["user_id"])
    return {
        "status": "success",
        "count": len(itineraries),
        "itineraries": itineraries,
    }


@router.delete("/saved-itinerary/{itinerary_id}")
def delete_saved_itinerary_endpoint(itinerary_id: str, request: Request):
    """Deletes saved itinerary strictly verifying user ownership."""
    user = require_authenticated_user(request)
    deleted = auth_service.delete_saved_itinerary(
        user_id=user["user_id"],
        itinerary_id=itinerary_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Itinerary not found or access denied.",
        )
    return {
        "status": "success",
        "message": "Saved itinerary deleted.",
        "itinerary_id": itinerary_id,
    }


@router.post("/save-conversation")
def save_conversation_endpoint(payload: SaveConversationRequest, request: Request):
    """Saves conversation chat thread for authenticated user."""
    user = require_authenticated_user(request)
    saved = auth_service.save_conversation(
        user_id=user["user_id"],
        title=payload.title,
        messages=payload.messages,
    )
    return {
        "status": "success",
        "message": "Conversation saved to your account.",
        "conversation": saved,
    }


@router.get("/saved-conversations")
def get_saved_conversations_endpoint(request: Request):
    """Lists saved conversations for authenticated user."""
    user = require_authenticated_user(request)
    conversations = auth_service.get_saved_conversations(user_id=user["user_id"])
    return {
        "status": "success",
        "count": len(conversations),
        "conversations": conversations,
    }


@router.delete("/saved-conversation/{conversation_id}")
def delete_saved_conversation_endpoint(conversation_id: str, request: Request):
    """Deletes saved conversation strictly verifying user ownership."""
    user = require_authenticated_user(request)
    deleted = auth_service.delete_saved_conversation(
        user_id=user["user_id"],
        conversation_id=conversation_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )
    return {
        "status": "success",
        "message": "Saved conversation deleted.",
        "conversation_id": conversation_id,
    }


# -----------------------------------------------------------------------------
# 3. Account-Linked Mock Bookings & Selective Transfers
# -----------------------------------------------------------------------------

@router.get("/saved-bookings")
def get_saved_bookings_endpoint(request: Request):
    """Lists verified simulated bookings for authenticated user."""
    user = require_authenticated_user(request)
    bookings = auth_service.get_user_bookings(user_id=user["user_id"])
    return {
        "status": "success",
        "count": len(bookings),
        "bookings": bookings,
    }


@router.get("/saved-bookings/{booking_id}")
def get_saved_booking_detail_endpoint(booking_id: str, request: Request):
    """Retrieves specific simulated booking strictly verifying ownership."""
    user = require_authenticated_user(request)
    booking = auth_service.get_user_booking(user_id=user["user_id"], booking_id=booking_id)
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking record not found or access denied.",
        )
    return {
        "status": "success",
        "booking": booking,
    }


@router.post("/save-booking")
def save_booking_endpoint(payload: SaveBookingRequest, request: Request):
    """Explicitly associates/saves a verified simulated booking for authenticated user."""
    user = require_authenticated_user(request)
    try:
        saved = auth_service.save_booking(
            user_id=user["user_id"],
            booking_data=payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
        )
        return {
            "status": "success",
            "message": "Simulated booking saved to your account.",
            "booking": saved,
        }
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/transfer-conversation")
def transfer_conversation_endpoint(payload: TransferConversationRequest, request: Request):
    """Selectively imports a guest conversational session to authenticated user's account."""
    user = require_authenticated_user(request)
    saved = auth_service.transfer_guest_conversation_to_user(
        user_id=user["user_id"],
        session_id=payload.session_id,
        title=payload.title,
    )
    if not saved:
        raise HTTPException(
            status_code=404,
            detail="No messages found for specified session ID to transfer.",
        )
    return {
        "status": "success",
        "message": "Conversation successfully transferred to your account.",
        "conversation": saved,
    }


@router.post("/transfer-trip")
def transfer_trip_endpoint(payload: TransferTripRequest, request: Request):
    """Selectively imports a guest trip plan to authenticated user's account."""
    user = require_authenticated_user(request)
    saved = auth_service.transfer_guest_trip_to_user(
        user_id=user["user_id"],
        session_id=payload.session_id,
        title=payload.title,
    )
    if not saved:
        raise HTTPException(
            status_code=404,
            detail="No trip plan found for specified session ID to transfer.",
        )
    return {
        "status": "success",
        "message": "Trip plan successfully transferred to your account.",
        "itinerary": saved,
    }


@router.post("/transfer-booking")
def transfer_booking_endpoint(payload: TransferBookingRequest, request: Request):
    """Selectively imports a guest simulated booking to authenticated user's account."""
    user = require_authenticated_user(request)
    try:
        saved = auth_service.transfer_guest_booking_to_user(
            user_id=user["user_id"],
            booking_id=payload.booking_id,
            session_id=payload.session_id,
        )
        if not saved:
            raise HTTPException(
                status_code=404,
                detail="Booking record not found for transfer or already belongs to another user.",
            )
        return {
            "status": "success",
            "message": "Simulated booking successfully transferred to your account.",
            "booking": saved,
        }
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )


@router.get("/profile")
def get_user_profile_endpoint(request: Request):
    """Retrieves user profile summary and saved counts."""
    user = require_authenticated_user(request)
    summary = auth_service.get_user_profile_summary(user_id=user["user_id"])
    return {
        "status": "success",
        "profile": summary,
    }


# -----------------------------------------------------------------------------
# 3. Test-Only Mock Inspection Endpoint
# -----------------------------------------------------------------------------

@router.get("/test/latest-otp")
def get_latest_test_otp_endpoint(email: str):
    """
    Test-only inspection endpoint: retrieves the latest OTP generated in MockEmailProvider.
    Strictly blocked in production (returns 404 Not Found to prevent route discovery or exposure).
    """
    if not is_dev_test_mode_enabled():
        raise HTTPException(
            status_code=404,
            detail="Not Found",
        )
    provider = get_email_provider()
    if not isinstance(provider, MockEmailProvider):
        raise HTTPException(
            status_code=404,
            detail="Not Found",
        )
    latest_otp = provider.get_latest_otp_for(email)
    if not latest_otp:
        raise HTTPException(
            status_code=404,
            detail="No verification code found in mock outbox for this email.",
        )
    return {
        "email": email,
        "latest_otp": latest_otp,
    }
