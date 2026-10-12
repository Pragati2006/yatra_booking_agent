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

# Regional zone mapping connecting Indian regions/states/cities to supported dataset hubs
REGION_TO_HUB = {
    # Gujarat / West Coast -> Ahmedabad
    "surat": "Ahmedabad", "vadodara": "Ahmedabad", "rajkot": "Ahmedabad", "gujarat": "Ahmedabad",
    # Maharashtra / West -> Mumbai
    "pune": "Mumbai", "nashik": "Mumbai", "nagpur": "Mumbai", "aurangabad": "Mumbai", "maharashtra": "Mumbai",
    # North & Central India -> Delhi
    "jaipur": "Delhi", "jodhpur": "Delhi", "udaipur": "Delhi", "rajasthan": "Delhi",
    "lucknow": "Delhi", "kanpur": "Delhi", "varanasi": "Delhi", "agra": "Delhi", "up": "Delhi", "uttar pradesh": "Delhi",
    "bhopal": "Delhi", "indore": "Delhi", "gwalior": "Delhi", "jabalpur": "Delhi", "mp": "Delhi", "madhya pradesh": "Delhi",
    "chandigarh": "Delhi", "amritsar": "Delhi", "ludhiana": "Delhi", "jalandhar": "Delhi", "punjab": "Delhi", "haryana": "Delhi",
    # South India -> Bangalore or Chennai
    "kochi": "Bangalore", "trivandrum": "Bangalore", "calicut": "Bangalore", "kerala": "Bangalore",
    "hyderabad": "Bangalore", "secunderabad": "Bangalore", "telangana": "Bangalore", "andhra": "Bangalore",
    "coimbatore": "Chennai", "madurai": "Chennai", "tamil nadu": "Chennai",
    # East India -> Kolkata
    "patna": "Kolkata", "ranchi": "Kolkata", "bhubaneswar": "Kolkata", "odisha": "Kolkata", "bihar": "Kolkata",
}

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

JAMMU_TO_KATRA_BUFFER_HOURS = 2
DARSHAN_PREP_BUFFER_HOURS = {
    "Helicopter Darshan": 3,
    "VIP Darshan": 10,
    "Normal Darshan": 10,
}


def _use_llm():
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _extract_pax(text):
    if not text:
        return None
    t = text.lower()
    m = re.search(r"(\d+)\s*(people|pax|person|persons|members|pilgrims|travellers|travelers)\b", t)
    if m:
        return max(1, int(m.group(1)))
    m2 = re.search(r"\b(?:we are|for|group of|total|we are a group of|family of|make that|make it|i meant)\s+(\d+)\b", t)
    if m2:
        num = int(m2.group(1))
        if not re.search(r"\b" + str(num) + r"\s*days?\b", t):
            return max(1, num)
    words_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }
    for word, num in words_to_num.items():
        if re.search(r"\b" + word + r"\s*(people|pax|person|persons|members|pilgrims|travellers|travelers)\b", t):
            return num
    return None


def _extract_origin(text):
    if not text:
        return None
    t = text.strip()
    m = re.search(
        r"\b(?:from|out of|leaving|travelling from|traveling from|departing from|starting from|starting city to|city to|from city|starting city|change my starting city to|change origin to)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
        t,
        re.IGNORECASE,
    )
    stop_words = {
        "the", "a", "an", "my", "our", "here", "there", "home", "katra",
        "next", "this", "that", "it", "them", "these", "those", "last", "for", "with", "by", "in", "during", "and", "to", "or",
        "on", "at", "around",
        "travelling", "traveling", "visiting", "going", "planning", "train", "flight", "bus", "is",
        "city", "starting", "from", "change", "make", "instead", "rather", "want", "prefer", "meant",
        "trip", "yatra", "day", "days", "people", "pax", "person", "relaxed", "devotional", "budget",
        "update", "modify", "edit", "fix", "switch", "keep", "more", "less", "friendly", "comfortable",
        "premium", "luxury", "balanced", "sightseeing", "mixed", "family", "solo", "couple", "friends",
        "group", "pilgrimage", "parents", "fast", "slow", "packed", "peaceful", "actually"
    }
    if m:
        candidate = re.sub(r"[^A-Za-z\s]", "", m.group(1)).strip()
        words = candidate.split()
        clean_words = []
        for w in words:
            if w.lower() in stop_words:
                break
            clean_words.append(w.capitalize())
        if clean_words:
            res = " ".join(clean_words)
            if res.lower() not in ["katra"] and len(res) >= 3:
                return res

    words = [w for w in re.findall(r"\b[A-Za-z]+\b", t) if w.lower() not in stop_words]
    if len(words) == 1 and len(words[0]) >= 3 and words[0].lower() not in ["katra"]:
        return words[0].capitalize()

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
    return None


def _extract_duration(text):
    if not text:
        return None
    m = re.search(r"(\d+)[\s-]*days?", text.lower())
    if m:
        return int(m.group(1))
    return None


def _extract_season(text):
    t = text.lower()
    if "navratri" in t:
        return "Navratri"
    if "diwali" in t:
        return "Diwali"
    return None


def _extract_sightseeing(text):
    t = text.lower()
    if any(kw in t for kw in ["remove sightseeing", "no sightseeing", "without sightseeing", "don't want sightseeing", "dont want sightseeing", "stop sightseeing"]):
        return False
    keywords = ["nearby places", "sightseeing", "visit places", "tourist spots", "places to see", "explore nearby", "add sightseeing", "want sightseeing"]
    if any(kw in t for kw in keywords):
        return True
    return None


def is_ambiguous_change(text: str) -> bool:
    """True if user text asks to change/update something but names no extractable field."""
    if not text:
        return False
    t = re.sub(r"[^\w\s]", "", text.strip().lower()).strip()
    ambiguous_phrases = [
        "change that", "update that", "fix that", "change it", "update my trip",
        "change trip", "modify trip", "edit trip", "change my trip", "make changes",
        "change this", "update this", "edit this"
    ]
    if any(p == t for p in ambiguous_phrases) or t in ("change", "update", "modify", "edit"):
        return True
    return False


def get_changed_fields(old_req, new_req):
    """Computes exact diff between old trip request state and updated state.
    Returns dict: {field_name: {"label": str, "old": val, "new": val}}."""
    if not old_req or not new_req:
        return {}
    diff = {}
    fields = [
        ("duration_days", "Duration", lambda v: f"{v} days" if v else None),
        ("pax", "Travellers", lambda v: f"{v} pilgrim{'s' if v > 1 else ''}" if v else None),
        ("origin", "Starting City", lambda v: v),
        ("mode", "Travel Mode", lambda v: str(v).title() if v else None),
        ("category", "Darshan Category", lambda v: v),
        ("sightseeing", "Sightseeing", lambda v: "Added" if v else "Removed"),
        ("group_type", "Group Type", lambda v: str(v).title() if v else None),
        ("travel_style", "Pacing & Style", lambda v: str(v).title() if v else None),
        ("trip_focus", "Trip Focus", lambda v: str(v).title() if v else None),
        ("budget_preference", "Budget Preference", lambda v: str(v).title() if v else None),
    ]
    for key, label, fmt in fields:
        old_v = old_req.get(key)
        new_v = new_req.get(key)
        if old_v != new_v and new_v is not None and old_v is not None:
            diff[key] = {
                "label": label,
                "old": fmt(old_v) if old_v is not None else "Not set",
                "new": fmt(new_v) if new_v is not None else "Not set",
            }
    return diff


def format_edit_confirmation(diff):
    """Renders a concise, professional confirmation of updated trip fields."""
    if not diff:
        return ""
    lines = ["✏️ **Updated Your Trip:**"]
    for key, info in diff.items():
        label = info["label"]
        old_v = info["old"]
        new_v = info["new"]
        lines.append(f"• **{label}:** {old_v} → {new_v}")
    lines.append("\n*I've kept the rest of your preferences unchanged.*")
    return "\n".join(lines)


def has_explicit_date(text):
    if not text:
        return False
    t = text.lower()
    if any(k in t for k in ["next week", "this week", "next month", "tomorrow"]):
        return True
    if re.search(r"\b(202\d)-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])\b", text):
        return True
    if re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", text, re.IGNORECASE):
        return True
    if re.search(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})\b", text, re.IGNORECASE):
        return True
    if re.search(r"\b([0-2]?[1-9]|3[01])[/-](0?[1-9]|1[0-2])[/-](202\d)\b", text):
        return True
    return False


def _extract_date_range(text):
    if not text:
        today = date.today()
        return today.isoformat(), (today + timedelta(days=13)).isoformat()
    t = text.lower()
    today = date.today()
    dur = _extract_duration(text)

    # 1. ISO format: YYYY-MM-DD
    m_iso = re.search(r"\b(202\d)-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])\b", text)
    if m_iso:
        try:
            start = datetime.strptime(m_iso.group(0), "%Y-%m-%d").date()
            span_days = dur - 1 if dur and dur > 1 else 3
            end = start + timedelta(days=span_days)
            return start.isoformat(), end.isoformat()
        except Exception:
            pass

    # 2. DD Month YYYY (e.g. 17 Oct 2026, 17 October 2026)
    m_dmy = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+(\d{4}))?\b",
        text,
        re.IGNORECASE,
    )
    if m_dmy:
        day_str = m_dmy.group(1)
        month_str = m_dmy.group(2)[:3].capitalize()
        year_str = m_dmy.group(3) or str(today.year)
        try:
            start = datetime.strptime(f"{day_str} {month_str} {year_str}", "%d %b %Y").date()
            span_days = dur - 1 if dur and dur > 1 else 3
            end = start + timedelta(days=span_days)
            return start.isoformat(), end.isoformat()
        except Exception:
            pass

    # 3. Month DD, YYYY (e.g. Oct 17, 2026 or October 17 2026)
    m_mdy = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
        text,
        re.IGNORECASE,
    )
    if m_mdy:
        month_str = m_mdy.group(1)[:3].capitalize()
        day_str = m_mdy.group(2)
        year_str = m_mdy.group(3) or str(today.year)
        try:
            start = datetime.strptime(f"{day_str} {month_str} {year_str}", "%d %b %Y").date()
            span_days = dur - 1 if dur and dur > 1 else 3
            end = start + timedelta(days=span_days)
            return start.isoformat(), end.isoformat()
        except Exception:
            pass

    # 4. DD/MM/YYYY or DD-MM-YYYY
    m_slash = re.search(r"\b([0-2]?[1-9]|3[01])[/-](0?[1-9]|1[0-2])[/-](202\d)\b", text)
    if m_slash:
        try:
            start = datetime.strptime(f"{m_slash.group(1)}/{m_slash.group(2)}/{m_slash.group(3)}", "%d/%m/%Y").date()
            span_days = dur - 1 if dur and dur > 1 else 3
            end = start + timedelta(days=span_days)
            return start.isoformat(), end.isoformat()
        except Exception:
            pass

    # 5. Relative phrases
    if "next week" in t:
        start = today + timedelta(days=7)
    elif "this week" in t:
        start = today
    elif "next month" in t:
        start = today + timedelta(days=30)
    else:
        start = today

    span_days = dur - 1 if dur and dur > 1 else 13
    end = start + timedelta(days=span_days)
    return start.isoformat(), end.isoformat()


def parse_request(text, current_request=None):
    """Rule-based extraction of a structured trip request from free text."""
    from agents import recommendation_agent

    pax_val = _extract_pax(text)
    prefs = recommendation_agent.extract_preferences(text)
    parsed = {
        "pax": pax_val,
        "origin": _extract_origin(text),
        "category": _extract_category(text),
        "mode": _extract_mode(text),
        "duration_days": _extract_duration(text),
        "season": _extract_season(text),
        "sightseeing": _extract_sightseeing(text),
        "group_type": prefs.get("group_type"),
        "travel_style": prefs.get("travel_style"),
        "trip_focus": prefs.get("trip_focus"),
        "budget_preference": prefs.get("budget_preference"),
        "start_date": _extract_date_range(text)[0],
        "end_date": _extract_date_range(text)[1],
    }
    return merge_requests(current_request, parsed, text)


def merge_requests(old_req, new_req, text=""):
    """Merges newly extracted trip details into an existing request state,
    properly supporting explicit corrections, value replacements, and state preservation."""
    from agents import recommendation_agent

    if not old_req:
        res = dict(new_req)
        if res.get("pax") is None:
            res["pax"] = 1
        return res

    merged = dict(old_req)

    # 1. Direct explicit field updates from new_req
    for k in ("origin", "category", "mode", "season", "duration_days", "group_type", "travel_style", "trip_focus", "budget_preference"):
        v = new_req.get(k)
        if v is not None:
            merged[k] = v

    if new_req.get("pax") is not None:
        merged["pax"] = new_req["pax"]

    if new_req.get("sightseeing") is not None:
        merged["sightseeing"] = new_req["sightseeing"]

    # 2. Text-based preference overrides
    prefs = recommendation_agent.extract_preferences(text)
    for pk, pv in prefs.items():
        if pv is not None:
            merged[pk] = pv

    # 3. Text-based duration override
    dur = _extract_duration(text)
    if dur is not None:
        merged["duration_days"] = dur
        try:
            st_date = datetime.strptime(merged.get("start_date", date.today().isoformat()), "%Y-%m-%d").date()
            merged["end_date"] = (st_date + timedelta(days=dur - 1)).isoformat()
        except Exception:
            pass

    # 4. Text-based origin override
    new_orig = _extract_origin(text)
    if new_orig is not None:
        merged["origin"] = new_orig

    # 5. Text-based mode override
    new_mode = _extract_mode(text)
    if new_mode is not None:
        merged["mode"] = new_mode

    # 6. Text-based darshan category override
    new_cat = _extract_category(text)
    if new_cat is not None:
        merged["category"] = new_cat

    # 7. Text-based sightseeing override
    sightseeing = _extract_sightseeing(text)
    if sightseeing is not None:
        merged["sightseeing"] = sightseeing
        if sightseeing is False and merged.get("trip_focus") == "mixed":
            merged["trip_focus"] = "devotional"

    season = _extract_season(text)
    if season is not None:
        merged["season"] = season

    # Ambiguity check
    if is_ambiguous_change(text):
        changed = get_changed_fields(old_req, merged)
        if not changed:
            merged["_ambiguous_change"] = True

    if has_explicit_date(text):
        st_date, en_date = _extract_date_range(text)
        merged["start_date"] = st_date
        merged["end_date"] = en_date
    elif not merged.get("start_date") or not merged.get("end_date"):
        st_date, en_date = _extract_date_range(text)
        merged["start_date"] = merged.get("start_date") or st_date
        merged["end_date"] = merged.get("end_date") or en_date

    return merged


def resolve_hub(origin):
    """Dynamically resolves an origin city to a supported dataset hub if direct transport is not available."""
    if not origin:
        return None, False

    supported_hubs = db.get_distinct_origins()
    supported_map = {h.lower(): h for h in supported_hubs}

    # Direct match in dataset
    if origin.lower() in supported_map:
        return supported_map[origin.lower()], True

    # Check regional zone mapping to a supported hub
    mapped = REGION_TO_HUB.get(origin.lower())
    if mapped and mapped.lower() in supported_map:
        return supported_map[mapped.lower()], False

    return None, False


def _enrich_flight_transfer(r):
    """Enriches flight options with verified road transfer details from Jammu Airport to Katra."""
    if r.get("mode") == "flight":
        r["is_flight_connecting_transfer"] = True
        r["arrival_hub"] = "Jammu Airport"
        r["transfer_mode"] = "Taxi / Bus"
        r["transfer_route"] = "Jammu Airport → Katra"
        r["transfer_distance"] = "approx. 44-55 km"
        r["transfer_duration"] = "approx. 1-1.5 hours by road"
        if r.get("is_connecting") and r.get("connecting_hub"):
            hub = r["connecting_hub"]
            r["transfer_note"] = (
                f"Direct flight to Katra is not available. This option flies from {hub} to Jammu, "
                "followed by a local taxi/bus transfer to Katra."
            )
            r["display_route"] = f"{r.get('origin', '')} → {hub} → Jammu Airport → Katra"
        else:
            r["transfer_note"] = (
                "Direct flight to Katra is not available. This option flies to Jammu, "
                "followed by a local taxi/bus transfer to Katra."
            )
            r["display_route"] = f"{r.get('origin', '')} → Jammu Airport → Katra"
    return r


def _search_transport(request):
    """Searches whichever modes are relevant and returns (combined_results, is_direct_flag)."""
    origin = request["origin"]
    start, end, pax = request["start_date"], request["end_date"], request["pax"]
    mode = request.get("mode")

    searchers = {
        "flight": db.search_flights,
        "train": db.search_trains,
        "bus": db.search_buses,
    }
    modes_to_search = [mode] if mode in searchers else list(searchers.keys())

    # 1. First search for direct transport
    direct_results = []
    for m in modes_to_search:
        direct_results.extend(searchers[m](origin, start, end, min_seats=pax))

    if direct_results:
        for r in direct_results:
            r["is_connecting"] = False
            r["origin"] = origin
            if r.get("mode") == "flight":
                _enrich_flight_transfer(r)
        return direct_results, True

    # 2. If direct transport unavailable, resolve regional hub
    hub, is_direct = resolve_hub(origin)
    if hub:
        connecting_results = []
        for m in modes_to_search:
            res = searchers[m](hub, start, end, min_seats=pax)
            for r in res:
                r["is_connecting"] = True
                r["connecting_hub"] = hub
                r["original_origin"] = origin
                r["origin"] = origin  # Preserve exact user's origin
                r["route_note"] = f"Connecting via {hub}"
                r["display_route"] = f"{origin} → Katra (via {hub})"
                if r.get("mode") == "flight":
                    _enrich_flight_transfer(r)
            connecting_results.extend(res)
        return connecting_results, False

    # 3. Unsupported origin -> return empty list (no fabricated data)
    return [], False


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
    transport, is_direct_transport = _search_transport(request)

    if not slots or not transport:
        mode_note = f" by {request['mode']}" if request.get("mode") else ""
        if not transport:
            supported_hubs = db.get_distinct_origins()
            msg = (
                f"Transport availability from {request['origin']} is not represented in the current prototype dataset. "
                f"Supported major departure hubs include: {', '.join(supported_hubs)}. "
                "You can search travel from one of these hubs to plan your yatra."
            )
        else:
            msg = (
                f"I couldn't find matching yatra slots{mode_note} for those dates. "
                "Want me to widen the date range or try a different mode of transport?"
            )
        return {
            "status": "NO_AVAILABILITY",
            "message": msg,
            "slots_found": len(slots),
            "flights_found": len(transport),
            "unsupported_origin": request.get("origin") if not transport else None,
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
                combos.append({"flight": tr, "transport": tr, "slot": s, "total_price": total})



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
# LLM-powered mode: GPT-OSS / OpenAI compatible
# ---------------------------------------------------------------------

def parse_request_llm(text, api_key=None, base_url=None):
    import json
    from openai import OpenAI

    key = api_key or os.environ.get("OPENAI_API_KEY", "dummy_key")
    url = base_url or os.environ.get("OPENAI_BASE_URL", None)
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=key, base_url=url) if url else OpenAI(api_key=key)
    today = date.today().isoformat()

    system = f"""Extract Vaishno Devi yatra trip details from the user's message as JSON only.
Today's date is {today}. Fields:
- pax (integer, default 1)
- origin (Indian city name in English or null)
- category (one of "Normal Darshan", "VIP Darshan", "Helicopter Darshan", or null)
- mode (one of "flight", "train", "bus", or null if no preference)
- start_date (YYYY-MM-DD)
- end_date (YYYY-MM-DD)
If no dates mentioned, use the next 14 days.
Respond with ONLY valid JSON, no markdown formatting or extra text."""

    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json", "", 1).strip()
    return json.loads(raw)


def process_message(text, api_key=None, base_url=None):
    """Single entry point the Streamlit UI calls. Returns a structured plan dict."""
    if api_key or os.environ.get("OPENAI_API_KEY"):
        try:
            request = parse_request_llm(text, api_key, base_url)
        except Exception:
            request = parse_request(text)
    else:
        request = parse_request(text)

    plan = build_plan(request)
    plan["_request"] = request
    return plan

