"""
test_phase_e.py
Phase E Unit Test Suite — Intelligent Day-by-Day Itinerary Editing & Contextual Parsing.
Run with: python test_phase_e.py
"""
import copy
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents import coordinator, itinerary_agent
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
print("PHASE E — INTELLIGENT DAY-BY-DAY ITINERARY EDITING TEST SUITE")
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

# --- TEST 1: Show itinerary ---
print("\nTEST 1: Show full itinerary")
res1 = coordinator.route_message("Show my itinerary.", current_request=base_req)
check("intent is ITINERARY", res1.get("intent") == "ITINERARY")
itin1 = res1.get("itinerary") or []
check("itinerary has 5 days", len(itin1) == 5, f"len={len(itin1)}")
check("reply contains Day-Wise Itinerary header", "Day-Wise Itinerary" in res1.get("reply", ""))

# --- TEST 2: Show specific day ---
print("\nTEST 2: Show specific day (Day 2)")
res2 = coordinator.route_message("What am I doing on Day 2?", current_request=base_req, current_itinerary=itin1)
check("intent is ITINERARY", res2.get("intent") == "ITINERARY")
check("reply specifies Day 2", "Day 2" in res2.get("reply", ""))
ctx2 = res2.get("last_itinerary_context") or {}
check("context recorded for Day 2", ctx2.get("day") == 2)

# --- TEST 3: Add activity ---
print("\nTEST 3: Add activity (Add Bhairavnath on Day 2)")
res3 = coordinator.route_message("Add Bhairavnath on Day 2.", current_request=base_req, current_itinerary=itin1)
itin3 = res3.get("itinerary") or []
day2_acts3 = itin3[1]["activities"]
check("Bhairavnath added to Day 2", any("Bhairavnath" in a for a in day2_acts3))
check("reply confirms addition", "Added to Day 2" in res3.get("reply", "") or "Bhairavnath" in res3.get("reply", ""))

# --- TEST 4: Remove activity ---
print("\nTEST 4: Remove activity (Remove Patnitop from Day 3)")
res4 = coordinator.route_message("Remove Patnitop from Day 3.", current_request=base_req, current_itinerary=itin3)
itin4 = res4.get("itinerary") or []
day3_acts4 = itin4[2]["activities"]
check("Patnitop removed from Day 3", not any("Patnitop" in a for a in day3_acts4))

# --- TEST 5: Move activity ---
print("\nTEST 5: Move activity (Move Patnitop to Day 3)")
# First add Patnitop back to Day 2
itin_with_p = itinerary_agent.apply_itinerary_edit(itin4, {"action": "ADD", "place": "Patnitop", "day": 2})[0]
res5 = coordinator.route_message("Move Patnitop to Day 3.", current_request=base_req, current_itinerary=itin_with_p)
itin5 = res5.get("itinerary") or []
check("Patnitop removed from Day 2", not any("Patnitop" in a for a in itin5[1]["activities"]))
check("Patnitop added to Day 3", any("Patnitop" in a for a in itin5[2]["activities"]))

# --- TEST 6: Replace activity ---
print("\nTEST 6: Replace activity (Replace Patnitop with Mansar Lake)")
res6 = coordinator.route_message("Replace Patnitop with Mansar Lake.", current_request=base_req, current_itinerary=itin5)
itin6 = res6.get("itinerary") or []
check("Patnitop removed", not any("Patnitop" in a for a in itin6[2]["activities"]))
check("Mansar Lake added to Day 3", any("Mansar Lake" in a for a in itin6[2]["activities"]))

# --- TEST 7: Rest day ---
print("\nTEST 7: Add a rest day (Add a rest day on Day 3)")
res7 = coordinator.route_message("Add a rest day on Day 3.", current_request=base_req, current_itinerary=itin1)
itin7 = res7.get("itinerary") or []
check("Day 3 title marked Rest", "Rest" in itin7[2]["title"])
check("Day 3 activities contain rest", any("Rest" in a for a in itin7[2]["activities"]))

# --- TEST 8: Modify day pace ---
print("\nTEST 8: Modify day pace (Make Day 2 relaxed)")
res8 = coordinator.route_message("Make Day 2 relaxed.", current_request=base_req, current_itinerary=itin1)
itin8 = res8.get("itinerary") or []
check("Day 2 title updated with pace", "Relaxed" in itin8[1]["title"])

# --- TEST 9: Invalid day validation ---
print("\nTEST 9: Invalid day validation (Show Day 8 for 5-day trip)")
res9 = coordinator.route_message("Show me Day 8.", current_request=base_req, current_itinerary=itin1)
check("rejects invalid day 8", "does not exist" in res9.get("reply", "").lower() or "5-day" in res9.get("reply", "").lower())

# --- TEST 10: Unknown place validation ---
print("\nTEST 10: Unknown place validation (Add Eiffel Tower to Day 2)")
res10 = coordinator.route_message("Add Eiffel Tower to Day 2.", current_request=base_req, current_itinerary=itin1)
check("rejects ungrounded place", "couldn't find" in res10.get("reply", "").lower() or "catalogue" in res10.get("reply", "").lower())

# --- TEST 11: Ambiguous edit without context ---
print("\nTEST 11: Ambiguous edit ('Move that to Day 3' without context)")
res11 = coordinator.route_message("Move that to Day 3.", current_request=base_req, current_itinerary=itin1, last_itinerary_context=None)
check("asks clarification for ambiguous move", "Which activity" in res11.get("reply", ""))

# --- TEST 12: Contextual follow-up ---
print("\nTEST 12: Contextual follow-up ('Show Day 3' -> 'Move that to Day 4')")
t_step1 = coordinator.route_message("What am I doing on Day 3?", current_request=base_req, current_itinerary=itin1)
ctx_step1 = t_step1.get("last_itinerary_context")

t_step2 = coordinator.route_message("Move that to Day 4.", current_request=base_req, current_itinerary=itin1, last_itinerary_context=ctx_step1)
itin12 = t_step2.get("itinerary") or []
check("uses context to move Day 3 activity to Day 4", any("Patnitop" in a for a in itin12[3]["activities"]))

# --- TEST 13: Duplicate prevention ---
print("\nTEST 13: Duplicate prevention")
itin13_1 = itinerary_agent.apply_itinerary_edit(itin1, {"action": "ADD", "place": "Patnitop", "day": 2})[0]
itin13_2 = itinerary_agent.apply_itinerary_edit(itin13_1, {"action": "ADD", "place": "Patnitop", "day": 2})[0]
pat_count = sum(1 for a in itin13_2[1]["activities"] if "Patnitop" in a)
check("activity not duplicated on same day", pat_count == 1)

# --- TEST 14: State preservation ---
print("\nTEST 14: State preservation of unedited days")
res14 = coordinator.route_message("Add Mansar Lake to Day 4.", current_request=base_req, current_itinerary=itin1)
itin14 = res14.get("itinerary") or []
check("Day 1 untouched", itin14[0] == itin1[0])
check("Day 2 untouched", itin14[1] == itin1[1])
check("Day 3 untouched", itin14[2] == itin1[2])

# --- TEST 15: Phase D interaction & duration sync ---
print("\nTEST 15: Phase D interaction & duration sync")
res15_trip = coordinator.route_message("Make the trip 7 days.", current_request=base_req, current_itinerary=itin1)
req15 = res15_trip.get("request") or {}
itin15 = res15_trip.get("itinerary") or []
check("Phase D updated duration to 7", req15.get("duration_days") == 7)
check("Itinerary synced length to 7 days", len(itin15) == 7)

# --- TEST 16: Tourism isolation ---
print("\nTEST 16: Tourism isolation")
res16_tour = coordinator.route_message("Tell me about Bhairavnath.", current_request=base_req, current_itinerary=itin1)
check("intent is TOURISM", res16_tour.get("intent") == "TOURISM")
check("itinerary returned is None (caller keeps old state)", res16_tour.get("itinerary") is None)

# --- TEST 17: Sequential multi-edits ---
print("\nTEST 17: Sequential multi-edits persistence")
seq_itin = copy.deepcopy(itin1)
# 1. Move Patnitop to Day 4
seq_res1 = coordinator.route_message("Move Patnitop to Day 4.", current_request=base_req, current_itinerary=seq_itin)
seq_itin = seq_res1["itinerary"]

# 2. Add Bhairavnath to Day 2
seq_res2 = coordinator.route_message("Add Bhairavnath on Day 2.", current_request=base_req, current_itinerary=seq_itin)
seq_itin = seq_res2["itinerary"]

# 3. Show Day 2
seq_res3 = coordinator.route_message("Show Day 2.", current_request=base_req, current_itinerary=seq_itin)
reply_seq3 = seq_res3.get("reply", "")

check("sequential edit 1 persisted (Patnitop in Day 4)", any("Patnitop" in a for a in seq_itin[3]["activities"]))
check("sequential edit 2 persisted (Bhairavnath in Day 2)", any("Bhairavnath" in a for a in seq_itin[1]["activities"]))
check("show Day 2 displays Bhairavnath", "Bhairavnath" in reply_seq3)

print("\n" + "=" * 70)
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)
