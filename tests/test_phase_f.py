"""
test_phase_f.py
Phase F Unit Test Suite — Tool Orchestration, Intent Routing, and Human-in-the-Loop Booking.
Run with: python test_phase_f.py
"""
import copy
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents import coordinator, tools, itinerary_agent, recommendation_agent
import agent as legacy_agent

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


print("=" * 70)
print("PHASE F — TOOL ORCHESTRATION & BOOKING WORKFLOW TEST SUITE")
print("=" * 70)

base_req = {
    "origin": "Delhi",
    "pax": 4,
    "duration_days": 5,
    "mode": "train",
    "category": "Normal Darshan",
    "sightseeing": True,
    "group_type": "family",
    "travel_style": "relaxed",
    "trip_focus": "mixed",
    "budget_preference": "comfortable",
}

# --- TEST 1: Tourism -> Knowledge Tool ---
print("\nTEST 1: Tourism -> Knowledge Tool")
res1 = coordinator.route_message("Tell me about Bhairavnath.")
check("intent is TOURISM", res1.get("intent") == "TOURISM")
check("reply mentions Bhairavnath", "Bhairavnath" in res1.get("reply", ""))
check("query_kind is place", res1.get("query_kind") == "place")

# --- TEST 2: Transport -> Transport Tool ---
print("\nTEST 2: Transport -> Transport Tool")
res2 = coordinator.route_message("What trains can I take from Delhi?", current_request=base_req)
check("intent is TRIP_PLANNING", res2.get("intent") == "TRIP_PLANNING")
plan2 = res2.get("plan") or {}
check("plan status is PLAN_READY", plan2.get("status") == "PLAN_READY")
check("options returned", bool(plan2.get("options")))

# --- TEST 3: Weather -> Weather Tool ---
print("\nTEST 3: Weather -> Weather Tool")
res3 = coordinator.route_message("What is the weather in Katra?")
check("intent is WEATHER", res3.get("intent") == "WEATHER")
check("reply contains Katra Weather Guidance", "Katra Weather Guidance" in res3.get("reply", ""))
t_exec3 = res3.get("tool_execution") or {}
check("tool invoked is check_weather_tool", t_exec3.get("tool") == "check_weather_tool")
check("tool status success", t_exec3.get("status") == "success")

# --- TEST 4: Trip Planning -> Multi-Tool Workflow ---
print("\nTEST 4: Trip Planning -> Multi-Tool Workflow (transport + recommendation + itinerary)")
res4 = coordinator.route_message("Plan a 5-day trip from Delhi for my family.")
check("intent is TRIP_PLANNING", res4.get("intent") == "TRIP_PLANNING")
check("request created with origin Delhi", res4.get("request", {}).get("origin") == "Delhi")
check("recommendation generated", bool(res4.get("recommendation")))
check("itinerary generated", bool(res4.get("itinerary")))

# --- TEST 5: Itinerary -> Itinerary Tool ---
print("\nTEST 5: Itinerary -> Itinerary Tool")
res5 = coordinator.route_message("What am I doing on Day 2?", current_request=base_req)
check("intent is ITINERARY", res5.get("intent") == "ITINERARY")
check("reply contains Day 2 breakdown", "Day 2" in res5.get("reply", ""))

# --- TEST 6: Booking without explicit confirmation -> RPA NOT invoked ---
print("\nTEST 6: Booking without explicit confirmation -> RPA NOT invoked")
dummy_options = {
    "pax": 4,
    "options": [
        {
            "transport": {"mode": "train", "operator": "Northern Rail", "origin": "Delhi", "destination": "Katra", "travel_date": "2026-10-01", "departure_time": "06:00", "price": 800},
            "slot": {"category": "Normal Darshan", "slot_date": "2026-10-02", "slot_time": "10:00", "price": 0},
            "total_price": 3200,
        }
    ]
}
res6 = coordinator.route_message("Book option 1", current_request=base_req, pending_options=dummy_options)
check("intent is BOOKING", res6.get("intent") == "BOOKING")
check("presents Human Confirmation Gate", "Human Confirmation Required" in res6.get("reply", ""))
t_exec6 = res6.get("tool_execution") or {}
check("status is pending_human_confirmation", t_exec6.get("status") == "pending_human_confirmation")
check("RPA info is None", res6.get("rpa_info") is None)

# --- TEST 7: Booking after explicit confirmation -> RPA invoked ---
print("\nTEST 7: Booking after explicit confirmation -> RPA invoked")
res7 = coordinator.route_message("Yes, confirm booking", current_request=base_req, pending_options=dummy_options)
check("intent is BOOKING", res7.get("intent") == "BOOKING")
check("reply confirms execution", "Booking Executed & Confirmed" in res7.get("reply", ""))
t_exec7 = res7.get("tool_execution") or {}
check("tool invoked is execute_rpa_booking_tool", t_exec7.get("tool") == "execute_rpa_booking_tool")
check("status is success", t_exec7.get("status") == "success")
check("rpa_info contains booking_id", bool(res7.get("rpa_info", {}).get("booking_id")))

# --- TEST 8: Tool Failure -> Graceful Fallback ---
print("\nTEST 8: Tool Failure -> Graceful Fallback")
# Pass unsupported city to transport tool
res8 = coordinator.route_message("Search transport from Atlantis for 5 days.")
check("handles unsupported city gracefully", "not represented" in (res8.get("reply") or "").lower() or "PLAN_READY" in res8.get("plan", {}).get("status", ""))
check("does not crash conversation", res8.get("intent") == "TRIP_PLANNING")

# --- TEST 9: Tourism isolation ---
print("\nTEST 9: Tourism isolation")
res9 = coordinator.route_message("What should I pack for the Yatra?", current_request=base_req)
check("intent is TOURISM", res9.get("intent") == "TOURISM")
check("request returned is None (state preserved)", res9.get("request") is None)

# --- TEST 10: Phase D edits still work ---
print("\nTEST 10: Phase D edits still work")
res10 = coordinator.route_message("Make the trip 6 days.", current_request=base_req)
check("duration changed to 6", res10.get("request", {}).get("duration_days") == 6)
check("origin preserved Delhi", res10.get("request", {}).get("origin") == "Delhi")

# --- TEST 11: Phase E itinerary edits still work ---
print("\nTEST 11: Phase E itinerary edits still work")
itin_base = itinerary_agent.generate_default_itinerary(base_req)
res11 = coordinator.route_message("Add Bhairavnath on Day 2.", current_request=base_req, current_itinerary=itin_base)
check("intent is ITINERARY", res11.get("intent") == "ITINERARY")
itin11 = res11.get("itinerary") or []
check("Bhairavnath added to Day 2", any("Bhairavnath" in a for a in itin11[1]["activities"]))

# --- TEST 12: Context preservation across tool invocations ---
print("\nTEST 12: Context preservation across tool invocations")
# 1. Weather query
r_w = coordinator.route_message("What's the weather in Katra?", current_request=base_req, current_itinerary=itin_base)
# 2. Tourism query
r_t = coordinator.route_message("Tell me about Bhairavnath.", current_request=base_req, current_itinerary=itin_base)
# 3. Itinerary query
r_i = coordinator.route_message("Show Day 2.", current_request=base_req, current_itinerary=itin_base)

check("weather does not wipe trip request", r_w.get("request") == base_req)
check("tourism does not wipe trip request", r_t.get("request") is None)
check("itinerary query preserves trip request", r_i.get("request") == base_req)

print("\n" + "=" * 70)
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
