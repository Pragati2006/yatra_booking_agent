"""
test_phase_c.py
Phase C unit test suite — Personalized Trip Recommendation & Multi-turn Preference State.
Run with: python test_phase_c.py
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents import coordinator, recommendation_agent, conversation_agent
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
print("PHASE C — PERSONALIZED TRIP RECOMMENDATION & PREFERENCE TESTS")
print("=" * 70)

# --- TEST 1: Family preference extraction ---
print("\nTEST 1: Family preference extraction")
p1 = recommendation_agent.extract_preferences("I am travelling with my family.")
check("group_type is family", p1.get("group_type") == "family", repr(p1.get("group_type")))

# --- TEST 2: Relaxed preference extraction ---
print("\nTEST 2: Relaxed preference extraction")
p2 = recommendation_agent.extract_preferences("We want a relaxed trip.")
check("travel_style is relaxed", p2.get("travel_style") == "relaxed", repr(p2.get("travel_style")))

# --- TEST 3: Sightseeing preference extraction ---
print("\nTEST 3: Sightseeing preference extraction")
p3 = recommendation_agent.extract_preferences("We want sightseeing.")
check("trip_focus is sightseeing", p3.get("trip_focus") == "sightseeing", repr(p3.get("trip_focus")))

# --- TEST 4: Devotional preference extraction ---
print("\nTEST 4: Devotional preference extraction")
p4 = recommendation_agent.extract_preferences("The main purpose is the Vaishno Devi pilgrimage.")
check("trip_focus is devotional", p4.get("trip_focus") == "devotional", repr(p4.get("trip_focus")))

# --- TEST 5: Mixed preference extraction ---
print("\nTEST 5: Mixed preference extraction")
p5 = recommendation_agent.extract_preferences("We want both pilgrimage and sightseeing.")
check("trip_focus is mixed", p5.get("trip_focus") == "mixed", repr(p5.get("trip_focus")))

# --- TEST 6: Budget preference extraction ---
print("\nTEST 6: Budget preference extraction")
p6 = recommendation_agent.extract_preferences("Keep it budget friendly.")
check("budget_preference is budget", p6.get("budget_preference") == "budget", repr(p6.get("budget_preference")))

# --- TEST 7: Multi-turn preference update (family -> relaxed) ---
print("\nTEST 7: Multi-turn preference update (family 5 days -> make it relaxed)")
t1 = coordinator.route_message("I am travelling with my family for 5 days.")
req1 = t1.get("request") or {}
check("turn 1 duration=5", req1.get("duration_days") == 5, repr(req1.get("duration_days")))
check("turn 1 group_type=family", req1.get("group_type") == "family", repr(req1.get("group_type")))

t2 = coordinator.route_message("Make it relaxed.", current_request=req1)
req2 = t2.get("request") or {}
check("turn 2 duration kept=5", req2.get("duration_days") == 5, repr(req2.get("duration_days")))
check("turn 2 group_type kept=family", req2.get("group_type") == "family", repr(req2.get("group_type")))
check("turn 2 travel_style updated=relaxed", req2.get("travel_style") == "relaxed", repr(req2.get("travel_style")))

# --- TEST 8: Multi-turn (Delhi 5 days -> We want sightseeing) ---
print("\nTEST 8: Multi-turn (Delhi 5 days -> We want sightseeing)")
t1 = coordinator.route_message("Travelling from Delhi for 5 days.")
req1 = t1.get("request") or {}
check("turn 1 origin=Delhi", req1.get("origin") == "Delhi", repr(req1.get("origin")))
check("turn 1 duration=5", req1.get("duration_days") == 5, repr(req1.get("duration_days")))

t2 = coordinator.route_message("We want sightseeing.", current_request=req1)
req2 = t2.get("request") or {}
check("turn 2 origin kept=Delhi", req2.get("origin") == "Delhi", repr(req2.get("origin")))
check("turn 2 duration kept=5", req2.get("duration_days") == 5, repr(req2.get("duration_days")))
check("turn 2 sightseeing=True", req2.get("sightseeing") is True, repr(req2.get("sightseeing")))

# --- TEST 9: Recommendation generation with family + relaxed + mixed + 5 days ---
print("\nTEST 9: Recommendation generation (family + relaxed + mixed + 5 days)")
sample_req = {
    "pax": 4,
    "origin": "Delhi",
    "duration_days": 5,
    "group_type": "family",
    "travel_style": "relaxed",
    "trip_focus": "mixed",
    "budget_preference": "comfortable",
}
rec = recommendation_agent.generate_recommendation(sample_req)
card = rec.get("formatted_card") or ""
check("has PERSONALIZED TRIP RECOMMENDATION header", "PERSONALIZED TRIP RECOMMENDATION" in card)
check("has Profile Family", "Family" in card)
check("has Profile 5 days", "5 days" in card)
check("has Profile Relaxed pace", "Relaxed" in card)
check("has Suggested Places", "Suggested Places" in card)
check("has Why This Suits You reasoning", "Why This Suits You" in card)
check("explains family & relaxed in reasoning", "family" in card.lower() and "relaxed" in card.lower())

# --- TEST 10: Recommendation with partial information ---
print("\nTEST 10: Recommendation with partial information")
partial_req = {"pax": 2, "duration_days": 3}
rec_partial = recommendation_agent.generate_recommendation(partial_req)
card_p = rec_partial.get("formatted_card") or ""
check("generates card with partial info", bool(card_p))
check("defaults duration to 3 days", "3 days" in card_p)
check("suggests places", "Suggested Places" in card_p)

# --- TEST 11: Changing one preference does NOT erase other fields ---
print("\nTEST 11: Changing one preference does NOT erase other fields")
base = {
    "origin": "Mumbai",
    "pax": 3,
    "duration_days": 6,
    "category": "VIP Darshan",
    "mode": "flight",
    "group_type": "family",
    "travel_style": "balanced",
}
updated = legacy_agent.merge_requests(base, {}, text="Make it budget friendly")
check("origin preserved=Mumbai", updated.get("origin") == "Mumbai")
check("pax preserved=3", updated.get("pax") == 3)
check("duration preserved=6", updated.get("duration_days") == 6)
check("category preserved=VIP Darshan", updated.get("category") == "VIP Darshan")
check("budget_preference set=budget", updated.get("budget_preference") == "budget")

# --- TEST 12: Tourism queries still work ---
print("\nTEST 12: Tourism queries still work")
res_tour = coordinator.route_message("Tell me about Bhairavnath.")
check("intent is TOURISM", res_tour.get("intent") == "TOURISM")
check("reply mentions Bhairavnath", "Bhairavnath" in (res_tour.get("reply") or ""))

# --- TEST 13: Existing transport tests still work ---
print("\nTEST 13: Existing transport search works")
res_trip = coordinator.route_message("2 people from Delhi for 4 days by train")
check("intent is TRIP_PLANNING", res_trip.get("intent") == "TRIP_PLANNING")
check("request pax=2", res_trip.get("request", {}).get("pax") == 2)
check("request origin=Delhi", res_trip.get("request", {}).get("origin") == "Delhi")

print("\n" + "=" * 70)
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
