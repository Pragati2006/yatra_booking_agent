from fastapi import APIRouter
from pydantic import BaseModel

import agents.coordinator as coordinator

router = APIRouter(
    prefix="/api/yatra",
    tags=["Yatra"],
)


class YatraRequest(BaseModel):
    message: str
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

    return {
        "status": "success",
        "itinerary": days,
        "days": len(days),
    }
class ConfirmBookingRequest(BaseModel):
    option: dict
    pax: int
    user_name: str
    hotel: dict | None = None
    hotel_nights: int = 0
    sightseeing_places: list[str] = []
    
    human_authorized: bool = False


@router.post("/confirm")
def confirm_booking(request: ConfirmBookingRequest):
    if not request.human_authorized:
        return {
            "status": "authorization_required",
            "message": "Human authorization is required before booking."
        }

    booking_id, blessing = coordinator.confirm_booking(
        option=request.option,
        pax=request.pax,
        user_name=request.user_name,
        hotel=request.hotel,
        hotel_nights=request.hotel_nights,
        sightseeing_places=request.sightseeing_places,
    )

    return {
        "status": "success",
        "booking_id": booking_id,
        "message": blessing,
    }
class RPARequest(BaseModel):
    user_name: str
    pax_count: int
    transport_text: str
    slot_text: str
    total_price: float
    headless: bool = True


@router.post("/rpa")
def run_rpa(request: RPARequest):
    result = coordinator.execute_rpa_demo(
        user_name=request.user_name,
        pax_count=request.pax_count,
        transport_text=request.transport_text,
        slot_text=request.slot_text,
        total_price=request.total_price,
        headless=request.headless,
    )

    return {
        "status": "success",
        "rpa": result,
    }