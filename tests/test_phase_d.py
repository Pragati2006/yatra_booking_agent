"""
test_phase_d.py
Phase D unit test suite — "Edit My Trip" functionality, partial updates, and correction detection.
Run with: python test_phase_d.py
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents import coordinator, conversation_agent, recommendation_agent
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
print("PHASE D — EDIT MY TRIP & CORRECTION TEST SUITE")
print("=" * 70)

# --- Base Setup for Multi-turn Edits ---
base_req = {
    "origin": "Delhi",
    "pax": 4,
    "duration_days": 5,
    "mode": "flight",
    "category": "Normal Darshan",
    "sightseeing": False,
    "group_type": "family",
    "travel_style": "balanced",
    "trip_focus": "devotional",
    "budget_preference": "comfortable",
}

# --- TEST 1: Duration update 5 -> 6 days ---
print("\nTEST 1: Duration update 5 -> 6 days")
res1 = coordinator.route_message("Make it 6 days.", current_request=base_req)
req1 = res1.get("request") or {}
check("duration changed to 6", req1.get("duration_days") == 6, repr(req1.get("duration_days")))
check("origin preserved Delhi", req1.get("origin") == "Delhi")
check("pax preserved 4", req1.get("pax") == 4)
check("diff captured duration", "duration_days" in res1.get("diff", {}))

# --- TEST 2: Traveller update 4 -> 5 people ---
print("\nTEST 2: Traveller update 4 -> 5 people")
res2 = coordinator.route_message("Actually we are 5 people.", current_request=base_req)
req2 = res2.get("request") or {}
check("pax changed to 5", req2.get("pax") == 5, repr(req2.get("pax")))
check("duration preserved 5", req2.get("duration_days") == 5)

# --- TEST 3: Origin correction Delhi -> Jammu ---
print("\nTEST 3: Origin correction Delhi -> Jammu")
res3 = coordinator.route_message("Change my starting city to Jammu.", current_request=base_req)
req3 = res3.get("request") or {}
check("origin changed to Jammu", req3.get("origin") == "Jammu", repr(req3.get("origin")))
check("pax preserved 4", req3.get("pax") == 4)

# --- TEST 4: Travel mode flight -> train ---
print("\nTEST 4: Travel mode flight -> train")
res4 = coordinator.route_message("Change to train.", current_request=base_req)
req4 = res4.get("request") or {}
check("mode changed to train", req4.get("mode") == "train", repr(req4.get("mode")))
check("origin preserved Delhi", req4.get("origin") == "Delhi")

# --- TEST 5: Darshan normal -> VIP ---
print("\nTEST 5: Darshan normal -> VIP")
res5 = coordinator.route_message("We want VIP darshan instead.", current_request=base_req)
req5 = res5.get("request") or {}
check("category changed to VIP Darshan", req5.get("category") == "VIP Darshan", repr(req5.get("category")))

# --- TEST 6: Sightseeing false -> true ---
print("\nTEST 6: Sightseeing false -> true")
res6 = coordinator.route_message("Add sightseeing.", current_request=base_req)
req6 = res6.get("request") or {}
check("sightseeing changed to True", req6.get("sightseeing") is True, repr(req6.get("sightseeing")))

# --- TEST 7: Travel style balanced -> relaxed ---
print("\nTEST 7: Travel style balanced -> relaxed")
res7 = coordinator.route_message("Make it relaxed.", current_request=base_req)
req7 = res7.get("request") or {}
check("travel_style changed to relaxed", req7.get("travel_style") == "relaxed", repr(req7.get("travel_style")))

# --- TEST 8: Trip focus mixed -> devotional ---
print("\nTEST 8: Trip focus mixed -> devotional")
mixed_base = dict(base_req, trip_focus="mixed", sightseeing=True)
res8 = coordinator.route_message("Make it more devotional.", current_request=mixed_base)
req8 = res8.get("request") or {}
check("trip_focus changed to devotional", req8.get("trip_focus") == "devotional", repr(req8.get("trip_focus")))

# --- TEST 9: Budget comfortable -> budget ---
print("\nTEST 9: Budget comfortable -> budget")
res9 = coordinator.route_message("Keep it budget friendly.", current_request=base_req)
req9 = res9.get("request") or {}
check("budget_preference changed to budget", req9.get("budget_preference") == "budget", repr(req9.get("budget_preference")))

# --- TEST 10: Multi-field preservation ---
print("\nTEST 10: Multi-field preservation while updating duration")
res10 = coordinator.route_message("Change to 7 days.", current_request=base_req)
req10 = res10.get("request") or {}
check("duration=7", req10.get("duration_days") == 7)
check("origin=Delhi preserved", req10.get("origin") == "Delhi")
check("pax=4 preserved", req10.get("pax") == 4)
check("mode=flight preserved", req10.get("mode") == "flight")
check("group_type=family preserved", req10.get("group_type") == "family")

# --- TEST 11: Correction keyword phrasing ("Actually, 6 days.") ---
print("\nTEST 11: Correction phrasing 'Actually, 6 days.'")
res11 = coordinator.route_message("Actually, 6 days.", current_request=base_req)
req11 = res11.get("request") or {}
check("duration updated to 6", req11.get("duration_days") == 6)

# --- TEST 12: Latest correction wins (Delhi -> Jammu -> Delhi) ---
print("\nTEST 12: Latest correction wins (Delhi -> Jammu -> Delhi)")
turn1 = coordinator.route_message("Change my starting city to Jammu.", current_request=base_req)
req_t1 = turn1.get("request") or {}
check("turn 1 origin is Jammu", req_t1.get("origin") == "Jammu")

turn2 = coordinator.route_message("Actually I'm travelling from Delhi.", current_request=req_t1)
req_t2 = turn2.get("request") or {}
check("turn 2 origin is back to Delhi", req_t2.get("origin") == "Delhi")

# --- TEST 13: Ambiguous update ("Change that.") asks for clarification ---
print("\nTEST 13: Ambiguous update ('Change that.')")
res13 = coordinator.route_message("Change that.", current_request=base_req)
reply13 = res13.get("reply") or ""
check("reply asks clarification", "What would you like to change" in reply13 or "clarification" in reply13.lower())
check("request state unchanged", res13.get("request", {}).get("duration_days") == 5)

# --- TEST 14: Tourism isolation (tourism query does not modify trip_request) ---
print("\nTEST 14: Tourism isolation")
res14 = coordinator.route_message("Tell me about Bhairavnath.", current_request=base_req)
check("intent is TOURISM", res14.get("intent") == "TOURISM")
check("request returned is None (caller keeps old state)", res14.get("request") is None)

# --- TEST 15: Tourism follow-up remains tourism ---
print("\nTEST 15: Tourism follow-up remains tourism")
t_tour1 = coordinator.route_message("Tell me about Bhairavnath.")
lp = t_tour1.get("last_tourism_place")
t_tour2 = coordinator.route_message("How far is it?", last_tourism_place=lp, current_request=base_req)
check("intent is TOURISM", t_tour2.get("intent") == "TOURISM")
check("request returned is None", t_tour2.get("request") is None)

# --- TEST 16: Recommendation refresh on travel_style change ---
print("\nTEST 16: Recommendation refresh on travel_style change")
res16 = coordinator.route_message("Make it relaxed.", current_request=base_req)
rec16 = res16.get("recommendation") or {}
card16 = rec16.get("formatted_card") or ""
check("recommendation generated", bool(card16))
check("card reflects Relaxed pace", "Relaxed" in card16)

print("\n" + "=" * 70)
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
