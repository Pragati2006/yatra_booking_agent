import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from backend.routes.weather import router as weather_router
import agents.coordinator as coordinator
import agents.session_store as session_store
from backend.routes.tourism import router as tourism_router
from backend.routes.yatra import router as yatra_router
from backend.routes.auth import router as auth_router
from utils.logger import SanitizingFormatter, set_correlation_id, get_correlation_id, log_event

# Configure root logger with SanitizingFormatter
root_logger = logging.getLogger()
if not root_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(SanitizingFormatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
    root_logger.addHandler(_handler)
else:
    for _handler in root_logger.handlers:
        _handler.setFormatter(SanitizingFormatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Yatra Booking Agent API",
    description="AI-powered Vaishno Devi Yatra Planning and Booking API",
    version="1.0.0",
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
        correlation_id = set_correlation_id(cid)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


app.add_middleware(CorrelationIdMiddleware)

# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tourism_router)
app.include_router(weather_router)
app.include_router(yatra_router)
app.include_router(auth_router)

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    current_request: dict | None = None
    current_itinerary: list | None = None
    last_tourism_place: str | None = None
    last_itinerary_context: dict | None = None
    pending_options: list | None = None


@app.get("/")
def root():
    return {
        "message": "Yatra Booking Agent API is running",
        "status": "success"
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "Yatra Booking Agent"
    }


@app.post("/api/chat")
def chat(request: ChatRequest, http_request: Request = None):

    result = coordinator.route_message(
        user_text=request.message,
        session_id=request.session_id,
        current_request=request.current_request,
        current_itinerary=request.current_itinerary,
        last_tourism_place=request.last_tourism_place,
        last_itinerary_context=request.last_itinerary_context,
        pending_options=request.pending_options,
    )

    # Link session to authenticated user if signed in
    if http_request is not None:
        try:
            from backend.routes.auth import extract_session_token
            from agents.auth_service import auth_service
            token = extract_session_token(http_request)
            if token:
                user = auth_service.get_user_by_session_token(token)
                sid = (result or {}).get("session_id") or request.session_id
                if user and sid:
                    session_store.update_session_user(sid, user["user_id"])
        except Exception as exc:
            logger.debug("Silently ignored session user update error: %s", exc)

    return result


@app.get("/api/chat/history/{session_id}")
def get_chat_history(session_id: str):
    """
    Returns persistent chat history for a session in chronological order.
    Returns an empty message list for unknown or new sessions without creating a session record.
    Raises HTTPException 500 on database retrieval errors.
    """
    try:
        messages = session_store.get_messages(session_id)
        return {
            "session_id": session_id,
            "messages": messages,
        }
    except Exception as exc:
        logger.error("Failed to retrieve chat history for session %s: %s", session_id, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve conversation history",
        )
