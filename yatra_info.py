"""
yatra_info.py
Real, cross-checked pilgrim essentials for the Explore Katra tab's
"Yatra Essentials" section: aarti timings, registration process, route
options to Bhawan, packing guidance, free facilities, and the official
helpline. Informational only - nothing here is bookable through this app.

Sourcing notes (see README "Data Sources" for the full table):
- Aarti timings: directly from the Shrine Board's own live-darshan page
  (maavaishnodevi.org/live), cross-checked against independent pilgrim
  guides - all agree on the same figures.
- Registration process, route options, and the official helpline number
  are cross-checked across multiple independent pilgrim-guide sources
  and (for the helpline) news coverage.
- Packing/prohibited-items guidance is general pilgrimage-travel advice,
  not a verbatim official checklist - flagged as such below.
"""

AARTI_TIMINGS = {
    "morning": {"start": "6:20 AM", "end": "8:00 AM", "note": "Same year-round."},
    "evening_summer": {"start": "7:20 PM", "end": "8:30 PM", "note": "April-September."},
    "evening_winter": {"start": "6:20 PM", "end": "8:00 PM", "note": "October-March."},
    "general_note": (
        "Darshan is open 24x7 otherwise, but pauses completely during these Aarti "
        "windows - plan around them rather than arriving right at these times."
    ),
}

REGISTRATION_INFO = {
    "cost": "Free (Yatra Slip / Yatra Parchi)",
    "mandatory": True,
    "mandatory_note": "Required for every pilgrim, without exception - even if you've booked a helicopter or battery-vehicle ticket.",
    "how_to_register": [
        "Online, in advance, at the official Shrine Board site (maavaishnodevi.org) - use only this official domain, never a third-party agent.",
        "Offline, on arrival, at 24x7 registration counters at Katra Chowk (main market) or Katra railway station.",
        "On-the-spot, if starting via Tarakote Marg - there's a registration counter right at that route's starting point.",
    ],
    "what_youll_need": [
        "A valid mobile number and email address",
        "A government-issued photo ID (Aadhaar, passport, or voter ID) - carry the same physical ID during the yatra",
        "Basic details for each pilgrim in the group (name, age, gender, city/state)",
    ],
    "reminder": "Carry a printed or digital copy of your Yatra Slip at all times during the yatra - it's checked at multiple points along the route.",
}

ROUTE_OPTIONS = [
    {
        "name": "Traditional trek route",
        "path": "Katra -> Banganga -> Charan Paduka -> Ardhkuwari -> Sanjichhat -> Bhairon Ghati -> Bhawan",
        "distance": "~13 km",
        "duration": "Commonly 5-9 hours one-way, depending on pace and rest stops",
        "notes": "Ponies, palanquins (palki), and pithoos (porters) are available on this route for those who need assistance.",
    },
    {
        "name": "Tarakote Marg (newer route)",
        "path": "Katra -> Tarakote Marg -> Adhkuwari -> Himkoti -> Bhawan",
        "distance": "~14 km",
        "duration": "Similar to the traditional route, often described as a gentler gradient",
        "notes": "Ponies and palanquins are not permitted here; it's a quieter, less-crowded, pedestrian-only alternative, with battery-operated vehicles available on part of the Adhkuwari-Bhawan stretch.",
    },
    {
        "name": "Helicopter",
        "path": "Katra helipad -> Sanjichhat (then a short walk to Bhawan)",
        "distance": "~2.5 km walk after landing",
        "duration": "~8-minute flight",
        "notes": "Book online up to 60 days ahead at the official Shrine Board site. Carry valid photo ID, address proof, and the card used for payment - boarding can be denied without these. The Yatra Slip is still mandatory even for helicopter passengers.",
    },
]

FACILITIES = [
    {"name": "Langar (free community kitchens)", "note": "Available at multiple points along the route, including near Banganga and on Tarakote Marg."},
    {"name": "Medical centers", "note": "Positioned at intervals along the trek route for pilgrim health emergencies."},
    {"name": "Battery-operated vehicles", "note": "Available on part of the route (mainly the Adhkuwari-Himkoti-Bhawan stretch) for those who need it."},
    {"name": "Bhairon Baba ropeway", "note": "An ~8-minute ropeway connects Bhawan to the Bhairon Baba temple, an alternative to the walking trek most pilgrims take after darshan."},
]

PACKING_GUIDANCE = {
    "disclaimer": "General pilgrimage-travel guidance, not a verbatim official checklist from the Shrine Board.",
    "recommended": [
        "Comfortable, broken-in walking shoes (the trek is long, regardless of route)",
        "A light woolen layer even in summer - it gets cool at altitude, especially at night",
        "A raincoat or poncho during the monsoon months",
        "Your printed/digital Yatra Slip and original photo ID",
        "A refillable water bottle and any personal medicines",
        "Sunscreen and a cap for daytime sun exposure on the trek",
    ],
    "commonly_restricted": [
        "Alcohol and tobacco products",
        "Non-vegetarian food",
        "Weapons or sharp objects",
        "Drones, without prior permission",
    ],
}

HELPLINE = {
    "official_yatra_helpline": "1800-180-7198",
    "note": "Official Shrine Board (SMVDSB) toll-free helpline for yatra-related queries.",
}


def get_aarti_timings():
    return AARTI_TIMINGS


def get_registration_info():
    return REGISTRATION_INFO


def get_route_options():
    return ROUTE_OPTIONS


def get_facilities():
    return FACILITIES


def get_packing_guidance():
    return PACKING_GUIDANCE


def get_helpline():
    return HELPLINE
