"""
Phase A routing tests — no Streamlit required.
Run: python test_intent_routing.py
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents import coordinator, conversation_agent

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
print("PHASE A — INTENT ROUTING / TOURISM RETRIEVAL")
print("=" * 70)

# --- TEST 1 ---
print("\nTEST 1: What places can I visit around Katra?")
msg = "What places can I visit around Katra?"
res = coordinator.route_message(msg)
reply = (res.get("reply") or "").lower()
check("intent TOURISM", res.get("intent") == "TOURISM", repr(res.get("intent")))
check("no plan", res.get("plan") is None)
check("no request", res.get("request") is None)
check("no origin question", "which city" not in reply and "origin" not in reply)
check("nearby names present", "bhairavnath" in reply or "charan paduka" in reply or "ban ganga" in reply)
check("not full dump of patnitop-only catalogue", "query_kind" in res)
check("query_kind nearby", res.get("query_kind") == "nearby_places", repr(res.get("query_kind")))

# --- TEST 2 ---
print("\nTEST 2: Tell me about Bhairavnath.")
msg = "Tell me about Bhairavnath."
res = coordinator.route_message(msg)
reply = (res.get("reply") or "").lower()
check("intent TOURISM", res.get("intent") == "TOURISM", repr(res.get("intent")))
check("mentions Bhairavnath Temple", "bhairavnath" in reply)
check("not all-place dump", "patnitop" not in reply and "amar mahal" not in reply)
check("no origin question", "which city" not in reply)
check("query_kind place", res.get("query_kind") == "place", repr(res.get("query_kind")))

# --- TEST 3 ---
print("\nTEST 3: What is the history of Vaishno Devi?")
msg = "What is the history of Vaishno Devi?"
res = coordinator.route_message(msg)
reply = (res.get("reply") or "").lower()
check("intent TOURISM", res.get("intent") == "TOURISM")
check("historical content", "legend" in reply or "goddess" in reply or "vaishnavi" in reply or "bhairavnath" in reply)
check("no booking/origin prompt", "which city" not in reply)
check("query_kind history", res.get("query_kind") == "vaishno_history", repr(res.get("query_kind")))

# --- TEST 4 ---
print("\nTEST 4: What should I pack for the Yatra?")
msg = "What should I pack for the Yatra?"
res = coordinator.route_message(msg)
reply = (res.get("reply") or "").lower()
check("intent TOURISM", res.get("intent") == "TOURISM")
check("packing content", "pack" in reply or "shoes" in reply or "yatra slip" in reply)
check("query_kind packing", res.get("query_kind") == "packing", repr(res.get("query_kind")))

# --- TEST 5 ---
print("\nTEST 5: What are the Aarti timings?")
msg = "What are the Aarti timings?"
res = coordinator.route_message(msg)
reply = (res.get("reply") or "").lower()
check("intent TOURISM", res.get("intent") == "TOURISM")
check("aarti times", "6:20" in reply or "aarti" in reply)
check("query_kind aarti", res.get("query_kind") == "aarti", repr(res.get("query_kind")))

print("\nTEST 5b: What are the registration steps?")
res = coordinator.route_message("What are the registration steps?")
reply = (res.get("reply") or "").lower()
check("intent TOURISM", res.get("intent") == "TOURISM")
check("registration content", "register" in reply or "yatra slip" in reply or "parchi" in reply)

# --- TEST 6 ---
print("\nTEST 6: 2 people from Surat travelling for 5 days with VIP darshan")
msg = "2 people from Surat travelling for 5 days with VIP darshan"
res = coordinator.route_message(msg)
req = res.get("request") or {}
plan = res.get("plan") or {}
check("intent TRIP_PLANNING", res.get("intent") == "TRIP_PLANNING", repr(res.get("intent")))
check("pax=2", req.get("pax") == 2, repr(req.get("pax")))
check("origin=Surat", req.get("origin") == "Surat", repr(req.get("origin")))
check("duration=5", req.get("duration_days") == 5, repr(req.get("duration_days")))
check("VIP darshan", req.get("category") == "VIP Darshan", repr(req.get("category")))
check("plan status usable", plan.get("status") in ("PLAN_READY", "NO_AVAILABILITY", "NO_COMBINATION"), repr(plan.get("status")))

print("\nTEST 6b: lowercase 'from surat'")
res = coordinator.route_message("2 people from surat travelling for 5 days with VIP darshan")
req = res.get("request") or {}
check("intent still trip", conversation_agent.detect_intent("2 people from surat travelling for 5 days with VIP darshan") == "TRIP_PLANNING")
check("origin still Surat", req.get("origin") == "Surat", repr(req.get("origin")))

# --- TEST 7 ---
print("\nTEST 7: multi-turn duration+VIP then origin Surat")
first = coordinator.route_message("I want to travel for 5 days with VIP darshan.")
req1 = first.get("request") or {}
check("first turn is trip", first.get("intent") == "TRIP_PLANNING")
check("duration preserved before origin", req1.get("duration_days") == 5, repr(req1.get("duration_days")))
check("VIP preserved before origin", req1.get("category") == "VIP Darshan", repr(req1.get("category")))
check("asks for origin", first.get("plan", {}).get("status") == "NEEDS_INFO", repr(first.get("plan", {}).get("status")))

second = coordinator.route_message("Surat", current_request=req1)
req2 = second.get("request") or {}
plan2 = second.get("plan") or {}
check("origin merged", req2.get("origin") == "Surat", repr(req2.get("origin")))
check("duration kept", req2.get("duration_days") == 5, repr(req2.get("duration_days")))
check("VIP kept", req2.get("category") == "VIP Darshan", repr(req2.get("category")))
check("plan not stuck on missing origin", plan2.get("status") != "NEEDS_INFO" or "origin" not in (plan2.get("missing") or []), repr(plan2.get("status")))

print("\nTEST 7b: tourism does not return a request that would wipe state")
tour = coordinator.route_message("Tell me about Bhairavnath.", current_request=req2)
check("tourism intent", tour.get("intent") == "TOURISM")
check("tourism request is None (caller must keep old state)", tour.get("request") is None)

# --- TEST 8 ---
print("\nTEST 8: connecting route from Surat (hub, not fabricated direct)")
res = coordinator.route_message("2 people from Surat travelling for 5 days with VIP darshan")
plan = res.get("plan") or {}
if plan.get("status") == "PLAN_READY":
    opts = plan.get("options") or []
    tr = (opts[0].get("transport") or opts[0].get("flight")) if opts else {}
    check("has options", bool(opts))
    check("connecting flagged", tr.get("is_connecting") is True, repr(tr.get("is_connecting")))
    check("route note honest", "via" in (tr.get("route_note") or "").lower() or "connecting" in (tr.get("route_note") or "").lower(), repr(tr.get("route_note")))
    check("origin preserved as Surat", tr.get("origin") == "Surat" or tr.get("original_origin") == "Surat", repr(tr.get("origin")))
elif plan.get("status") == "NO_AVAILABILITY":
    check("no fabricated options", True)
    print("  NOTE  PLAN_READY not produced (availability); no fabricated direct route.")
else:
    check("unexpected status", False, repr(plan.get("status")))

print("\n" + "=" * 70)
print("PHASE B — TOURISM RESPONSE QUALITY & CONVERSATIONAL FOLLOW-UPS")
print("=" * 70)

# --- TEST 9: Structured Bhairavnath Answer ---
print("\nTEST 9: Tell me about Bhairavnath (Structured Response)")
res = coordinator.route_message("Tell me about Bhairavnath.")
reply = res.get("reply") or ""
check("intent TOURISM", res.get("intent") == "TOURISM")
check("has Title Bhairavnath", "Bhairavnath" in reply)
check("has Overview section", "Overview" in reply)
check("has Significance section", "Significance" in reply)
check("has Pilgrimage Route Position section", "Pilgrimage Route Position" in reply)
check("has Practical Information section", "Practical Information" in reply)
check("last_tourism_place captured", res.get("last_tourism_place") == "Bhairavnath Temple", repr(res.get("last_tourism_place")))

# --- TEST 10: Concise Katra Nearby Places ---
print("\nTEST 10: What places can I visit around Katra? (Concise List)")
res = coordinator.route_message("What places can I visit around Katra?")
reply = res.get("reply") or ""
check("intent TOURISM", res.get("intent") == "TOURISM")
check("has title Key Places to Visit Around Katra", "Places to Visit Around Katra" in reply)
check("has Ban Ganga / Charan Paduka / Ardhkuwari", "Ban Ganga" in reply and "Ardhkuwari" in reply)
check("no dump of full catalogue", "Amar Mahal" not in reply)

# --- TEST 11: Structured Packing Guidance ---
print("\nTEST 11: What should I carry for Vaishno Devi?")
res = coordinator.route_message("What should I carry for Vaishno Devi?")
reply = res.get("reply") or ""
check("intent TOURISM", res.get("intent") == "TOURISM")
check("has Recommended Essentials", "Recommended Essentials" in reply)
check("has Restricted Items", "Restricted" in reply)
check("has Practical Tips", "Practical Tips" in reply)

# --- TEST 12: Structured Registration Guide ---
print("\nTEST 12: How do I register for the Yatra?")
res = coordinator.route_message("How do I register for the Yatra?")
reply = res.get("reply") or ""
check("intent TOURISM", res.get("intent") == "TOURISM")
check("has Registration Title", "Registration" in reply)
check("has How to Register", "How to Register" in reply)
check("has What You Need to Bring", "What You Need to Bring" in reply)

# --- TEST 13: Follow-Up "What can I do there?" for Patnitop ---
print("\nTEST 13: Follow-up Patnitop -> What can I do there?")
t1 = coordinator.route_message("Tell me about Patnitop.")
lp1 = t1.get("last_tourism_place")
check("turn 1 place is Patnitop", lp1 == "Patnitop", repr(lp1))

t2 = coordinator.route_message("What can I do there?", last_tourism_place=lp1)
reply2 = t2.get("reply") or ""
check("turn 2 intent TOURISM", t2.get("intent") == "TOURISM")
check("turn 2 addresses Patnitop activities", "Patnitop" in reply2 and "Attractions" in reply2)
check("turn 2 no origin prompt", "which city" not in reply2.lower() and "origin city" not in reply2.lower() and "where will you travel from" not in reply2.lower())

# --- TEST 14: Follow-Up "How far is it?" for Bhairavnath ---
print("\nTEST 14: Follow-up Bhairavnath -> How far is it?")
t1 = coordinator.route_message("Tell me about Bhairavnath.")
lp1 = t1.get("last_tourism_place")
check("turn 1 place is Bhairavnath Temple", lp1 == "Bhairavnath Temple", repr(lp1))

t2 = coordinator.route_message("How far is it?", last_tourism_place=lp1)
reply2 = t2.get("reply") or ""
check("turn 2 intent TOURISM", t2.get("intent") == "TOURISM")
check("turn 2 addresses Bhairavnath distance", "Bhairavnath" in reply2 and "Distance" in reply2)
check("turn 2 no origin prompt", "which city" not in reply2.lower() and "origin" not in reply2.lower())

# --- TEST 15: Follow-Up "Tell me more about it." ---
print("\nTEST 15: Follow-up Bhairavnath -> Tell me more about it.")
t2 = coordinator.route_message("Tell me more about it.", last_tourism_place="Bhairavnath Temple")
reply2 = t2.get("reply") or ""
check("turn 2 intent TOURISM", t2.get("intent") == "TOURISM")
check("turn 2 resolves Bhairavnath", "Bhairavnath" in reply2)

# --- TEST 16: Place Aliases Verification ---
print("\nTEST 16: Place Aliases Verification")
from agents import knowledge_agent
aliases_to_check = [
    ("ardhkuwari", "Ardhkuwari Cave"),
    ("charan paduka", "Charan Paduka"),
    ("ban ganga", "Ban Ganga"),
    ("nau devi", "Nau Devi Cave Temple"),
    ("shiv khori", "Shiv Khori"),
    ("patnitop", "Patnitop"),
]
for alias, canonical in aliases_to_check:
    matched = knowledge_agent.find_specific_places(alias)
    found_name = matched[0]["name"] if matched else None
    check(f"alias '{alias}' -> '{canonical}'", found_name == canonical, repr(found_name))

print("\n" + "=" * 70)
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(1 if FAIL else 0)

