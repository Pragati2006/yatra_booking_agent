from fastapi import APIRouter
from pydantic import BaseModel

import agents.coordinator as coordinator

router = APIRouter(
    prefix="/api/weather",
    tags=["Weather"],
)


class WeatherRequest(BaseModel):
    location: str


@router.post("/")
def weather(request: WeatherRequest):
    result = coordinator.route_message(
        user_text=f"What is the weather in {request.location}?"
    )

    return result