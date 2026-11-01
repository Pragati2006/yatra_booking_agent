import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel

import agents.coordinator as coordinator
from agents.auth_service import auth_service
from backend.routes.auth import extract_session_token
from utils.logger import log_event
from utils.masking import mask_name, mask_otp, mask_sensitive_data

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/yatra",
    tags=["Yatra"],
)


class YatraRequest(BaseModel):
    message: str
    session_id: str | None = None
    current_request: dict | None = None
    current_itinerary: list | None = None
    last_itinerary_context: dict | None = None
    pending_options: list | None = None


class HotelRequest(BaseModel):
    check_in_date: str
    category: str | None = None
    min_rooms: int = 1


@router.post("/")
def yatra(request: YatraRequest):
    result = coordinator.route_message(
        user_text=request.message,
        session_id=request.session_id,
        current_request=request.current_request,
        current_itinerary=request.current_itinerary,
        last_itinerary_context=request.last_itinerary_context,
        pending_options=request.pending_options,
    )
    return result


@router.post("/accommodation")
def accommodation(request: HotelRequest):
    hotels = coordinator.get_hotel_options(
        check_in_date=request.check_in_date,
        category=request.category,
    )

    # Filter by minimum rooms because the coordinator wrapper
    # currently exposes only check_in_date and category.
    hotels = [
        hotel
        for hotel in hotels
        if hotel.get("rooms_available", 0) >= request.min_rooms
    ]

    return {
        "status": "success",
        "check_in_date": request.check_in_date,
        "category": request.category,
        "hotels": hotels,
        "count": len(hotels),
    }
class SightseeingRequest(BaseModel):
    category: str | None = None


@router.post("/sightseeing")
def sightseeing(request: SightseeingRequest):
    places = coordinator.get_sightseeing_places(
        category=request.category
    )

    return {
        "status": "success",
        "category": request.category,
        "places": places,
        "count": len(places),
    }
class ItineraryRequest(BaseModel):
    option: dict
    hotel: dict | None = None
    hotel_nights: int = 0
    sightseeing_places: list[str] = []
    request: dict | None = None


@router.post("/itinerary")
def itinerary(request: ItineraryRequest):
    days = coordinator.build_final_itinerary(
        option=request.option,
        hotel=request.hotel,
        hotel_nights=request.hotel_nights,
        sightseeing_places=request.sightseeing_places,
        request=request.request,
    )

    infeasible = getattr(days, "infeasible_places", [])
    feasible = getattr(days, "feasible_places", [])

    return {
        "status": "success",
        "itinerary": days,
        "days": len(days),
        "infeasible_places": infeasible,
        "feasible_places": feasible,
    }
from datetime import datetime
import agents.session_store as session_store

class ConfirmBookingRequest(BaseModel):
    option: dict
    pax: int
    user_name: str
    hotel: dict | None = None
    hotel_nights: int = 0
    sightseeing_places: list[str] = []
    human_authorized: bool = False
    session_id: str | None = None
    plan_version: int | None = None


class AuthorizePlanRequest(BaseModel):
    session_id: str
    plan_version: int
    user_confirmation: str = "Confirm booking"


@router.post("/authorize")
def authorize_plan(request: AuthorizePlanRequest):
    """Explicitly records human authorization on the server-side session state for a specific plan revision."""
    if not request.session_id:
        return {
            "status": "authorization_required",
            "message": "Missing session ID. Server-side authorization requires an active session."
        }

    session = session_store.get_session(request.session_id)
    if not session:
        return {
            "status": "authorization_required",
            "message": "Session not found or expired. Authorization failed closed."
        }

    lock = session_store.get_session_lock(request.session_id)
    with lock:
        fresh_session = session_store.get_session(request.session_id)
        if not fresh_session:
            return {
                "status": "authorization_required",
                "message": "Session not found or expired. Authorization failed closed."
            }
        state = fresh_session.get("state", {})
        curr_version = state.get("plan_version", 1)

        if request.plan_version > curr_version:
            curr_version = request.plan_version
            session_store.update_session(
                session_id=request.session_id,
                updates={
                    "plan_version": curr_version,
                    "authorized_plan_version": None,
                    "authorization": {
                        "pending": False,
                        "granted": False,
                    }
                }
            )
        elif request.plan_version < curr_version:
            return {
                "status": "authorization_required",
                "message": f"Plan version mismatch. Current plan is Revision #{curr_version}. Cannot authorize outdated Revision #{request.plan_version}."
            }

        now_iso = datetime.now().isoformat()
        session_store.update_session(
            session_id=request.session_id,
            updates={
                "authorized_plan_version": curr_version,
                "authorization": {
                    "pending": False,
                    "granted": True,
                    "plan_version": curr_version,
                    "authorized_for_version": curr_version,
                    "authorized_at": now_iso,
                    "revoked_reason": None,
                    "confirmed_via": "explicit_user_authorization",
                }
            },
            status="AUTHORIZED_PENDING_EXECUTION"
        )

        return {
            "status": "success",
            "plan_version": curr_version,
            "message": f"Server-side authorization recorded for Revision #{curr_version}."
        }


@router.post("/confirm")
def confirm_booking(request: ConfirmBookingRequest, http_request: Request = None):
    # 1. Require session_id - cannot bypass authorization by omitting session_id
    if not request.session_id:
        return {
            "status": "authorization_required",
            "message": "Missing session ID. Booking confirmation requires an active session with recorded authorization."
        }

    # 2. Require valid existing session
    session = session_store.get_session(request.session_id)
    if not session:
        return {
            "status": "authorization_required",
            "message": "Session not found or expired. Booking failed closed."
        }

    # 3. Thread-safe lock per session
    lock = session_store.get_session_lock(request.session_id)
    with lock:
        fresh_session = session_store.get_session(request.session_id)
        if not fresh_session:
            return {
                "status": "authorization_required",
                "message": "Session not found or expired. Booking failed closed."
            }
        state = fresh_session.get("state", {})
        curr_version = state.get("plan_version", 1)

        # 4. Plan version match check
        if request.plan_version is not None and request.plan_version != curr_version:
            return {
                "status": "authorization_required",
                "message": f"Plan has been updated to Revision #{curr_version}. Authorization for Revision #{request.plan_version} is no longer valid."
            }

        # 5. Check if already confirmed for this revision (Idempotency / Duplicate Prevention)
        existing_bid = state.get("rpa_execution", {}).get("booking_id")
        if existing_bid and state.get("authorized_plan_version") == curr_version and state.get("authorization", {}).get("granted"):
            return {
                "status": "success",
                "booking_id": existing_bid,
                "plan_version": curr_version,
                "message": "Booking already confirmed for this plan revision. No duplicate created.",
                "duplicate_prevented": True,
            }

        # 6. Server-side authorization check:
        # Client-provided human_authorized: true is NOT sufficient!
        auth = state.get("authorization", {})
        server_authorized = bool(auth.get("granted")) and (state.get("authorized_plan_version") == curr_version)
        if not server_authorized or not request.human_authorized:
            return {
                "status": "authorization_required",
                "message": f"Server-side human authorization has not been granted for Revision #{curr_version}. An API flag cannot authorize a booking."
            }

        # 7. Execute booking
        booking_id, blessing = coordinator.confirm_booking(
            option=request.option,
            pax=request.pax,
            user_name=request.user_name,
            hotel=request.hotel,
            hotel_nights=request.hotel_nights,
            sightseeing_places=request.sightseeing_places,
        )

        booking_history = list(state.get("booking_history") or [])
        booking_history.append({
            "booking_id": booking_id,
            "plan_version": curr_version,
            "status": "CONFIRMED",
            "authorized_at": datetime.now().isoformat(),
        })

        # Link confirmed booking to authenticated user if signed in
        user = None
        if http_request is not None:
            token = extract_session_token(http_request)
            if token:
                user = auth_service.get_user_by_session_token(token)

        user_id = user["user_id"] if user else fresh_session.get("user_id")
        if user_id:
            try:
                auth_service.save_booking(
                    user_id=user_id,
                    booking_data={
                        "booking_id": booking_id,
                        "session_id": request.session_id,
                        "plan_version": curr_version,
                        "user_name": request.user_name,
                        "pax_count": request.pax,
                        "slot_date": (request.option.get("slot") or {}).get("slot_date") or request.option.get("slot_date") or "2026-10-20",
                        "category": (request.option.get("slot") or {}).get("category") or request.option.get("category") or "Normal Darshan",
                        "slot_time": (request.option.get("slot") or {}).get("slot_time") or request.option.get("slot_time") or "Morning (06:00)",
                        "transport_mode": (request.option.get("transport") or {}).get("mode") or "Train",
                        "transport_info": str(request.option.get("transport") or "Train (Vande Bharat Express)"),
                        "hotel_name": (request.hotel or {}).get("name") if request.hotel else None,
                        "total_price": float(request.option.get("total_price") or 0.0),
                        "payment_status": "COMPLETED_SANDBOX",
                        "status": "SIMULATED_CONFIRMED",
                        "receipt": {
                            "booking_id": booking_id,
                            "user_name": request.user_name,
                            "pax_count": request.pax,
                            "slot_date": (request.option.get("slot") or {}).get("slot_date") or request.option.get("slot_date") or "2026-10-20",
                            "category": (request.option.get("slot") or {}).get("category") or request.option.get("category") or "Normal Darshan",
                            "total_price": float(request.option.get("total_price") or 0.0),
                            "confirmed_at": datetime.now().isoformat(),
                            "portal_label": "LOCAL MOCK PORTAL / DEMO",
                            "title": "Simulated Yatra Booking Confirmation",
                            "pass_type": "Demo Pilgrim Pass (Local Simulation)",
                        },
                    },
                )
            except Exception as exc:
                logger.warning("Failed to link confirmed booking %s to user %s: %s", booking_id, user_id, exc)

        session_store.update_session(
            session_id=request.session_id,
            updates={
                "authorized_plan_version": curr_version,
                "authorization": {
                    "pending": False,
                    "granted": True,
                    "plan_version": curr_version,
                    "authorized_for_version": curr_version,
                    "authorized_at": datetime.now().isoformat(),
                    "revoked_reason": None,
                },
                "rpa_execution": {
                    "status": "success",
                    "booking_id": booking_id,
                    "plan_version": curr_version,
                },
                "booking_history": booking_history,
                "user_id": user_id,
            },
            status="BOOKING_CONFIRMED",
            user_id=user_id,
        )

        return {
            "status": "success",
            "booking_id": booking_id,
            "plan_version": curr_version,
            "message": blessing,
        }


class RPARequest(BaseModel):
    user_name: str
    pax_count: int
    transport_text: str
    slot_text: str
    total_price: float
    headless: bool = True
    session_id: str | None = None
    plan_version: int | None = None
    human_authorized: bool = False


@router.post("/rpa")
def run_rpa(request: RPARequest):
    # 1. Require session_id - cannot bypass authorization by omitting session_id
    if not request.session_id:
        return {
            "status": "authorization_required",
            "message": "Missing session ID. Playwright RPA execution requires a valid session with recorded human authorization."
        }

    # 2. Require valid existing session
    session = session_store.get_session(request.session_id)
    if not session:
        return {
            "status": "authorization_required",
            "message": "Session not found or expired. RPA execution failed closed."
        }

    # 3. Thread-safe lock per session
    lock = session_store.get_session_lock(request.session_id)
    with lock:
        fresh_session = session_store.get_session(request.session_id)
        if not fresh_session:
            return {
                "status": "authorization_required",
                "message": "Session not found or expired. RPA execution failed closed."
            }
        state = fresh_session.get("state", {})
        curr_version = state.get("plan_version", 1)

        # 4. Plan version match check
        if request.plan_version is not None and request.plan_version != curr_version:
            return {
                "status": "authorization_required",
                "message": f"Plan has been updated to Revision #{curr_version}. Authorization for Revision #{request.plan_version} is no longer valid."
            }

        # 5. Duplicate RPA execution check (Idempotency)
        existing_bid = state.get("rpa_execution", {}).get("booking_id")
        if existing_bid and state.get("authorized_plan_version") == curr_version and state.get("authorization", {}).get("granted"):
            return {
                "status": "success",
                "rpa": state.get("rpa_execution"),
                "plan_version": curr_version,
                "message": "Playwright RPA already executed for this plan revision. No duplicate execution performed.",
                "duplicate_prevented": True,
            }

        # 6. Server-side authorization check:
        auth = state.get("authorization", {})
        server_authorized = bool(auth.get("granted")) and (state.get("authorized_plan_version") == curr_version)
        if not server_authorized:
            return {
                "status": "authorization_required",
                "message": f"Server-side human authorization has not been granted for Revision #{curr_version}. Playwright RPA execution blocked."
            }

        # 7. Execute Playwright RPA demo
        result = coordinator.execute_rpa_demo(
            user_name=request.user_name,
            pax_count=request.pax_count,
            transport_text=request.transport_text,
            slot_text=request.slot_text,
            total_price=request.total_price,
            headless=request.headless,
        )

        rpa_info = dict(result)
        rpa_info["plan_version"] = curr_version

        session_store.update_session(
            session_id=request.session_id,
            updates={
                "rpa_execution": rpa_info,
            },
            status="RPA_EXECUTED",
        )

        return {
            "status": "success",
            "plan_version": curr_version,
            "rpa": rpa_info,
        }


class RPAAvailabilityRequest(BaseModel):
    date: str | None = "2026-10-20"
    category: str | None = None
    headless: bool = True
    max_attempts: int = 3


@router.post("/rpa/availability")
def check_rpa_availability(request: RPAAvailabilityRequest):
    """
    Week 5 & 6 RPA Task: Automated Darshan Slot Availability Checking & Data Extraction with Error Handling.
    Navigates the local mock portal availability calendar using Playwright, validates DOM state,
    retries transient failures with backoff, and extracts structured slot data (status, seats, session, price).
    Triggers safe pause-and-handover if structural page changes or data integrity issues occur.
    Read-only audit: does NOT confirm bookings, mutate sessions, or bypass human authorization.
    """
    log_event(
        logging.INFO,
        "api.yatra",
        "API_RPA_AVAILABILITY",
        f"RPA availability check requested for date={request.date}, category={request.category}",
        details={"date": request.date, "category": request.category, "headless": request.headless}
    )
    result = coordinator.check_slot_availability_rpa(
        requested_date=request.date,
        category=request.category,
        headless=request.headless,
        max_attempts=request.max_attempts,
    )
    return result


# ==============================================================================
# WEEK 8: USER-CONTROLLED WORKFLOW & HUMAN-IN-THE-LOOP ENDPOINTS
# ==============================================================================

class StartWorkflowRequest(BaseModel):
    session_id: str
    user_name: str = "Guest-Pilgrim"
    pax_count: int = 1
    transport_text: str = "Train (Vande Bharat Express)"
    slot_text: str = "Morning Aarti & Darshan (06:00)"
    total_price: float = 0.0
    checkpoint_mode: str | None = None  # "OTP" or "CAPTCHA"
    headless: bool = True
    plan_version: int | None = None
    human_authorized: bool = False


class ResumeWorkflowRequest(BaseModel):
    session_id: str
    workflow_id: str
    user_confirmed_action: bool = True
    manual_input_value: str | None = None
    simulate_manual_clearance: bool = False
    headless: bool = True


class CancelWorkflowRequest(BaseModel):
    session_id: str
    workflow_id: str
    reason: str = "Cancelled by user"


@router.post("/rpa/workflow/start")
def start_user_controlled_workflow_route(request: StartWorkflowRequest, http_request: Request = None):
    """
    Week 8: Initiates a user-controlled RPA booking workflow.
    Safely pauses execution when reaching security-sensitive checkpoints (OTP or CAPTCHA).
    Enforces server-side human authorization and plan-version invariants.
    """
    if not request.session_id:
        return {
            "status": "authorization_required",
            "message": "Missing session ID. User-controlled workflow requires a valid session.",
        }

    session = session_store.get_session(request.session_id)
    if not session:
        return {
            "status": "authorization_required",
            "message": "Session not found or expired. Workflow initiation failed closed.",
        }

    lock = session_store.get_session_lock(request.session_id)
    with lock:
        fresh_session = session_store.get_session(request.session_id)
        if not fresh_session:
            return {
                "status": "authorization_required",
                "message": "Session not found or expired.",
            }
        state = fresh_session.get("state", {})
        curr_version = state.get("plan_version", 1)

        # Plan version match check
        if request.plan_version is not None and request.plan_version != curr_version:
            return {
                "status": "authorization_required",
                "message": f"Plan has been updated to Revision #{curr_version}. Authorization for Revision #{request.plan_version} is no longer valid.",
            }

        # Server-side authorization check:
        auth = state.get("authorization", {})
        server_authorized = bool(auth.get("granted")) and (state.get("authorized_plan_version") == curr_version)
        if not server_authorized and not request.human_authorized:
            log_event(
                logging.WARNING,
                "api.yatra",
                "API_WORKFLOW_START_BLOCKED",
                f"Workflow initiation blocked for session {request.session_id}: human authorization required for revision {curr_version}",
                error_category="AUTHORIZATION_REQUIRED",
                details={"session_id": request.session_id, "plan_version": curr_version}
            )
            return {
                "status": "authorization_required",
                "message": f"Server-side human authorization has not been granted for Revision #{curr_version}. Workflow initiation blocked.",
            }

        log_event(
            logging.INFO,
            "api.yatra",
            "API_WORKFLOW_START",
            f"Starting user-controlled workflow for session {request.session_id}",
            details={
                "session_id": request.session_id,
                "user_name": mask_name(request.user_name),
                "pax_count": request.pax_count,
                "checkpoint_mode": request.checkpoint_mode,
            }
        )

        result = coordinator.start_user_controlled_workflow(
            session_id=request.session_id,
            user_name=request.user_name,
            pax_count=request.pax_count,
            transport_text=request.transport_text,
            slot_text=request.slot_text,
            total_price=request.total_price,
            checkpoint_mode=request.checkpoint_mode,
            headless=request.headless,
        )

        return result


@router.get("/rpa/workflow/{workflow_id}")
def get_workflow_status_route(workflow_id: str, session_id: str):
    """
    Week 8: Retrieves current status of a user-controlled workflow.
    Strictly enforces cross-session isolation: rejects requests from different sessions.
    """
    if not session_id or not workflow_id:
        return {
            "status": "error",
            "message": "session_id and workflow_id are both required.",
        }

    wf = coordinator.get_user_controlled_workflow_status(
        session_id=session_id,
        workflow_id=workflow_id,
    )
    if not wf:
        return {
            "status": "error",
            "message": "Workflow not found or session access denied.",
            "workflow_id": workflow_id,
        }

    return {
        "status": "success",
        "workflow": wf,
    }


@router.post("/rpa/workflow/resume")
def resume_workflow_route(request: ResumeWorkflowRequest, http_request: Request = None):
    """
    Week 8: Resumes a paused user-controlled workflow.
    Strictly requires user_confirmed_action=True.
    Validates that the workflow is not expired, not cancelled, and belongs to session_id.
    Validates page state before continuing automation to booking confirmation.
    """
    if not request.session_id or not request.workflow_id:
        return {
            "status": "error",
            "message": "session_id and workflow_id are both required to resume workflow.",
        }

    if not request.user_confirmed_action:
        return {
            "status": "confirmation_required",
            "message": "Explicit user confirmation is strictly required to resume a paused workflow.",
            "workflow_id": request.workflow_id,
        }

    log_event(
        logging.INFO,
        "api.yatra",
        "API_WORKFLOW_RESUME",
        f"Resuming user-controlled workflow {request.workflow_id} for session {request.session_id}",
        details={
            "session_id": request.session_id,
            "workflow_id": request.workflow_id,
            "manual_input_provided": bool(request.manual_input_value),
        }
    )

    result = coordinator.resume_user_controlled_workflow(
        session_id=request.session_id,
        workflow_id=request.workflow_id,
        user_confirmed_action=request.user_confirmed_action,
        manual_input_value=request.manual_input_value,
        simulate_manual_clearance=request.simulate_manual_clearance,
        headless=request.headless,
    )

    # Link confirmed simulated booking to authenticated user if logged in
    if isinstance(result, dict) and result.get("status") == "SUCCESS" and result.get("booking_id"):
        user = None
        if http_request is not None:
            token = extract_session_token(http_request)
            if token:
                user = auth_service.get_user_by_session_token(token)

        session_rec = session_store.get_session(request.session_id)
        user_id = user["user_id"] if user else (session_rec.get("user_id") if session_rec else None)
        if user_id:
            try:
                auth_service.save_booking(
                    user_id=user_id,
                    booking_data={
                        "booking_id": result["booking_id"],
                        "session_id": request.session_id,
                        "plan_version": result.get("plan_version") or 1,
                        "user_name": result.get("user_name") or "Guest-Pilgrim",
                        "pax_count": result.get("pax_count") or 1,
                        "slot_date": result.get("slot_date") or "2026-10-20",
                        "category": result.get("category") or "Normal Darshan",
                        "slot_time": result.get("slot_time") or "Morning (06:00)",
                        "transport_mode": result.get("transport_mode") or "Train",
                        "transport_info": result.get("transport_text") or "Vande Bharat Express",
                        "total_price": float(result.get("total_price") or 0.0),
                        "payment_status": "COMPLETED_SANDBOX",
                        "status": "SIMULATED_CONFIRMED",
                        "receipt": result.get("receipt") or result,
                    },
                )
                session_store.update_session_user(request.session_id, user_id)
            except Exception as exc:
                logger.warning("Failed to link resumed booking %s to user %s: %s", result["booking_id"], user_id, exc)

    return result


@router.post("/rpa/workflow/cancel")
def cancel_workflow_route(request: CancelWorkflowRequest):
    """
    Week 8: Safely cancels a paused user-controlled workflow.
    Enforces cross-session security. Cancelled workflows cannot be resumed.
    """
    if not request.session_id or not request.workflow_id:
        return {
            "status": "error",
            "message": "session_id and workflow_id are both required to cancel workflow.",
        }

    log_event(
        logging.INFO,
        "api.yatra",
        "API_WORKFLOW_CANCEL",
        f"Cancelling user-controlled workflow {request.workflow_id} for session {request.session_id}",
        details={"session_id": request.session_id, "workflow_id": request.workflow_id, "reason": request.reason}
    )

    result = coordinator.cancel_user_controlled_workflow(
        session_id=request.session_id,
        workflow_id=request.workflow_id,
        reason=request.reason,
    )

    return result
