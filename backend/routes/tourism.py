from fastapi import APIRouter
from pydantic import BaseModel

import agents.coordinator as coordinator


router = APIRouter(
    prefix="/api/tourism",
    tags=["Tourism"],
)


class TourismRequest(BaseModel):
    query: str
    last_tourism_place: str | None = None


@router.post("/")
def tourism(request: TourismRequest):
    result = coordinator.answer_tourism_query(
        user_text=request.query,
        last_tourism_place=request.last_tourism_place,
    )

    return result