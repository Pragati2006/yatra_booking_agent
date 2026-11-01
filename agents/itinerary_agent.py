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


# -----------------------------------------------------------------------------
# Destination Logistics & Realistic Feasibility Engine
# -----------------------------------------------------------------------------

DESTINATION_LOGISTICS = {
    "Bhairavnath Temple": {
        "region": "trek_route",
        "base_hub": "Shri Mata Vaishno Devi Bhawan",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 0.5,
        "travel_time_desc": "~3 km uphill from Bhawan or 5-min ropeway",
        "exertion_level": "High",
        "min_trip_days_required": 2,
        "suitability": "Sacred completion shrine; traditionally visited right after Bhawan darshan.",
        "estimated_transport_cost": "₹100 one-way ropeway or on foot",
        "cost_type": "verified_ticket",
    },
    "Ardhkuwari Cave": {
        "region": "trek_route",
        "base_hub": "Trek Route (Garbh Joon)",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 3.0,
        "travel_time_desc": "Roughly halfway up the 13 km trek from Katra",
        "exertion_level": "High",
        "min_trip_days_required": 2,
        "suitability": "Natural midpoint resting shrine where Goddess meditated in Garbh Joon cave.",
        "estimated_transport_cost": "Free entry (battery car ₹350 one-way where operational)",
        "cost_type": "verified_ticket",
    },
    "Charan Paduka": {
        "region": "trek_route",
        "base_hub": "Trek Route (~1.5 km)",
        "visit_duration_hrs": 0.5,
        "travel_time_from_katra_hrs": 0.75,
        "travel_time_desc": "~1.5 km from Katra base checkpost",
        "exertion_level": "Moderate",
        "min_trip_days_required": 2,
        "suitability": "Low-effort sacred stop early on the trek trail marking the Goddess's footprints.",
        "estimated_transport_cost": "Free (on foot / pony route)",
        "cost_type": "verified_ticket",
    },
    "Ban Ganga": {
        "region": "trek_route",
        "base_hub": "Katra Base / Ban Ganga",
        "visit_duration_hrs": 0.5,
        "travel_time_from_katra_hrs": 0.25,
        "travel_time_desc": "~1.5 km from Katra town",
        "exertion_level": "Light",
        "min_trip_days_required": 2,
        "suitability": "Sacred stream where pilgrims traditionally cleanse before beginning the trek.",
        "estimated_transport_cost": "Free",
        "cost_type": "verified_ticket",
    },
    "Himkoti": {
        "region": "trek_route",
        "base_hub": "Tarakote Marg",
        "visit_duration_hrs": 0.75,
        "travel_time_from_katra_hrs": 2.5,
        "travel_time_desc": "Midpoint along the newer Tarakote Marg route",
        "exertion_level": "Moderate",
        "min_trip_days_required": 2,
        "suitability": "Scenic viewpoint with panoramic valley views and rest facilities on gentler slope.",
        "estimated_transport_cost": "Free (battery car option available)",
        "cost_type": "verified_ticket",
    },
    "Katra": {
        "region": "katra_nearby",
        "base_hub": "Katra Base Town",
        "visit_duration_hrs": 2.0,
        "travel_time_from_katra_hrs": 0.0,
        "travel_time_desc": "Base town",
        "exertion_level": "Light",
        "min_trip_days_required": 2,
        "suitability": "Vibrant pilgrim hub for RFID registration, dry fruits shopping, and dining.",
        "estimated_transport_cost": "Walking / local auto ₹50-100",
        "cost_type": "estimated_local",
    },
    "Nau Devi Cave Temple": {
        "region": "katra_nearby",
        "base_hub": "Katra Base Town",
        "visit_duration_hrs": 1.0,
        "travel_time_from_katra_hrs": 0.35,
        "travel_time_desc": "~10 km from Katra (~20-25 mins by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "Quiet cave temple dedicated to the nine forms of Durga; excellent gentle recovery stop.",
        "estimated_transport_cost": "Auto / taxi ₹200-400 roundtrip (Estimated)",
        "cost_type": "estimated_local",
    },
    "Baba Dhansar": {
        "region": "katra_nearby",
        "base_hub": "Katra Base Town",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 0.5,
        "travel_time_desc": "~15 km from Katra (~30-35 mins by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "Tranquil waterfall and turquoise spring pools, perfect for relaxing after the yatra trek.",
        "estimated_transport_cost": "Local taxi ₹600-1,000 roundtrip (Estimated)",
        "cost_type": "estimated_local",
    },
    "Jhajjar Kotli": {
        "region": "katra_nearby",
        "base_hub": "Katra Base Town",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 0.5,
        "travel_time_desc": "~15-20 km from Katra (~35 mins by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "Popular picnic retreat along a fresh mountain stream with relaxing scenery.",
        "estimated_transport_cost": "Local taxi ₹800-1,200 roundtrip (Estimated)",
        "cost_type": "estimated_local",
    },
    "Dera Baba Banda Bahadur": {
        "region": "katra_nearby",
        "base_hub": "Katra Base Town",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 0.75,
        "travel_time_desc": "~28 km from Katra (~45-50 mins along Chenab banks)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "300-year-old historic Sikh gurudwara on the Chenab riverbank honoring Baba Banda Singh Bahadur.",
        "estimated_transport_cost": "Taxi ₹1,200-1,800 roundtrip (Estimated)",
        "cost_type": "estimated_local",
    },
    "Raghunath Temple, Jammu": {
        "region": "jammu_city",
        "base_hub": "Jammu City",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 1.25,
        "travel_time_desc": "~45-55 km from Katra (~1-1.5 hrs via NH-44)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "Grand Dogra-era temple complex in the heart of Jammu city, ideal on arrival or departure day.",
        "estimated_transport_cost": "Jammu-Katra cab ₹1,300-2,000 one-way (Estimated)",
        "cost_type": "estimated_local",
    },
    "Bahu Fort & Bagh-e-Bahu": {
        "region": "jammu_city",
        "base_hub": "Jammu City",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 1.25,
        "travel_time_desc": "~50 km from Katra (~1-1.5 hrs by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "Historic fort with Bawey Wali Mata temple and terraced gardens overlooking the Tawi river.",
        "estimated_transport_cost": "Entry ₹10; cab from Katra ₹1,500-2,200 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Amar Mahal Palace": {
        "region": "jammu_city",
        "base_hub": "Jammu City",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 1.25,
        "travel_time_desc": "~48 km from Katra (~1-1.5 hrs by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "19th-century French-chateau-style palace museum housing historic miniature paintings and golden throne.",
        "estimated_transport_cost": "Entry ₹20 adults; Jammu transit cab (Estimated)",
        "cost_type": "estimated_local",
    },
    "Peer Kho Cave Temple": {
        "region": "jammu_city",
        "base_hub": "Jammu City",
        "visit_duration_hrs": 1.0,
        "travel_time_from_katra_hrs": 1.25,
        "travel_time_desc": "~48 km from Katra (~1.2 hrs by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 3,
        "suitability": "Ancient Shiva cave shrine with Ramayana ties overlooking the Tawi river in Jammu.",
        "estimated_transport_cost": "Free entry; local auto / cab (Estimated)",
        "cost_type": "estimated_local",
    },
    "Mansar Lake": {
        "region": "jammu_city",
        "base_hub": "Jammu Outer Circuit",
        "visit_duration_hrs": 2.0,
        "travel_time_from_katra_hrs": 2.25,
        "travel_time_desc": "~60 km from Jammu / ~90 km from Katra (~2-2.5 hrs)",
        "exertion_level": "Light",
        "min_trip_days_required": 4,
        "suitability": "Sacred lake ringed by hills and temples with boating; best on an extended 4+ day itinerary.",
        "estimated_transport_cost": "Full-day cab ₹2,200-3,200 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Shiv Khori": {
        "region": "distant_excursion",
        "base_hub": "Ransoo / Reasi",
        "visit_duration_hrs": 3.0,
        "travel_time_from_katra_hrs": 3.0,
        "travel_time_desc": "~80 km from Katra (~2.5-3 hrs each way via winding hill roads)",
        "exertion_level": "High",
        "min_trip_days_required": 5,
        "suitability": "Sacred natural limestone cave shrine with 3 km walk from Ransoo base; requires a dedicated day following post-trek recovery on trips of 5+ days.",
        "estimated_transport_cost": "Full-day taxi hire approx. ₹2,500-3,800 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Patnitop": {
        "region": "distant_excursion",
        "base_hub": "Patnitop / Ramban",
        "visit_duration_hrs": 4.0,
        "travel_time_from_katra_hrs": 3.5,
        "travel_time_desc": "~85 km from Katra / ~112 km from Jammu (~3-3.5 hrs mountain drive each way, ~7 hrs roundtrip)",
        "exertion_level": "Moderate",
        "min_trip_days_required": 5,
        "suitability": "Premier Himalayan hill resort with pine meadows and panoramic Chenab valley views; requires a full dedicated day following post-trek recovery on trips of 5+ days.",
        "estimated_transport_cost": "Full-day hill taxi hire approx. ₹3,000-4,500 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Sanasar": {
        "region": "distant_excursion",
        "base_hub": "Patnitop / Sanasar",
        "visit_duration_hrs": 3.0,
        "travel_time_from_katra_hrs": 4.0,
        "travel_time_desc": "~20 km beyond Patnitop (~3.5-4 hrs from Katra each way)",
        "exertion_level": "Moderate",
        "min_trip_days_required": 5,
        "suitability": "Scenic cup-shaped alpine meadow for eco-tourism and paragliding near Patnitop; requires a dedicated day following post-trek recovery on trips of 5+ days.",
        "estimated_transport_cost": "Full-day hill cab combined with Patnitop approx. ₹3,500-5,000 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Srinagar (Dal Lake & Gardens)": {
        "region": "kashmir",
        "base_hub": "Srinagar, Kashmir",
        "visit_duration_hrs": 5.0,
        "travel_time_from_katra_hrs": 7.0,
        "travel_time_desc": "~290 km from Jammu (~6-7 hrs via NH-44 tunnel corridor or direct flight)",
        "exertion_level": "Light",
        "min_trip_days_required": 6,
        "suitability": "Summer capital of J&K with iconic Dal Lake shikaras and royal Mughal gardens; requires a multi-day Kashmir extension (6+ days).",
        "estimated_transport_cost": "Flight or private cab ₹5,000-8,000+ (Estimated)",
        "cost_type": "estimated_local",
    },
    "Gulmarg (Snow Meadow)": {
        "region": "kashmir",
        "base_hub": "Gulmarg, Kashmir",
        "visit_duration_hrs": 4.0,
        "travel_time_from_katra_hrs": 8.0,
        "travel_time_desc": "~60 km from Srinagar (~1.5-2 hrs onward drive)",
        "exertion_level": "Moderate",
        "min_trip_days_required": 6,
        "suitability": "Alpine snow meadow and world-class gondola cable car; requires a multi-day Kashmir tour.",
        "estimated_transport_cost": "Gondola ₹740-950 verified; cab from Srinagar ₹2,000-3,000 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Pahalgam (Valley of Shepherds)": {
        "region": "kashmir",
        "base_hub": "Pahalgam, Kashmir",
        "visit_duration_hrs": 4.0,
        "travel_time_from_katra_hrs": 8.0,
        "travel_time_desc": "~90 km from Srinagar (~2-2.5 hrs onward drive)",
        "exertion_level": "Moderate",
        "min_trip_days_required": 6,
        "suitability": "Scenic Lidder river valley, pine forests, and Betaab Valley; requires a multi-day Kashmir tour.",
        "estimated_transport_cost": "Cab from Srinagar approx. ₹2,500-3,500 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Sonamarg (Meadow of Gold)": {
        "region": "kashmir",
        "base_hub": "Sonamarg, Kashmir",
        "visit_duration_hrs": 4.0,
        "travel_time_from_katra_hrs": 8.5,
        "travel_time_desc": "~80 km from Srinagar (~2.5 hrs onward along NH-1)",
        "exertion_level": "Moderate",
        "min_trip_days_required": 6,
        "suitability": "Gateway to Thajiwas Glacier and Sindh valley; requires a dedicated Kashmir tour.",
        "estimated_transport_cost": "Cab from Srinagar approx. ₹2,800-3,800 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Shankaracharya Temple, Srinagar": {
        "region": "kashmir",
        "base_hub": "Srinagar, Kashmir",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 7.0,
        "travel_time_desc": "Hilltop within Srinagar city overlooking Dal Lake",
        "exertion_level": "Moderate",
        "min_trip_days_required": 6,
        "suitability": "Ancient hilltop temple to Shiva consecrated by Adi Shankaracharya; requires Kashmir base.",
        "estimated_transport_cost": "Local Srinagar auto/cab (Estimated)",
        "cost_type": "estimated_local",
    },
    "Kheer Bhawani Temple, Tulmulla": {
        "region": "kashmir",
        "base_hub": "Ganderbal, Kashmir",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 7.5,
        "travel_time_desc": "~25 km from Srinagar (~45 mins by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 6,
        "suitability": "Sacred spring shrine deeply venerated by Kashmiri Pandits; requires Kashmir base.",
        "estimated_transport_cost": "Cab from Srinagar approx. ₹1,200-1,800 (Estimated)",
        "cost_type": "estimated_local",
    },
    "Verinag Spring and Mughal Garden": {
        "region": "kashmir",
        "base_hub": "Anantnag, Kashmir",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 5.5,
        "travel_time_desc": "~78 km south of Srinagar along Jammu-Srinagar corridor",
        "exertion_level": "Light",
        "min_trip_days_required": 5,
        "suitability": "Historic octagonal source of Jhelum River and Mughal garden; en route to Kashmir valley.",
        "estimated_transport_cost": "Entry ₹20; highway cab stop (Estimated)",
        "cost_type": "estimated_local",
    },
    "Achabal Mughal Garden": {
        "region": "kashmir",
        "base_hub": "Anantnag, Kashmir",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 6.5,
        "travel_time_desc": "~58 km from Srinagar (~1.5 hrs by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 6,
        "suitability": "Royal pleasure retreat designed by Empress Noor Jahan with stepped water cascades.",
        "estimated_transport_cost": "Entry ₹20; cab from Srinagar (Estimated)",
        "cost_type": "estimated_local",
    },
    "Martand Sun Temple, Mattan": {
        "region": "kashmir",
        "base_hub": "Anantnag, Kashmir",
        "visit_duration_hrs": 1.5,
        "travel_time_from_katra_hrs": 6.5,
        "travel_time_desc": "~64 km from Srinagar (~1.5-2 hrs by road)",
        "exertion_level": "Light",
        "min_trip_days_required": 6,
        "suitability": "8th-century grand stone temple ruins showcasing ancient Kashmiri Hindu architecture.",
        "estimated_transport_cost": "Free entry; cab from Srinagar (Estimated)",
        "cost_type": "estimated_local",
    },
    "Sinthan Top": {
        "region": "kashmir",
        "base_hub": "Kishtwar / Anantnag",
        "visit_duration_hrs": 2.5,
        "travel_time_from_katra_hrs": 7.5,
        "travel_time_desc": "~115 km from Srinagar (3-4.5 hrs mountain pass road)",
        "exertion_level": "Moderate",
        "min_trip_days_required": 6,
        "suitability": "High-altitude mountain pass (12,500 ft) connecting South Kashmir to Kishtwar.",
        "estimated_transport_cost": "SUV hire required (Estimated)",
        "cost_type": "estimated_local",
    },
    "Kashmir Valley": {
        "region": "kashmir",
        "base_hub": "Kashmir Region",
        "visit_duration_hrs": 8.0,
        "travel_time_from_katra_hrs": 7.0,
        "travel_time_desc": "~290 km from Jammu via NH-44 or flight",
        "exertion_level": "Light",
        "min_trip_days_required": 6,
        "suitability": "Encompasses Srinagar, Gulmarg, and Pahalgam; requires a multi-day Kashmir holiday.",
        "estimated_transport_cost": "Varies by circuit (Estimated)",
        "cost_type": "estimated_local",
    },
}


class ItineraryList(list):
    """Subclass of list that carries itinerary feasibility metadata while preserving full list semantics."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.infeasible_places = []
        self.feasible_places = []


def _fmt_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%a, %d %b %Y")
    except Exception:
        return str(d)


def get_destination_logistics(place_name: str) -> dict:
    if not place_name:
        return None
    canonical = match_place_name(place_name)
    if canonical and canonical in DESTINATION_LOGISTICS:
        return DESTINATION_LOGISTICS[canonical]
    if place_name in DESTINATION_LOGISTICS:
        return DESTINATION_LOGISTICS[place_name]
    return None


def evaluate_sightseeing_feasibility(places: list, duration_days: int, pace: str = "balanced") -> dict:
    """
    Deterministically evaluates whether selected sightseeing destinations
    realistically fit within the given trip duration and pacing constraints.
    Returns: {"feasible": [str, ...], "infeasible": [{"place": str, "reason": str, "suggestion": str}, ...]}
    """
    feasible = []
    infeasible = []
    dur = max(1, duration_days or 4)
    pace_lower = (pace or "balanced").lower()

    # Number of available non-departure sightseeing days (Day 3 to N-1)
    available_sightseeing_days = max(0, dur - 3) if dur >= 4 else 0

    # Max off-trek places allowed based on available days and pace
    if pace_lower == "relaxed":
        max_per_day = 1
    elif pace_lower == "packed":
        max_per_day = 2
    else:  # balanced
        max_per_day = 1 if available_sightseeing_days <= 1 else 2

    max_capacity = available_sightseeing_days * max_per_day

    for raw_p in places or []:
        logistics = get_destination_logistics(raw_p)
        canonical = match_place_name(raw_p) or (raw_p if logistics else None)

        # 1. Reject uncatalogued / ungrounded destinations
        if not logistics or not canonical:
            r_text = (
                f"'{raw_p}' could not be verified against the supported Jammu & Kashmir destination catalogue."
            )
            s_text = (
                "Please select a verified pilgrimage shrine or supported destination from the catalogue "
                "(e.g., Baba Dhansar, Nau Devi Cave Temple, Patnitop, Shiv Khori)."
            )
            infeasible.append({"place": raw_p, "reason": r_text, "suggestion": s_text})
            continue

        region = logistics.get("region", "katra_nearby")
        min_days = logistics.get("min_trip_days_required", 3)

        # 2. Trek route shrines (Bhairavnath, Ardhkuwari, etc.) are visited during the Day 2 holy trek
        if region == "trek_route":
            if dur < 2:
                r_text = f"{canonical} is on the sacred trek route and requires at least a 2-day trip."
                s_text = "Extend your trip duration to at least 2 days."
                infeasible.append({"place": canonical, "reason": r_text, "suggestion": s_text})
            else:
                if canonical not in feasible:
                    feasible.append(canonical)
            continue

        # 3. Off-trek destinations require an intermediate non-departure day
        if available_sightseeing_days == 0:
            if region == "distant_excursion":
                r_text = (
                    f"{canonical} is ~85 km from Katra and requires a ~7-hour roundtrip mountain road drive. "
                    f"On a {dur}-day trip, Day 1 is arrival & registration, Day 2 is the 26 km Vaishno Devi trek, "
                    f"and Day {dur} is departure. Scheduling {canonical} would cause severe physical exhaustion "
                    f"and risks missing your departure transport."
                )
                s_text = (
                    f"Consider extending your trip to at least {min_days} days to enjoy a dedicated {canonical} day trip, "
                    "or visit nearby Baba Dhansar (~30 mins from Katra) on your recovery day instead."
                )
            elif region == "kashmir":
                r_text = (
                    f"Kashmir Valley destinations like {canonical} are ~290 km from Jammu (6–7 hours by road) "
                    "and require a dedicated 6+ day holiday based in Srinagar, not a short Katra pilgrimage."
                )
                s_text = "Focus this sacred trip on Katra and Jammu shrines, and plan Kashmir as a separate extended itinerary."
            else:
                r_text = (
                    f"A {dur}-day trip reserves Day 1 for arrival and Katra registration, Day 2 for the holy 26 km Vaishno Devi trek, "
                    f"and Day {dur} for departure. There are no intermediate days available to visit {canonical}. "
                    f"A trip duration of at least 4 days is required to include off-trek sightseeing."
                )
                s_text = (
                    f"Consider extending your trip to at least 4 days to visit {canonical}, "
                    "or focus this 3-day trip on the holy trek shrines (Ardhkuwari Cave and Bhairavnath Temple)."
                )
            infeasible.append({"place": canonical, "reason": r_text, "suggestion": s_text})
            continue

        # 4. Check trip duration constraint for distant/demanding excursions
        if dur < min_days:
            if region == "distant_excursion":
                r_text = (
                    f"{canonical} is ~85 km from Katra and requires a ~7-hour roundtrip mountain road drive. "
                    f"On a {dur}-day trip, Day 1 is arrival & registration, Day 2 is the 26 km Vaishno Devi trek, "
                    f"Day 3 is reserved for essential post-trek muscle recovery, and Day {dur} is departure. "
                    f"Scheduling {canonical} would cause severe physical exhaustion and violate post-trek recovery. "
                    f"A trip duration of at least {min_days} days is required to schedule {canonical} on a dedicated day after recovery."
                )
                s_text = (
                    f"Consider extending your trip to at least {min_days} days to enjoy a dedicated {canonical} day trip, "
                    "or visit nearby Baba Dhansar (~30 mins from Katra) on your recovery day instead."
                )
            elif region == "kashmir":
                r_text = (
                    f"Kashmir Valley destinations like {canonical} are ~290 km from Jammu (6–7 hours by road) "
                    "and require a dedicated 6+ day holiday based in Srinagar, not a short Katra pilgrimage."
                )
                s_text = "Focus this sacred trip on Katra and Jammu shrines, and plan Kashmir as a separate extended itinerary."
            else:
                r_text = (
                    f"{canonical} requires at least a {min_days}-day itinerary to ensure adequate time for "
                    "both the core pilgrimage darshan and return transit."
                )
                s_text = f"Extend your trip duration to {min_days} days or choose local Katra shrines."

            infeasible.append({"place": canonical, "reason": r_text, "suggestion": s_text})
            continue

        # 5. Check daily capacity constraint for off-trek places
        off_trek_feasible = [p for p in feasible if get_destination_logistics(p) and get_destination_logistics(p).get("region") != "trek_route"]
        if len(off_trek_feasible) >= max_capacity:
            r_text = (
                f"Your selected pace is '{pace_lower.capitalize()}'. To maintain essential rest buffers after the "
                f"high-exertion trek, the schedule allows a maximum of {max_capacity} additional sightseeing spot{'s' if max_capacity > 1 else ''} "
                f"across your {available_sightseeing_days} available intermediate day{'s' if available_sightseeing_days > 1 else ''}."
            )
            s_text = f"Remove one of your earlier selected places or extend your trip duration to accommodate {canonical}."
            infeasible.append({"place": canonical, "reason": r_text, "suggestion": s_text})
            continue

        if canonical not in feasible:
            feasible.append(canonical)

    return {"feasible": feasible, "infeasible": infeasible}


def build_itinerary(option, hotel=None, hotel_nights=0, sightseeing_places=None, request=None):
    """
    Builds a realistic, deterministic day-wise itinerary list matching exact trip duration.
    Enforces:
    1. Exactly N days for an N-day trip (never N+1 or N-1).
    2. Day 2 is dedicated exclusively to the high-exertion Vaishno Devi trek & darshan.
       No Patnitop or distant excursions are scheduled on Day 2.
    3. Day 3 preserves post-trek recovery time when duration permits (N >= 4).
    4. Distant excursions (Patnitop, Shiv Khori) require N >= 4 and conservative travel estimates.
    5. Infeasible places are identified and explained in metadata.
    """
    tr = option.get("transport") or option.get("flight") or {}
    s = option.get("slot") or {"category": "Normal Darshan", "slot_time": "12:00 PM", "slot_date": tr.get("travel_date", "")}
    req = request or {}

    duration = req.get("duration_days")
    if not duration:
        base_days = 2 + (1 if sightseeing_places else 0) + (1 if hotel or hotel_nights else 0)
        duration = max(3, base_days)
    duration = int(duration)

    travel_date = tr.get("travel_date") or req.get("start_date") or datetime.now().strftime("%Y-%m-%d")
    origin = tr.get("origin") or req.get("origin") or "Delhi"
    mode = (tr.get("mode") or req.get("mode") or "train").lower()
    operator = tr.get("operator") or ("Northern Railways" if mode == "train" else "Air Carrier")
    transport_no = tr.get("transport_no", "")
    dep_time = tr.get("departure_time") or "06:00 AM"
    pace = req.get("travel_style") or "balanced"

    hotel_name = hotel.get("name", "Certified Katra Hotel") if hotel else "Katra Pilgrim Guesthouse"
    hotel_cat = hotel.get("category", "Standard") if hotel else "Standard"

    try:
        start_dt = datetime.strptime(travel_date, "%Y-%m-%d")
    except Exception:
        start_dt = datetime.now()

    # Feasibility evaluation
    raw_sightseeing = list(sightseeing_places or [])
    feasibility = evaluate_sightseeing_feasibility(raw_sightseeing, duration, pace=pace)
    feasible_places = feasibility["feasible"]
    infeasible_places = feasibility["infeasible"]

    sight_choice = (req.get("sightseeing_choice") or "").lower()

    # Recommended fallback if user provided no places and did not choose "later"
    if not feasible_places and not raw_sightseeing and (sight_choice != "later"):
        if duration <= 3:
            recommended_default = []
        elif duration == 4:
            recommended_default = ["Baba Dhansar"]
        else:
            recommended_default = ["Baba Dhansar", "Patnitop"]
        for p in recommended_default:
            if p not in feasible_places:
                feasible_places.append(p)

    days = ItineraryList()
    days.infeasible_places = infeasible_places
    days.feasible_places = feasible_places

    # -------------------------------------------------------------------------
    # DAY 1: Arrival, Base Orientation & Yatra Registration
    # -------------------------------------------------------------------------
    day1_date_str = _fmt_date(start_dt.strftime("%Y-%m-%d"))
    if mode == "flight":
        t_summary = f"Fly with {operator} ({transport_no}) departing at {dep_time} from {origin} to Jammu Airport"
        t_transfer = "Scenic taxi transfer from Jammu Airport to Katra base town (~1.5–2 hrs via NH-44)"
        t_time = "~1.5–2 hrs road transfer from Jammu"
        t_cost = "₹1,300–2,500 private cab (Estimated)"
    else:
        t_summary = f"Travel by Train via {operator} ({transport_no}) departing at {dep_time} from {origin} to Shri Mata Vaishno Devi Katra"
        t_transfer = "Direct arrival at Shri Mata Vaishno Devi Katra railway station and transfer to hotel"
        t_time = "~15–20 mins local transfer to Katra hotel"
        t_cost = "Included in train ticket; local auto ₹100–150"

    day1_activities = [
        f"10:00 AM – 01:30 PM: {t_summary}",
        f"01:30 PM – 03:00 PM: {t_transfer} and check-in at {hotel_name} ({hotel_cat})",
        "03:30 PM – 05:00 PM: Obtain mandatory Yatra RFID Registration Card at Katra Yatra Registration Counter",
        "05:30 PM – 07:30 PM: Evening Katra market stroll (dry fruits, prasad) & orientation",
        "08:00 PM – Onward: Early dinner and overnight rest in Katra to prepare for tomorrow's holy trek",
    ]

    days.append({
        "day_number": 1,
        "date": day1_date_str,
        "title": "Arrival, Base Orientation & Yatra Registration",
        "base_location": "Katra Base Town",
        "exertion_level": "Light",
        "activities": day1_activities,
        "rest_buffers": "1.5 hrs post-arrival rest and orientation buffer",
        "travel_time_est": t_time,
        "travel_cost_est": t_cost,
        "booking_notes": "Mandatory Yatra RFID Registration Card must be collected in person at Katra counters before beginning the trek.",
        "practicality_note": "Ensures comfortable arrival, hotel check-in, mandatory RFID slip registration, and early overnight rest before tomorrow's trek.",
    })

    # -------------------------------------------------------------------------
    # DAY 2: Dedicated Holy Yatra & Darshan Trek (High Exertion)
    # -------------------------------------------------------------------------
    day2_dt = start_dt + timedelta(days=1)
    day2_date_str = _fmt_date(day2_dt.strftime("%Y-%m-%d"))
    slot_cat = s.get("category", "Normal Darshan")
    slot_time = s.get("slot_time", "12:00 PM")

    if slot_cat == "Helicopter Darshan":
        trek_desc = "07:30 AM – 08:30 AM: Helicopter flight from Katra helipad to Sanjichhat (approx. 8 mins), followed by a gentle 2.5 km walk to Bhawan"
        trek_descent = "03:30 PM – 05:00 PM: Return flight via Sanjichhat helipad to Katra base"
    else:
        trek_desc = "05:30 AM – 06:30 AM: Early morning trek departure from Katra base via Ban Ganga / Tarakote Marg (13 km ascent)"
        trek_descent = "04:30 PM – 08:30 PM: Scenic descent back to Katra base town and overnight muscle recovery"

    day2_activities = [
        trek_desc,
        "08:00 AM – 09:30 AM: En route darshan pause at Charan Paduka & Ardhkuwari Cave (Garbh Joon)",
        f"11:00 AM – 01:30 PM: Sacred Darshan of Maa Vaishno Devi Ji at Holy Bhawan ({slot_cat} at {slot_time})",
        "02:00 PM – 03:30 PM: Ascent to Bhairavnath Temple via ropeway / uphill trek (completes the pilgrimage)",
        trek_descent,
    ]

    days.append({
        "day_number": 2,
        "date": day2_date_str,
        "title": "Dedicated Holy Yatra & Darshan Trek",
        "base_location": "Katra ➔ Shri Mata Vaishno Devi Bhawan",
        "exertion_level": "High",
        "activities": day2_activities,
        "rest_buffers": "Mid-trek rest intervals at Himkoti & Sanjichhat; overnight recovery following descent",
        "travel_time_est": "5–7 hrs ascent on foot (or 8 mins by helicopter); 4–5 hrs return descent",
        "travel_cost_est": "Free trek on foot; ropeway to Bhairavnath ₹100 verified ticket",
        "booking_notes": "Keep RFID card accessible for barcode scanning at Ban Ganga, Ardhkuwari, and Bhawan checkpoints.",
        "practicality_note": "Vaishno Devi trek is a physically demanding 13 km ascent + descent requiring a full dedicated day with zero conflicting travel or distant excursions.",
    })

    # -------------------------------------------------------------------------
    # INTERMEDIATE DAYS: Day 3 to Day (duration - 1)
    # -------------------------------------------------------------------------
    recovery_places = []
    excursion_places = []

    for fp in feasible_places:
        p_log = get_destination_logistics(fp) or {}
        reg = p_log.get("region", "katra_nearby")
        ex = p_log.get("exertion_level", "Light")
        if reg == "trek_route":
            pass  # Handled as sacred en-route shrines on Day 2
        elif reg in ("katra_nearby", "jammu_city") and ex == "Light":
            recovery_places.append(fp)
        else:
            excursion_places.append(fp)

    for d in range(3, duration):
        day_dt = start_dt + timedelta(days=d - 1)
        day_date_str = _fmt_date(day_dt.strftime("%Y-%m-%d"))

        # Day 3 is Post-Trek Recovery Day (STRICTLY PROTECTED FOR GENTLE ACTIVITIES)
        # Demanding excursions like Patnitop, Sanasar, Shiv Khori are NEVER scheduled on Day 3!
        if d == 3:
            if recovery_places:
                chosen_place = recovery_places.pop(0)
                p_log = get_destination_logistics(chosen_place) or {}
                # Check if a second gentle recovery place can be combined on Day 3 (e.g. 4-day trip with 2 local spots)
                second_place = recovery_places.pop(0) if (recovery_places and (duration <= 4) and pace != "relaxed") else None
                p_log2 = get_destination_logistics(second_place) if second_place else None

                day3_title = f"Post-Trek Recovery & Local Sightseeing ({chosen_place}{f' & {second_place}' if second_place else ''})"
                day3_base = "Katra Base Town"
                day3_exertion = "Light"
                day3_travel_time = p_log.get("travel_time_desc", "~30-35 mins by road")
                day3_cost = p_log.get("estimated_transport_cost", "Local taxi approx. ₹600-1,000 roundtrip (Estimated)")
                day3_note = "Provides vital post-trek physical recovery with a relaxed morning wake-up and low-impact afternoon nature/temple visits."

                if second_place:
                    day3_acts = [
                        "09:00 AM – 11:30 AM: Leisure breakfast, sleep-in, and foot muscle recovery at hotel",
                        f"12:30 PM – 03:00 PM: Afternoon gentle excursion to {chosen_place} ({day3_travel_time})",
                        f"03:30 PM – 05:30 PM: Short visit to {second_place} ({p_log2.get('travel_time_desc', 'Local Katra area')})",
                        "06:30 PM – 08:00 PM: Local Katra market stroll for walnuts, saffron, and yatra souvenirs",
                        "08:30 PM – 09:30 PM: Traditional Dogra dinner in Katra town",
                    ]
                else:
                    day3_acts = [
                        "09:00 AM – 11:30 AM: Leisure breakfast, sleep-in, and foot muscle recovery at hotel",
                        f"12:30 PM – 03:30 PM: Afternoon gentle excursion to {chosen_place} ({day3_travel_time})",
                        "04:30 PM – 07:00 PM: Local Katra market stroll for walnuts, saffron, and yatra souvenirs",
                        "07:30 PM – 09:30 PM: Traditional Dogra dinner in Katra town",
                    ]
            else:
                day3_title = "Post-Trek Recovery & Katra Town Leisure"
                day3_base = "Katra Base Town"
                day3_exertion = "Light"
                day3_travel_time = "Local Katra town"
                day3_cost = "Local expenses only"
                if sight_choice == "later":
                    day3_note = "Provides vital post-trek physical recovery. Sightseeing options left open to decide locally upon arrival in Katra."
                else:
                    day3_note = "Provides vital post-trek physical recovery. Schedule kept open for muscle relaxation, temple visits, or local Katra bazaars."
                day3_acts = [
                    "09:00 AM – 11:30 AM: Leisure breakfast, sleep-in, and foot muscle recovery at hotel",
                    "12:30 PM – 03:30 PM: Relaxed afternoon in Katra town; explore local markets or rest at hotel",
                    "04:30 PM – 07:00 PM: Evening stroll at leisure in Katra town (optional local sightseeing)",
                    "07:30 PM – 09:30 PM: Traditional Dogra dinner in Katra town",
                ]

            days.append({
                "day_number": 3,
                "date": day_date_str,
                "title": day3_title,
                "base_location": day3_base,
                "exertion_level": day3_exertion,
                "activities": day3_acts,
                "rest_buffers": "Full morning sleep-in and recovery buffer",
                "travel_time_est": day3_travel_time,
                "travel_cost_est": day3_cost,
                "booking_notes": "Local taxi can be hired from Katra taxi stand or booked via hotel desk.",
                "practicality_note": day3_note,
            })

        else:
            # Day 4+ Excursion / Regional Circuit (Appropriate for demanding excursions like Patnitop)
            if excursion_places:
                chosen_place = excursion_places.pop(0)
                p_log = get_destination_logistics(chosen_place) or {}
                day_title = f"Regional Excursion — {chosen_place}"
                day_base = f"{chosen_place} Circuit"
                day_exertion = p_log.get("exertion_level", "Moderate")
                day_tt = p_log.get("travel_time_desc", "~3.5 hrs drive each way")
                day_cost = p_log.get("estimated_transport_cost", "Taxi hire (Estimated)")
                day_acts = [
                    f"07:30 AM – 11:00 AM: Scenic mountain drive to {chosen_place} ({day_tt})",
                    f"11:30 AM – 03:00 PM: Guided exploration of {chosen_place} meadows and viewpoints",
                    "03:30 PM – 06:30 PM: Scenic return journey to Katra / Jammu base",
                    "07:30 PM – 09:30 PM: Relaxed evening dining and next-day departure packing",
                ]
                day_note = f"Geographically clustered visit to {chosen_place} scheduled comfortably after post-trek recovery, leaving ample evening rest buffer before onward travel."
            elif recovery_places:
                chosen_place = recovery_places.pop(0)
                p_log = get_destination_logistics(chosen_place) or {}
                day_title = f"Local Sightseeing — {chosen_place}"
                day_base = "Katra Base Town"
                day_exertion = "Light"
                day_tt = p_log.get("travel_time_desc", "Local road transit")
                day_cost = p_log.get("estimated_transport_cost", "Local taxi (Estimated)")
                day_acts = [
                    f"09:30 AM – 11:00 AM: Transit to {chosen_place} ({day_tt})",
                    f"11:00 AM – 02:30 PM: Explore {chosen_place}",
                    "03:30 PM – 06:00 PM: Return to Katra town and local market exploration",
                    "07:30 PM – 09:30 PM: Dinner and rest",
                ]
                day_note = f"Relaxed visit to {chosen_place} with low exertion."
            else:
                day_title = f"Day {d}: Leisure & Optional Regional Sightseeing"
                day_base = "Katra / Local Base"
                day_exertion = "Light"
                day_acts = [
                    "09:00 AM – 12:00 PM: Relaxed morning at base hotel or local town exploration",
                    "12:30 PM – 04:00 PM: Free afternoon (optional excursions can be arranged locally)",
                    "05:00 PM – 07:30 PM: Evening stroll and shopping at local Katra/Jammu markets",
                    "08:00 PM – 09:30 PM: Dinner and rest",
                ]
                day_tt = "Local transit"
                day_cost = "Local expenses only"
                day_note = "Open leisure day allowing pilgrims to rest or book optional local sightseeing based on on-ground energy."

            days.append({
                "day_number": d,
                "date": day_date_str,
                "title": day_title,
                "base_location": day_base,
                "exertion_level": day_exertion,
                "activities": day_acts,
                "rest_buffers": "2 hrs evening relaxation buffer",
                "travel_time_est": day_tt,
                "travel_cost_est": day_cost,
                "booking_notes": "Check road and weather advisories locally for mountain routes.",
                "practicality_note": day_note,
            })

    # -------------------------------------------------------------------------
    # FINAL DAY: Check-out & Return Journey
    # -------------------------------------------------------------------------
    if duration >= 3:
        dep_dt = start_dt + timedelta(days=duration - 1)
        dep_date_str = _fmt_date(dep_dt.strftime("%Y-%m-%d"))

        if mode == "flight":
            dep_summary = f"Taxi transfer to Jammu Airport and return flight to {origin}"
            dep_time_est = "~1.5–2 hrs road transfer to Jammu Airport"
            dep_cost_est = "₹1,300–2,000 private sedan (Estimated)"
        else:
            dep_summary = f"Transfer to Katra Railway Station and return journey to {origin} by Train"
            dep_time_est = "15–20 mins to Katra railway station"
            dep_cost_est = "Included in train ticket; local auto ₹100–150"

        days.append({
            "day_number": duration,
            "date": dep_date_str,
            "title": "Check-out & Return Journey",
            "base_location": f"Katra ➔ {origin}",
            "exertion_level": "Light",
            "activities": [
                f"08:30 AM – 10:30 AM: Leisure breakfast and hotel check-out at {hotel_name}",
                "11:00 AM – 01:00 PM: Last-minute Katra bazaar shopping (dry fruits, Mata prasad, devotional mementos)",
                f"01:30 PM – Onward: {dep_summary}",
            ],
            "rest_buffers": "2-hour departure transit buffer before scheduled boarding",
            "travel_time_est": dep_time_est,
            "travel_cost_est": dep_cost_est,
            "booking_notes": "Keep return train/flight tickets and valid government photo IDs handy for station/airport entry.",
            "practicality_note": "Structured with generous 2-hour departure buffer to ensure relaxed hotel checkout and on-time terminal check-in.",
        })

    return days


def format_itinerary_text(days):
    """Plain-text version, useful for chat display or a downloadable summary."""
    lines = []
    for d in days:
        ex = d.get("exertion_level", "Moderate")
        base = d.get("base_location", "Katra")
        lines.append(f"Day {d['day_number']} — {d['date']}: {d['title']} [Base: {base} | Exertion: {ex}]")
        if d.get("practicality_note"):
            lines.append(f"  💡 {d['practicality_note']}")
        for a in d["activities"]:
            lines.append(f"  • {a}")
        lines.append("")
    return "\n".join(lines).strip()


def generate_default_itinerary(request):
    """Generates a structured day-wise itinerary list matching request parameters."""
    req = request or {}
    duration = req.get("duration_days", 4) or 4
    origin = req.get("origin") or "Delhi"
    mode = (req.get("mode") or "train").lower()
    cat = req.get("category") or "Normal Darshan"
    start_date_str = req.get("start_date") or datetime.now().strftime("%Y-%m-%d")

    dummy_option = {
        "transport": {
            "origin": origin,
            "destination": "Katra",
            "mode": mode,
            "operator": "Northern Railways" if mode == "train" else "Air Carrier",
            "transport_no": "12425" if mode == "train" else "6E-204",
            "departure_time": "06:00 AM",
            "travel_date": start_date_str,
            "price": 850 if mode == "train" else 4200,
        },
        "slot": {
            "category": cat,
            "slot_time": "12:00 PM",
            "slot_date": start_date_str,
            "price": 0 if "normal" in cat.lower() else 500,
        },
    }

    return build_itinerary(
        dummy_option,
        hotel=None,
        hotel_nights=max(1, int(duration) - 1),
        sightseeing_places=req.get("sightseeing_places", []),
        request=req,
    )


def sync_itinerary_duration(itinerary, new_duration, request=None):
    """Synchronizes itinerary length when trip duration changes, strictly enforcing N days."""
    req = dict(request or {})
    req["duration_days"] = new_duration
    return generate_default_itinerary(req)



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
