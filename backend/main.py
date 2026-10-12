from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.routes.weather import router as weather_router
import agents.coordinator as coordinator
from backend.routes.tourism import router as tourism_router
from backend.routes.yatra import router as yatra_router

app = FastAPI(
    title="Yatra Booking Agent API",
    description="AI-powered Vaishno Devi Yatra Planning and Booking API",
    version="1.0.0",
)


# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tourism_router)
app.include_router(weather_router)
app.include_router(yatra_router)

class ChatRequest(BaseModel):
    message: str
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
def chat(request: ChatRequest):

    result = coordinator.route_message(
        user_text=request.message,
        current_request=request.current_request,
        current_itinerary=request.current_itinerary,
        last_tourism_place=request.last_tourism_place,
        last_itinerary_context=request.last_itinerary_context,
        pending_options=request.pending_options,
    )

    return result