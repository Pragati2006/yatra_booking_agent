"""
agent.py
The 'agent' brain. Two modes:

1. RULE_BASED (default, no API key needed): extracts trip details with
   simple parsing, queries the mock database across all transport
   modes (flight/train/bus), ranks combinations, and proposes options.

2. LLM_POWERED (auto-enabled if ANTHROPIC_API_KEY is set): uses Claude
   to parse the free-text request into the same structure, then reuses
   the identical deterministic ranking/booking logic below.

Both modes produce the same output shape so the Streamlit UI doesn't
need to know which one is active.
"""

import os
import re
from datetime import date, datetime, timedelta

import db

ORIGIN_CITIES = ["delhi", "mumbai", "bangalore", "bengaluru", "chennai", "kolkata", "ahmedabad"]
CATEGORY_KEYWORDS = {
    "helicopter": "Helicopter Darshan",
    "heli": "Helicopter Darshan",
    "vip": "VIP Darshan",
    "normal": "Normal Darshan",
}
MODE_KEYWORDS = {
    "train": "train", "rail": "train", "railway": "train",
    "bus": "bus", "flight": "flight", "fly": "flight", "flying": "flight", "plane": "flight", "air": "flight",
}

MAX_OPTIONS = 3  # how many ranked combinations to show for review

# Real-world buffers, used so a combination is never proposed that would
# require a pilgrim to be in two places at once (e.g. landing at 6 AM and
# having a darshan slot at 6 AM the same morning).
#  - Flights land at Jammu Airport, not Katra - reaching Katra needs the
#    Jammu-Katra taxi leg (~1.5-2 hrs; see explore_data.py's researched
#    fares). Trains (into Katra's own SVDK station) and buses (direct to
#    Katra) don't need this extra leg.
#  - From Katra, Normal/VIP Darshan requires the ~12-13 km trek, commonly
#    5-9 hours one-way for an average pilgrim - but that's pure walking
#    time. A realistic buffer also needs to account for arrival fatigue,
#    food/rest breaks, and queueing at Bhawan, so this is set toward the
#    higher end (10h) rather than the optimistic low end, to avoid
#    proposing combinations that are only technically possible on paper.
#    Helicopter Darshan cuts the trek to a short flight plus walk, but
#    still needs check-in, security, and queueing time.
JAMMU_TO_KATRA_BUFFER_HOURS = 2
DARSHAN_PREP_BUFFER_HOURS = {
    "Helicopter Darshan": 3,
    "VIP Darshan": 10,
    "Normal Darshan": 10,
}


def _use_llm():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _extract_pax(text):
    m = re.search(r"(\d+)\s*(people|pax|person|persons|members|pilgrims)?", text.lower())
    if m:
        return max(1, int(m.group(1)))
    return 1


def _extract_origin(text):
    t = text.lower()
    for city in ORIGIN_CITIES:
        if city in t:
            return "Bangalore" if city == "bengaluru" else city.capitalize()
    return None


def _extract_category(text):
    t = text.lower()
    for kw, cat in CATEGORY_KEYWORDS.items():
        if kw in t:
            return cat
    return None


def _extract_mode(text):
    t = text.lower()
    for kw, mode in MODE_KEYWORDS.items():
        if kw in t:
            return mode
    return None  # no preference -> show a diversified mix


def _extract_date_range(text):
    t = text.lower()
    today = date.today()
    if "next week" in t:
        start = today + timedelta(days=7)
        end = start + timedelta(days=6)
    elif "this week" in t:
        start = today
        end = today + timedelta(days=6)
    elif "next month" in t:
        start = today + timedelta(days=30)
        end = start + timedelta(days=6)
    else:
        start = today
        end = today + timedelta(days=14)
    return start.isoformat(), end.isoformat()


def parse_request(text):
    """Rule-based extraction of a structured trip request from free text."""
    return {
        "pax": _extract_pax(text),
        "origin": _extract_origin(text),
        "category": _extract_category(text),
        "mode": _extract_mode(text),
        "start_date": _extract_date_range(text)[0],
        "end_date": _extract_date_range(text)[1],
    }


def _search_transport(request):
    """Searches whichever modes are relevant and returns one combined list."""
    origin, start, end, pax = request["origin"], request["start_date"], request["end_date"], request["pax"]
    mode = request.get("mode")

    searchers = {
        "flight": db.search_flights,
        "train": db.search_trains,
        "bus": db.search_buses,
    }
    modes_to_search = [mode] if mode in searchers else list(searchers.keys())

    results = []
    for m in modes_to_search:
        results.extend(searchers[m](origin, start, end, min_seats=pax))
    return results


def _transport_arrival_datetime(tr):
    """Real arrival moment: departure + travel duration, plus a Jammu-Katra
    taxi buffer for flights (trains/buses already terminate in Katra)."""
    dep = datetime.strptime(f"{tr['travel_date']} {tr['departure_time']}", "%Y-%m-%d %H:%M")
    duration = tr.get("duration_mins")
    arrival = dep + timedelta(minutes=int(duration)) if duration else dep
    if tr.get("mode") == "flight":
        arrival += timedelta(hours=JAMMU_TO_KATRA_BUFFER_HOURS)
    return arrival


def _slot_datetime(s):
    return datetime.strptime(f"{s['slot_date']} {s['slot_time']}", "%Y-%m-%d %H:%M")


def build_plan(request):
    """
    Core planning logic shared by both modes: query slots + transport
    across all relevant modes, rank every valid combination, and
    return the top options so the user can compare and pick.
    """
    missing = []
    if not request.get("origin"):
        missing.append("origin city")

    if missing:
        return {
            "status": "NEEDS_INFO",
            "missing": missing,
            "message": f"I need your {', '.join(missing)} to search travel options. Which city will you travel from?",
        }

    slots = db.search_yatra_slots(
        request["start_date"], request["end_date"],
        category=request.get("category"), min_seats=request["pax"]
    )
    transport = _search_transport(request)

    if not slots or not transport:
        mode_note = f" by {request['mode']}" if request.get("mode") else ""
        return {
            "status": "NO_AVAILABILITY",
            "message": f"I couldn't find matching yatra slots and travel options{mode_note} for those dates. "
                       "Want me to widen the date range or try a different mode of transport?",
            "slots_found": len(slots),
            "flights_found": len(transport),
        }

    # Rank every valid combination by cheapest total, but only combinations
    # where the pilgrim could realistically reach the darshan slot given
    # real transport arrival time + Jammu-Katra travel + trek/heli buffers
    # (see DARSHAN_PREP_BUFFER_HOURS above) - never same-moment matches.
    combos = []
    for tr in transport[:30]:
        arrival = _transport_arrival_datetime(tr)
        for s in slots[:15]:
            buffer_hours = DARSHAN_PREP_BUFFER_HOURS.get(s["category"], 8)
            earliest_possible_darshan = arrival + timedelta(hours=buffer_hours)
            if _slot_datetime(s) >= earliest_possible_darshan:
                total = (tr["price"] + s["price"]) * request["pax"]
                combos.append({"flight": tr, "slot": s, "total_price": total})

    if not combos:
        return {
            "status": "NO_COMBINATION",
            "message": "Found travel options and yatra slots separately, but no valid combination "
                       "(travel would arrive after the yatra slot). Try a wider date range.",
        }

    combos.sort(key=lambda c: c["total_price"])

    options = []
    seen = set()

    if not request.get("mode"):
        # No preference stated: show one option per mode first, so the
        # person can actually compare flight vs train vs bus, rather
        # than three near-identical cheap-train results dominating the
        # list just because trains are usually cheapest.
        for m in ("flight", "train", "bus"):
            for c in combos:
                if c["flight"]["mode"] == m:
                    key = (c["flight"]["id"], c["flight"]["mode"], c["slot"]["category"])
                    if key not in seen:
                        seen.add(key)
                        options.append(c)
                        break

    for c in combos:
        if len(options) >= MAX_OPTIONS:
            break
        key = (c["flight"]["id"], c["flight"]["mode"], c["slot"]["category"])
        if key in seen:
            continue
        seen.add(key)
        options.append(c)

    options.sort(key=lambda c: c["total_price"])
    options = options[:MAX_OPTIONS]

    return {
        "status": "PLAN_READY",
        "pax": request["pax"],
        "options": options,
        "alt_slots_count": len(slots),
        "alt_flights_count": len(transport),
    }


def confirm_booking(option, pax, user_name, hotel=None, hotel_nights=0, sightseeing_places=None):
    """Executes the mock booking for a chosen option from PLAN_READY['options'],
    optionally including a hotel stay and a list of sightseeing places
    (hotel cost is added to the total; sightseeing places are informational,
    not priced, since they aren't bookable through this app)."""
    total = option["total_price"]
    if hotel:
        total += hotel.get("price_per_night", 0) * hotel_nights

    booking_id = db.create_booking(
        user_name=user_name,
        pax_count=pax,
        yatra_slot=option["slot"],
        transport=option["flight"],
        total_price=total,
        hotel=hotel,
        hotel_nights=hotel_nights,
        sightseeing_places=sightseeing_places,
    )
    return booking_id


# ---------------------------------------------------------------------
# Optional: LLM-powered mode. Only activates if ANTHROPIC_API_KEY is set.
# ---------------------------------------------------------------------

def parse_request_llm(text, api_key):
    import json
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    today = date.today().isoformat()

    system = f"""Extract yatra trip details from the user's message as JSON only.
Today's date is {today}. Fields: pax (integer, default 1), origin (city name or null),
category (one of "Normal Darshan","VIP Darshan","Helicopter Darshan", or null),
mode (one of "flight","train","bus", or null if no preference stated),
start_date (YYYY-MM-DD), end_date (YYYY-MM-DD). If no dates mentioned, use the next 14 days.
Respond with ONLY the JSON object, no other text."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": text}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    raw = raw.strip().strip("`").replace("json", "", 1) if raw.strip().startswith("```") else raw
    return json.loads(raw)


def process_message(text, api_key=None):
    """Single entry point the Streamlit UI calls. Returns a structured plan dict."""
    if api_key:
        try:
            request = parse_request_llm(text, api_key)
        except Exception:
            request = parse_request(text)
    else:
        request = parse_request(text)

    plan = build_plan(request)
    plan["_request"] = request
    return plan
