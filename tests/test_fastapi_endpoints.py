import os
import sys
import io
sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("=== 1. Health Endpoint ===")
r_health = client.get("/api/health")
assert r_health.status_code == 200
print("PASS: Health ->", r_health.json())

print("\n=== 2. Chat Endpoint ===")
r_chat = client.post("/api/chat", json={"message": "What places can I visit around Katra?"})
assert r_chat.status_code == 200
chat_data = r_chat.json()
assert chat_data.get("intent") == "TOURISM"
assert len(chat_data.get("reply", "")) > 20
print("PASS: Chat Tourism -> intent:", chat_data["intent"], "reply length:", len(chat_data["reply"]))

print("\n=== 3. Yatra Search Endpoint ===")
r_yatra = client.post("/api/yatra/", json={"message": "2 people from Delhi to Katra on 20 October 2026 by train for 4 days with VIP darshan"})
assert r_yatra.status_code == 200
yatra_data = r_yatra.json()
assert yatra_data.get("intent") == "TRIP_PLANNING"
plan = yatra_data.get("plan", {})
options = plan.get("options", [])
assert len(options) > 0
print(f"PASS: Yatra Search -> {len(options)} options returned")

selected_option = options[0]

print("\n=== 4. Accommodation Endpoint ===")
r_hotel = client.post("/api/yatra/accommodation", json={"check_in_date": "2026-10-20", "category": None, "min_rooms": 1})
assert r_hotel.status_code == 200
hotel_data = r_hotel.json()
assert hotel_data.get("status") == "success"
hotels = hotel_data.get("hotels", [])
assert len(hotels) > 0
print(f"PASS: Accommodation -> {len(hotels)} hotels returned. First hotel: {hotels[0]['name']}")

selected_hotel = hotels[0]

print("\n=== 5. Sightseeing Endpoint (29 Places) ===")
r_places = client.post("/api/yatra/sightseeing", json={"category": None})
assert r_places.status_code == 200
places_data = r_places.json()
assert places_data.get("status") == "success"
places = places_data.get("places", [])
assert len(places) == 29
print(f"PASS: Sightseeing -> exactly {len(places)} destinations returned")

selected_places = [places[0]["name"], places[1]["name"]]

print("\n=== 6. Itinerary Generation Endpoint ===")
r_itin = client.post("/api/yatra/itinerary", json={
    "option": selected_option,
    "hotel": selected_hotel,
    "hotel_nights": 2,
    "sightseeing_places": selected_places,
    "request": yatra_data.get("request")
})
assert r_itin.status_code == 200
itin_data = r_itin.json()
assert itin_data.get("status") == "success"
days = itin_data.get("itinerary", [])
assert len(days) > 0
print(f"PASS: Itinerary -> {len(days)} days generated. Day 1: {days[0]['title']}")

sid = yatra_data.get("session_id")
curr_version = yatra_data.get("plan_version", 1)

print("\n=== 7. Human Authorization Gate & Confirm Endpoint ===")
# Without authorization -> should reject
r_unauth = client.post("/api/yatra/confirm", json={
    "option": selected_option,
    "pax": 2,
    "user_name": "Test-Pilgrim",
    "hotel": selected_hotel,
    "hotel_nights": 2,
    "sightseeing_places": selected_places,
    "human_authorized": False,
    "session_id": sid,
    "plan_version": curr_version,
})
assert r_unauth.json().get("status") == "authorization_required"
print("PASS: Human gate prevented un-authorized confirmation")

# Record server-side authorization
r_grant = client.post("/api/yatra/authorize", json={
    "session_id": sid,
    "plan_version": curr_version,
})
assert r_grant.json().get("status") == "success"
print("PASS: Human authorization recorded on server")

# With authorization -> should confirm
r_auth = client.post("/api/yatra/confirm", json={
    "option": selected_option,
    "pax": 2,
    "user_name": "Test-Pilgrim",
    "hotel": selected_hotel,
    "hotel_nights": 2,
    "sightseeing_places": selected_places,
    "human_authorized": True,
    "session_id": sid,
    "plan_version": curr_version,
})
auth_data = r_auth.json()
assert auth_data.get("status") == "success"
assert "booking_id" in auth_data
print(f"PASS: Human authorization confirmed booking -> ID: {auth_data['booking_id']}")

print("\n=== 8. Playwright RPA Endpoint ===")
r_rpa = client.post("/api/yatra/rpa", json={
    "user_name": "Test-Pilgrim",
    "pax_count": 2,
    "transport_text": "train from Delhi",
    "slot_text": "VIP Darshan",
    "total_price": 2400.0,
    "headless": True,
    "session_id": sid,
    "plan_version": curr_version,
    "human_authorized": True,
})
assert r_rpa.status_code == 200
rpa_data = r_rpa.json()
assert rpa_data.get("status") == "success"
rpa_info = rpa_data.get("rpa", {})
assert "booking_id" in rpa_info
print(f"PASS: Playwright RPA demonstration -> RPA Ref: {rpa_info['booking_id']}")

print("\n=======================================================")
print("ALL FASTAPI ENDPOINTS VERIFIED AND WORKING 100%!")
print("=======================================================")
