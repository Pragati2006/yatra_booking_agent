"""
agents/itinerary_agent.py
Phase E — Intelligent Day-by-Day Itinerary Generation, Editing, and Presentation.

Supports:
- Original build_itinerary() and format_itinerary_text() for option-based bookings
- generate_default_itinerary() for trip-request based planning
- sync_itinerary_duration() to keep itinerary length aligned with Phase D trip edits
- parse_itinerary_command(), validate_itinerary_command(), apply_itinerary_edit()
  for natural language day-by-day itinerary modifications (MOVE, ADD, REMOVE, REPLACE, REST, SHOW, etc.)
- Grounding against explore_data.PLACES and contextual follow-ups.
"""

import copy
import os
import re
from datetime import datetime, timedelta

import agent as legacy_agent
import explore_data
import yatra_info

CANONICAL_PLACES = {
    "bhairavnath": "Bhairavnath Temple",
    "bhairavnath temple": "Bhairavnath Temple",
    "ardhkuwari": "Ardhkuwari Cave",
    "ardhkuwari cave": "Ardhkuwari Cave",
    "garbh joon": "Ardhkuwari Cave",
    "charan paduka": "Charan Paduka",
    "nau devi": "Nau Devi Cave Temple",
    "nau devi cave temple": "Nau Devi Cave Temple",
    "baba dhansar": "Baba Dhansar",
    "jhajjar kotli": "Jhajjar Kotli",
    "patnitop": "Patnitop",
    "sanasar": "Sanasar",
    "mansar": "Mansar Lake",
    "mansar lake": "Mansar Lake",
    "raghunath": "Raghunath Temple, Jammu",
    "raghunath temple": "Raghunath Temple, Jammu",
    "bahu fort": "Bahu Fort & Bagh-e-Bahu",
    "bagh-e-bahu": "Bahu Fort & Bagh-e-Bahu",
    "amar mahal": "Amar Mahal Palace",
    "ban ganga": "Ban Ganga",
    "himkoti": "Himkoti",
    "dera baba banda": "Dera Baba Banda Bahadur",
    "shiv khori": "Shiv Khori",
    "peer kho": "Peer Kho Cave Temple",
    "sightseeing": "Sightseeing",
}


def _fmt_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%a, %d %b %Y")
    except Exception:
        return str(d)


def build_itinerary(option, hotel=None, hotel_nights=0, sightseeing_places=None, request=None):
    """Returns a list of day dicts: {day_number, date, title, activities: [str, ...]}
    dynamically respecting the requested trip duration from request."""
    tr = option.get("transport") or option.get("flight")
    s = option["slot"]
    sightseeing_places = sightseeing_places or []

    req = request or {}
    duration = req.get("duration_days")
    if not duration:
        base_days = 2 + (1 if sightseeing_places else 0) + (1 if hotel or hotel_nights else 0)
        duration = max(3, base_days)

    days = []
    travel_date = tr["travel_date"]
    darshan_date = s["slot_date"]
    origin = tr.get("origin", "Delhi")
    mode = tr.get("mode", "transport").lower()
    operator = tr.get("operator", "")
    transport_no = tr.get("transport_no", "")
    dep_time = tr.get("departure_time", "")

    if mode == "flight":
        transport_summary = f"Fly with {operator} ({transport_no}) departing at {dep_time} from {tr['origin']} to {tr['destination']}"
    elif mode == "train":
        transport_summary = f"Travel by Train via {operator} - {transport_no} departing at {dep_time} from {tr['origin']} to {tr['destination']}"
    else:
        transport_summary = f"Travel via {operator} {transport_no} from {tr['origin']} to {tr['destination']}"

    if tr.get("route_note"):
        transport_summary += f" ({tr['route_note']})"

    start_dt = datetime.strptime(travel_date, "%Y-%m-%d")

    # Day 1: Arrival & Check-in
    day1_activities = [transport_summary]
    if mode == "flight":
        day1_activities.append("Taxi transfer from Jammu Airport to Katra (~1.5-2 hrs)")
    else:
        day1_activities.append("Direct arrival in Katra base town")

    if hotel:
        day1_activities.append(f"Check in at {hotel['name']} ({hotel['category']})")
    day1_activities.append("Obtain mandatory Yatra Slip / Parchi at Katra counter")
    days.append({"day_number": 1, "date": _fmt_date(travel_date), "title": "Arrival & Check-in", "activities": day1_activities})

    # Day 2: Pilgrimage & Darshan
    darshan_activities = []
    if s["category"] == "Helicopter Darshan":
        darshan_activities.append("Helicopter from Katra to Sanjichhat, then a short walk to Bhawan")
    else:
        darshan_activities.append("Trek (or pony/palki) from Katra to Bhawan via the traditional route or Tarakote Marg")
    darshan_activities.append(f"{s['category']} at {s['slot_time']}")
    darshan_activities.append("Visit Bhairavnath Temple after darshan (traditionally considered part of completing the yatra)")
    days.append({"day_number": 2, "date": _fmt_date(darshan_date), "title": "Pilgrimage & Darshan", "activities": darshan_activities})

    # Day 3 to Day (duration - 1): Intermediate Days (Sightseeing / Rest / Excursions)
    suggested_places = ["Patnitop", "Baba Dhansar", "Ardhkuwari Cave", "Mansar Lake", "Shiv Khori", "Nau Devi Cave Temple"]
    sight_idx = 0

    for d in range(3, duration):
        day_date = start_dt + timedelta(days=d - 1)
        day_str = _fmt_date(day_date.strftime("%Y-%m-%d"))

        if sight_idx < len(sightseeing_places):
            p_name = sightseeing_places[sight_idx]
            days.append({
                "day_number": d,
                "date": day_str,
                "title": f"Sightseeing — {p_name}",
                "activities": [
                    f"Visit {p_name}",
                    "Local sightseeing and exploration around Katra / Jammu region",
                ],
            })
            sight_idx += 1
        elif d == 3:
            p_sug = suggested_places[0]
            days.append({
                "day_number": d,
                "date": day_str,
                "title": "Sightseeing & Exploration",
                "activities": [
                    f"Visit {p_sug}",
                    "Local Katra market exploration & souvenirs",
                ],
            })
        elif d == 4:
            p_sug = suggested_places[1]
            days.append({
                "day_number": d,
                "date": day_str,
                "title": "Rest & Local Exploration",
                "activities": [
                    f"Visit {p_sug}",
                    "Rest and local dining in Katra town",
                ],
            })
        else:
            p_sug = suggested_places[(d - 3) % len(suggested_places)]
            days.append({
                "day_number": d,
                "date": day_str,
                "title": "Excursion & Leisure",
                "activities": [
                    f"Day trip to {p_sug}",
                    "Relaxed evening in Katra",
                ],
            })

    # Final Day (Day duration): Check-out & Return Journey
    if duration >= 3:
        dep_date = start_dt + timedelta(days=duration - 1)
        dep_activities = []
        if hotel:
            dep_activities.append(f"Check out of {hotel['name']}")
        else:
            dep_activities.append("Check out from hotel")
        if mode == "flight":
            dep_activities.append("Taxi back to Jammu (if departing by flight)")
        dep_activities.append(f"Return journey to {origin}")

        days.append({
            "day_number": duration,
            "date": _fmt_date(dep_date.strftime("%Y-%m-%d")),
            "title": "Check-out & Return Journey",
            "activities": dep_activities,
        })

    return days


def format_itinerary_text(days):
    """Plain-text version, useful for chat display or a downloadable summary."""
    lines = []
    for d in days:
        lines.append(f"Day {d['day_number']} — {d['date']}: {d['title']}")
        for a in d["activities"]:
            lines.append(f"  • {a}")
    return "\n".join(lines)


def generate_default_itinerary(request):
    """Generates a structured day-wise itinerary list of dicts based on request parameters."""
    req = request or {}
    duration = req.get("duration_days", 4) or 4
    origin = req.get("origin") or "Delhi"
    mode = (req.get("mode") or "train").title()
    cat = req.get("category") or "Normal Darshan"
    start_date_str = req.get("start_date") or datetime.now().strftime("%Y-%m-%d")

    try:
        st_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    except Exception:
        st_date = datetime.now()

    days = []

    # Day 1: Arrival
    days.append({
        "day_number": 1,
        "date": _fmt_date(st_date.strftime("%Y-%m-%d")),
        "title": "Arrival & Check-in",
        "activities": [
            f"Travel from {origin} to Katra by {mode}",
            "Arrival & check-in at Katra hotel",
            "Obtain mandatory Yatra Slip / Parchi at Katra counter",
        ],
    })

    # Day 2: Darshan
    days.append({
        "day_number": 2,
        "date": _fmt_date((st_date + timedelta(days=1)).strftime("%Y-%m-%d")),
        "title": "Pilgrimage & Darshan",
        "activities": [
            "Trek from Katra to Bhawan via Tarakote Marg / Traditional Route",
            f"{cat} at Bhawan",
            "Visit Bhairavnath Temple after darshan",
        ],
    })

    # Day 3 to Day N-1: Sightseeing / Rest
    suggested_places = ["Patnitop", "Baba Dhansar", "Ardhkuwari Cave", "Mansar Lake", "Shiv Khori", "Nau Devi Cave Temple"]
    place_idx = 0

    for d in range(3, duration):
        day_date = st_date + timedelta(days=d - 1)
        if d == 3:
            p1 = suggested_places[place_idx % len(suggested_places)]
            days.append({
                "day_number": d,
                "date": _fmt_date(day_date.strftime("%Y-%m-%d")),
                "title": "Sightseeing & Exploration",
                "activities": [f"Visit {p1}", "Local Katra market exploration & souvenirs"],
            })
            place_idx += 1
        elif d == 4:
            p2 = suggested_places[place_idx % len(suggested_places)]
            days.append({
                "day_number": d,
                "date": _fmt_date(day_date.strftime("%Y-%m-%d")),
                "title": "Rest & Relaxation",
                "activities": [f"Visit {p2}", "Rest and local dining in Katra town"],
            })
            place_idx += 1
        else:
            p_next = suggested_places[place_idx % len(suggested_places)]
            days.append({
                "day_number": d,
                "date": _fmt_date(day_date.strftime("%Y-%m-%d")),
                "title": "Excursion & Leisure",
                "activities": [f"Day trip to {p_next}", "Relaxed evening in Katra"],
            })
            place_idx += 1

    # Final Day: Departure (only if duration >= 3, else Day 2 is final if duration=2)
    if duration >= 3:
        dep_date = st_date + timedelta(days=duration - 1)
        days.append({
            "day_number": duration,
            "date": _fmt_date(dep_date.strftime("%Y-%m-%d")),
            "title": "Check-out & Return Journey",
            "activities": ["Check out from hotel", f"Return journey to {origin}"],
        })

    return days


def sync_itinerary_duration(itinerary, new_duration, request=None):
    """Synchronizes itinerary length when Phase D modifies duration_days."""
    if not itinerary:
        return generate_default_itinerary(request or {"duration_days": new_duration})

    curr_len = len(itinerary)
    if curr_len == new_duration:
        return itinerary

    new_itin = copy.deepcopy(itinerary)
    req = request or {}
    origin = req.get("origin") or "Delhi"

    try:
        st_date = datetime.strptime(req.get("start_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
    except Exception:
        st_date = datetime.now()

    if curr_len < new_duration:
        # Extend itinerary
        last_day_num = curr_len
        # Move previous final departure day if it was departure
        if new_itin[-1]["title"] == "Check-out & Return Journey":
            departure_day = new_itin.pop()
        else:
            departure_day = None

        suggested = ["Patnitop", "Mansar Lake", "Baba Dhansar", "Shiv Khori", "Nau Devi Cave Temple"]
        for d in range(len(new_itin) + 1, new_duration):
            day_dt = st_date + timedelta(days=d - 1)
            place = suggested[(d - 3) % len(suggested)]
            new_itin.append({
                "day_number": d,
                "date": _fmt_date(day_dt.strftime("%Y-%m-%d")),
                "title": "Sightseeing & Exploration",
                "activities": [f"Visit {place}", "Relaxed local activities"],
            })

        # Add departure day at end
        dep_dt = st_date + timedelta(days=new_duration - 1)
        new_itin.append({
            "day_number": new_duration,
            "date": _fmt_date(dep_dt.strftime("%Y-%m-%d")),
            "title": "Check-out & Return Journey",
            "activities": ["Check out from hotel", f"Return journey to {origin}"],
        })
    else:
        # Trim itinerary
        new_itin = new_itin[:new_duration]
        dep_dt = st_date + timedelta(days=new_duration - 1)
        new_itin[-1] = {
            "day_number": new_duration,
            "date": _fmt_date(dep_dt.strftime("%Y-%m-%d")),
            "title": "Check-out & Return Journey",
            "activities": ["Check out from hotel", f"Return journey to {origin}"],
        }

    # Re-index day_number
    for idx, d in enumerate(new_itin, start=1):
        d["day_number"] = idx

    return new_itin


def match_place_name(text):
    """Grounds a free-text place name against known canonical places."""
    if not text:
        return None
    t = text.strip().lower()
    t_clean = re.sub(r"[^\w\s]", "", t).strip()

    if t_clean in CANONICAL_PLACES:
        return CANONICAL_PLACES[t_clean]
    for key, val in CANONICAL_PLACES.items():
        if key == t_clean or (len(key) >= 4 and key in t_clean):
            return val

    for p in explore_data.PLACES:
        p_name = p["name"].lower()
        if t_clean == p_name or (len(t_clean) >= 4 and t_clean in p_name):
            return p["name"]

    return None


def parse_itinerary_command(text, itinerary=None, context=None):
    """Deterministic extraction of day-level itinerary action from user text."""
    t = (text or "").strip().lower()
    clean_t = re.sub(r"[^\w\s]", " ", t)

    # 1. Day Numbers
    day_matches = re.findall(r"\bday\s*(\d+)\b", t)
    days = [int(d) for d in day_matches]
    target_day = days[-1] if days else None
    source_day = days[0] if len(days) >= 2 else None

    context = context or {}

    # 2. Action: REST (check before ADD so 'add a rest day on Day 3' matches REST)
    if "rest day" in t or "add a rest day" in t or re.search(r"\bmake day\s*\d+.*rest\b", t):
        return {
            "action": "REST",
            "day": target_day or 3,
        }

    # 3. Action: REPLACE
    m_replace = re.search(r"\breplace\s+(.*?)\s+with\s+(.*)", t)
    if m_replace:
        raw_old = m_replace.group(1).strip()
        raw_new = m_replace.group(2).strip()
        old_p = match_place_name(raw_old) or raw_old.capitalize()
        new_p = match_place_name(raw_new) or raw_new.capitalize()
        return {
            "action": "REPLACE",
            "old_place": old_p,
            "new_place": new_p,
            "raw_new_place": raw_new,
            "day": target_day,
        }

    # 4. Action: MOVE
    m_move = re.search(r"\b(?:move|shift|transfer)\s+(.*?)\s+to\s+day\s*(\d+)", t)
    if m_move:
        raw_place = m_move.group(1).strip()
        t_day = int(m_move.group(2))
        if raw_place in ("that", "it", "this") or not raw_place:
            place = context.get("place")
        else:
            place = match_place_name(raw_place) or raw_place.capitalize()

        if not place and raw_place in ("that", "it", "this"):
            return {
                "action": "MOVE",
                "place": None,
                "target_day": t_day,
                "ambiguous": True,
                "ambiguity_prompt": f"Which activity would you like me to move to Day {t_day}?",
            }
        return {
            "action": "MOVE",
            "place": place,
            "raw_place": raw_place,
            "source_day": source_day,
            "target_day": t_day,
        }

    # 5. Action: REMOVE
    m_remove_from = re.search(r"\b(?:remove|delete|drop|take out)\s+(.*?)\s+from\s+day\s*(\d+)", t)
    if m_remove_from:
        raw_place = m_remove_from.group(1).strip()
        r_day = int(m_remove_from.group(2))
        place = match_place_name(raw_place) or (raw_place.title() if raw_place != "sightseeing" else "Sightseeing")
        return {
            "action": "REMOVE",
            "place": place,
            "raw_place": raw_place,
            "day": r_day,
        }

    m_remove = re.search(r"\b(?:remove|delete|drop)\s+([a-z\s]+)", t)
    if m_remove and not re.search(r"\bday\s*\d+", t):
        raw_place = m_remove.group(1).strip()
        if raw_place and raw_place not in ("itinerary", "day", "days"):
            place = match_place_name(raw_place) or raw_place.title()
            return {
                "action": "REMOVE",
                "place": place,
                "raw_place": raw_place,
                "day": target_day,
            }

    # 6. Action: ADD
    m_add_on = re.search(r"\b(?:add|include|put)\s+(.*?)\s+(?:on|to)\s+day\s*(\d+)", t)
    if m_add_on:
        raw_place = m_add_on.group(1).strip()
        a_day = int(m_add_on.group(2))
        place = match_place_name(raw_place) or (raw_place.title() if raw_place != "sightseeing" else "Sightseeing")
        return {
            "action": "ADD",
            "place": place,
            "raw_place": raw_place,
            "day": a_day,
        }

    # 7. Action: MODIFY_PACE / MODIFY_THEME
    m_pace = re.search(r"\bmake day\s*(\d+).*(relaxed|devotional|packed|sightseeing)\b", t)
    if m_pace:
        p_day = int(m_pace.group(1))
        style = m_pace.group(2)
        return {
            "action": "MODIFY_PACE" if style in ("relaxed", "packed") else "MODIFY_THEME",
            "day": p_day,
            "style": style,
        }

    # 8. Action: SHOW
    if any(k in t for k in ["show", "view", "what am i doing", "tell me about day", "what's on", "what is on"]):
        return {
            "action": "SHOW",
            "day": target_day,
        }

    # Default SHOW
    return {
        "action": "SHOW",
        "day": target_day,
    }


def validate_itinerary_command(itinerary, command):
    """Validates whether an itinerary command is actionable against current itinerary state."""
    if not itinerary:
        return False, "No active itinerary found to modify."

    total_days = len(itinerary)
    action = command.get("action")

    if action == "SHOW":
        day = command.get("day")
        if day is not None and (day < 1 or day > total_days):
            return False, f"Day {day} does not exist in your current {total_days}-day itinerary. Your trip runs from Day 1 to Day {total_days}."
        return True, ""

    if action == "MOVE":
        target_day = command.get("target_day")
        if target_day is not None and (target_day < 1 or target_day > total_days):
            return False, f"Target Day {target_day} does not exist in your current {total_days}-day itinerary."
        place = command.get("place")
        if not place:
            return False, command.get("ambiguity_prompt", f"Which activity would you like me to move to Day {target_day}?")
        return True, ""

    if action == "ADD":
        day = command.get("day")
        if day is not None and (day < 1 or day > total_days):
            return False, f"Day {day} does not exist in your current {total_days}-day itinerary."
        raw_place = command.get("raw_place")
        place = command.get("place")
        if not match_place_name(raw_place) and place not in ("Sightseeing", "Rest"):
            return False, f"I couldn't find '{raw_place}' in our verified J&K places catalogue. Supported places include Patnitop, Mansar Lake, Shiv Khori, Baba Dhansar, Bhairavnath Temple, etc."
        return True, ""

    if action == "REMOVE":
        day = command.get("day")
        if day is not None and (day < 1 or day > total_days):
            return False, f"Day {day} does not exist in your current {total_days}-day itinerary."
        return True, ""

    if action == "REPLACE":
        raw_new = command.get("raw_new_place")
        if not match_place_name(raw_new):
            return False, f"I couldn't find '{raw_new}' in our verified J&K places catalogue."
        return True, ""

    if action == "REST":
        day = command.get("day")
        if day is not None and (day < 1 or day > total_days):
            return False, f"Day {day} does not exist in your current {total_days}-day itinerary."
        return True, ""

    if action in ("MODIFY_PACE", "MODIFY_THEME"):
        day = command.get("day")
        if day is not None and (day < 1 or day > total_days):
            return False, f"Day {day} does not exist in your current {total_days}-day itinerary."
        return True, ""

    return True, ""


def apply_itinerary_edit(itinerary, command):
    """Applies a safe mutation to a copy of itinerary and returns (updated_itinerary, summary_str, new_context)."""
    new_itin = copy.deepcopy(itinerary)
    action = command.get("action")
    new_ctx = {}

    if action == "MOVE":
        target_day = command["target_day"]
        place = command["place"]

        # Find current day containing place
        source_day_num = None
        removed_act_str = None
        for d in new_itin:
            for act in d["activities"]:
                if place.lower() in act.lower():
                    source_day_num = d["day_number"]
                    removed_act_str = act
                    d["activities"].remove(act)
                    break
            if source_day_num:
                break

        target_d = new_itin[target_day - 1]
        act_line = removed_act_str or f"Visit {place}"
        if not any(place.lower() in a.lower() for a in target_d["activities"]):
            target_d["activities"].append(act_line)

        summary = f"✏️ **Itinerary Updated:**\n• **{place}:** Moved from Day {source_day_num or 'previous'} → Day {target_day}\n\n*All other itinerary items remain unchanged.*"
        new_ctx = {"day": target_day, "place": place}
        return new_itin, summary, new_ctx

    if action == "ADD":
        day_num = command.get("day") or 2
        place = command["place"]
        target_d = new_itin[day_num - 1]
        act_line = f"Visit {place}" if not place.startswith("Visit") else place
        if not any(place.lower() in a.lower() for a in target_d["activities"]):
            target_d["activities"].append(act_line)

        summary = f"✏️ **Itinerary Updated:**\n• **{place}:** Added to Day {day_num}\n\n*All other itinerary items remain unchanged.*"
        new_ctx = {"day": day_num, "place": place}
        return new_itin, summary, new_ctx

    if action == "REMOVE":
        day_num = command.get("day")
        place = command["place"]
        found_day = None

        if day_num:
            target_d = new_itin[day_num - 1]
            to_remove = [a for a in target_d["activities"] if place.lower() in a.lower()]
            for r in to_remove:
                target_d["activities"].remove(r)
            found_day = day_num
        else:
            for d in new_itin:
                to_remove = [a for a in d["activities"] if place.lower() in a.lower()]
                if to_remove:
                    found_day = d["day_number"]
                    for r in to_remove:
                        d["activities"].remove(r)

        summary = f"✏️ **Itinerary Updated:**\n• **{place}:** Removed from Day {found_day or 'itinerary'}\n\n*All other itinerary items remain unchanged.*"
        return new_itin, summary, new_ctx

    if action == "REPLACE":
        old_place = command["old_place"]
        new_place = command["new_place"]
        found_day = command.get("day")

        if not found_day:
            for d in new_itin:
                if any(old_place.lower() in a.lower() for a in d["activities"]):
                    found_day = d["day_number"]
                    break
        found_day = found_day or 3
        target_d = new_itin[found_day - 1]

        # Replace activity
        replaced = False
        for idx, a in enumerate(target_d["activities"]):
            if old_place.lower() in a.lower():
                target_d["activities"][idx] = f"Visit {new_place}"
                replaced = True
                break
        if not replaced:
            target_d["activities"].append(f"Visit {new_place}")

        summary = f"✏️ **Itinerary Updated:**\n• **{new_place}:** Replaced {old_place} on Day {found_day}\n\n*All other itinerary items remain unchanged.*"
        new_ctx = {"day": found_day, "place": new_place}
        return new_itin, summary, new_ctx

    if action == "REST":
        day_num = command.get("day") or 3
        target_d = new_itin[day_num - 1]
        target_d["title"] = "Rest & Preparation"
        target_d["activities"] = ["Rest at your hotel and prepare for travel/trek ahead", "Casual local relaxation in Katra"]
        summary = f"✏️ **Itinerary Updated:**\n• **Day {day_num}:** Marked as a Rest & Preparation Day\n\n*All other itinerary items remain unchanged.*"
        new_ctx = {"day": day_num, "place": "Rest"}
        return new_itin, summary, new_ctx

    if action in ("MODIFY_PACE", "MODIFY_THEME"):
        day_num = command.get("day") or 2
        style = command.get("style") or "relaxed"
        target_d = new_itin[day_num - 1]
        target_d["title"] = f"{target_d['title']} ({style.title()})"
        summary = f"✏️ **Itinerary Updated:**\n• **Day {day_num} Pacing:** Set to {style.title()}\n\n*All other itinerary items remain unchanged.*"
        new_ctx = {"day": day_num}
        return new_itin, summary, new_ctx

    return new_itin, "No edits made.", new_ctx


def format_show_reply(itinerary, command):
    """Formats response when user asks to show full itinerary or a specific day."""
    day_num = command.get("day")
    if day_num:
        d = itinerary[day_num - 1]
        acts = "\n".join(f"• {a}" for a in d["activities"])
        reply = (
            f"🙏 **Jai Mata Di! Here is Day {d['day_number']}:**\n\n"
            f"### Day {d['day_number']} — {d['date']}: {d['title']}\n"
            f"{acts}\n\n"
            f"_Would you like to modify this day or view another day?_"
        )
        ctx_place = None
        for a in d["activities"]:
            p = match_place_name(a)
            if p:
                ctx_place = p
                break
        ctx = {"day": day_num, "place": ctx_place or (d["activities"][0] if d["activities"] else None)}
        return reply, ctx

    return format_full_itinerary_card(itinerary), None


def format_full_itinerary_card(itinerary):
    """Renders clean markdown block for the complete day-wise itinerary."""
    lines = ["🙏 **Jai Mata Di! Here is your Day-by-Day Itinerary:**\n", "### Day-Wise Itinerary\n"]
    for d in itinerary:
        lines.append(f"**Day {d['day_number']:02d} — {d['date']}: {d['title']}**")
        for a in d["activities"]:
            lines.append(f"• {a}")
        lines.append("")
    lines.append("_Would you like to move an activity, add a place, or adjust pacing for any day?_")
    return "\n".join(lines)
