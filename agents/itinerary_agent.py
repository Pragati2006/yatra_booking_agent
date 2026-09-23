"""
agents/itinerary_agent.py
Builds a day-wise itinerary once the pilgrim has chosen their transport
+ darshan option, optionally a hotel, and optionally sightseeing spots.
Purely a presentation/planning layer over data the other agents already
fetched - it doesn't do any new searching or booking itself.
"""

import os
from datetime import datetime, timedelta

import agent as legacy_agent  # reuses the real-world arrival/darshan timing logic


def _fmt_date(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%a, %d %b %Y")


def build_itinerary(option, hotel=None, hotel_nights=0, sightseeing_places=None):
    """Returns a list of day dicts: {day_number, date, title, activities: [str, ...]}."""
    tr = option.get("transport") or option.get("flight")
    s = option["slot"]
    sightseeing_places = sightseeing_places or []

    days = []
    travel_date = tr["travel_date"]
    darshan_date = s["slot_date"]
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

    # Day 1: travel + arrival
    day1_activities = [transport_summary]
    if mode == "flight":
        day1_activities.append("Taxi transfer from Jammu Airport to Katra (~1.5-2 hrs)")
    else:
        day1_activities.append("Direct arrival in Katra base town")

    if hotel:
        day1_activities.append(f"Check in at {hotel['name']} ({hotel['category']})")
    days.append({"day_number": 1, "date": _fmt_date(travel_date), "title": "Arrival & Check-in", "activities": day1_activities})


    # If darshan is on a later date, add a rest/prep day
    dep = datetime.strptime(travel_date, "%Y-%m-%d")
    darshan_dt = datetime.strptime(darshan_date, "%Y-%m-%d")
    gap_days = (darshan_dt - dep).days

    if gap_days >= 1:
        for d in range(1, gap_days):
            day_date = dep + timedelta(days=d)
            days.append({
                "day_number": d + 1,
                "date": _fmt_date(day_date.strftime("%Y-%m-%d")),
                "title": "Rest & preparation",
                "activities": ["Rest at your hotel and prepare for the trek/darshan ahead", "Optional: visit nearby trek-route shrines like Charan Paduka"],
            })

    darshan_day_num = gap_days + 1
    darshan_activities = []
    if s["category"] == "Helicopter Darshan":
        darshan_activities.append("Helicopter from Katra to Sanjichhat, then a short walk to Bhawan")
    else:
        darshan_activities.append("Trek (or pony/palki) from Katra to Bhawan via the traditional route or Tarakote Marg")
    darshan_activities.append(f"{s['category']} at {s['slot_time']}")
    darshan_activities.append("Visit Bhairavnath Temple after darshan (traditionally considered part of completing the yatra)")
    days.append({"day_number": darshan_day_num, "date": _fmt_date(darshan_date), "title": "Darshan day", "activities": darshan_activities})

    # Sightseeing day, if any places were chosen
    if sightseeing_places:
        sightseeing_date = darshan_dt + timedelta(days=1)
        days.append({
            "day_number": darshan_day_num + 1,
            "date": _fmt_date(sightseeing_date.strftime("%Y-%m-%d")),
            "title": "Sightseeing",
            "activities": [f"Visit {name}" for name in sightseeing_places],
        })

    # Departure day
    last_day = days[-1]
    departure_date = datetime.strptime(darshan_date, "%Y-%m-%d") + timedelta(days=(2 if sightseeing_places else 1))
    if hotel:
        days.append({
            "day_number": last_day["day_number"] + 1,
            "date": _fmt_date(departure_date.strftime("%Y-%m-%d")),
            "title": "Check-out & departure",
            "activities": [f"Check out of {hotel['name']}", "Taxi back to Jammu (if departing by flight)", "Return journey"],
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
