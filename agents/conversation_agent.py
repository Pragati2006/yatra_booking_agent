"""
agents/conversation_agent.py
Handles understanding the pilgrim's free-text message (in whatever
language they write in) and generating warm, culturally appropriate
replies. This is the "front door" agent other agents don't talk to
directly - the Coordinator calls it first to understand intent, and
last to phrase the final reply.

Two modes:
  - LLM-powered (if ANTHROPIC_API_KEY is set): uses Claude, which can
    genuinely read/respond in Hindi, Hinglish, English, or other
    languages the pilgrim writes in, and naturally weaves in respectful
    devotional phrasing.
  - Rule-based fallback (no key needed): reuses the existing, tested
    regex-based extraction from agent.py, and uses a small template
    bank for devotional phrasing. Always English in this mode - honest
    limitation, not a fake multilingual claim.
"""

import json
import os
import random
import re

import agent as legacy_agent  # the existing, tested transport/darshan parsing + ranking logic

# ---------------------------------------------------------------------------
# Intent Detection — rule-based, no API key required
# ---------------------------------------------------------------------------

# Signals that a message is CLEARLY a tourism/info question and NOT a booking
_TOURISM_QUESTION_PATTERNS = [
    r"\bwhat\b.{0,60}\b(place|places|visit|see|explore|history|about|temple|fort|lake|cave|trek|route|timing|timings|pack|packing|bring|carry|register|registration|aarti|facility|facilities|guide|tips|advice|info|information|weather|distance|know|helpline|contact|steps|do|see)\b",
    r"\btell me\b.{0,50}\b(about|history|heritage|timing|route|place|site|temple|cave|fort|trek|more)\b",
    r"\bhow\b.{0,40}\b(reach|get|go|visit|register|trek|climb|pack|far)\b",
    r"\bwhere\b.{0,40}\b(is|are|can i|should i|to visit|to see|to go|to trek)\b",
    r"\b(history|historical|heritage|mythology|legend|background|significance)\b",
    r"\b(aarti|aarthi)\s*timings?\b",
    r"\b(packing|what to pack|what to bring|what to carry|what to wear|should i pack|should we pack)\b",
    r"\b(yatra registration|yatra parchi|yatra slip|how to register|registration steps)\b",
    r"\b(trek route|which route|how to reach bhawan)\b",
    r"\b(nearby places|places to see|places to visit|tourist spots|sightseeing spots)\b",
    r"\b(bhairavnath|ardhkuwari|charan paduka|ban ganga|shiv khori|patnitop|sanasar|mansar|bahu fort|amar mahal|raghunath|peer kho|himkoti|baba dhansar|jhajjar kotli|nau devi)\b",
    r"\b(vaishno devi history|vaishno devi significance|vaishno devi legend|about vaishno devi)\b",
    r"\b(how far|what (can|to) (i|we) do|tell me more|how to reach|how do i reach|what is the distance|where is it|where located|tell me about it)\b",
]

# Words after "from" that are destinations or grammar, not origin cities.
_FROM_ORIGIN_STOPWORDS = {
    "the", "a", "an", "my", "our", "here", "there", "home", "katra", "jammu",
    "bhawan", "next", "this", "last", "for", "with", "by", "in", "during",
    "and", "to", "or", "there", "here",
}

# Signals that are STRONG booking/planning intent — override tourism detection
_TRIP_PLANNING_PATTERNS = [
    r"\b(\d+)\s*(people|pax|person|persons|members|pilgrims)\b",
    r"\b(book|booking|reserve|reservation)\b",
    r"\b(find|search|look for|check|get me)\b.{0,30}\b(flight|train|bus|travel|transport|darshan slot|options)\b",
    r"\b(vip darshan|helicopter darshan|normal darshan)\b",
    r"\b(travelling|traveling|trip to|going to|plan.*yatra|i want.*travel|i want.*darshan)\b",
    r"\b(proceed|confirm|authorise|authorize|complete booking)\b",
]


_ITINERARY_PATTERNS = [
    r"\b(show|view|see|display|what am i doing|tell me about|what is on|what's on)\b.{0,30}\b(itinerary|day\s*\d+|schedule)\b",
    r"\bday\s*\d+\b",
    r"\b(move|shift|transfer)\b.{0,40}\b(to day\s*\d+|day\s*\d+)\b",
    r"\b(add|put|include)\b.{0,40}\b(on day\s*\d+|to day\s*\d+|day\s*\d+)\b",
    r"\b(remove|delete|drop|take out)\b.{0,40}\b(from day\s*\d+|day\s*\d+)\b",
    r"\b(replace|swap)\b.{0,40}\bwith\b",
    r"\b(add a rest day|make day\s*\d+.*rest|rest day)\b",
    r"\b(make day\s*\d+.*(relaxed|devotional|packed|sightseeing)|change day\s*\d+)\b",
    r"\bmove (that|it) to day\s*\d+\b",
    r"\b(show my itinerary|show itinerary|view itinerary|my itinerary)\b",
]


def _has_trip_origin_phrase(text_lower):
    """True when the pilgrim names a departure city, regardless of capitalization.
    Ignores destination words such as Katra/Jammu so tourism questions are not
    misread as booking requests."""
    m = re.search(
        r"\b(?:from|out of|leaving|travelling from|traveling from|departing from|starting from)\s+([a-z]+(?:\s+[a-z]+)?)",
        text_lower,
    )
    if not m:
        return False
    words = m.group(1).split()
    clean = []
    for w in words:
        if w in _FROM_ORIGIN_STOPWORDS:
            break
        clean.append(w)
    return bool(clean) and len("".join(clean)) >= 3


_WEATHER_PATTERNS = [
    r"\b(weather|temperature|forecast|climate|how cold|is it raining|rain forecast|snow in katra|what to wear for weather|weather in katra)\b",
]

_BOOKING_PATTERNS = [
    r"\b(book option \d+|confirm booking|proceed with booking|execute rpa|authorize booking|confirm my option|book this option|yes,?\s*proceed|yes,?\s*confirm|confirm trip|proceed)\b",
]


def detect_intent(user_text):
    """Classifies the pilgrim's message into one of:
      - 'BOOKING'       : booking execution / confirmation request
      - 'WEATHER'       : weather forecast or climate guidance question
      - 'ITINERARY'     : day-by-day itinerary view or modification request
      - 'TOURISM'       : informational/tourism question — do NOT start booking flow
      - 'TRIP_PLANNING' : booking/travel search request
      - 'UNKNOWN'       : ambiguous; default to TRIP_PLANNING to preserve existing behaviour
    """
    t = (user_text or "").strip()
    tl = t.lower()

    # 1. Check for booking confirmation/execution intent first
    for pat in _BOOKING_PATTERNS:
        if re.search(pat, tl):
            return "BOOKING"

    # 2. Check for weather intent
    for pat in _WEATHER_PATTERNS:
        if re.search(pat, tl):
            return "WEATHER"

    # 3. Check for itinerary intent
    for pat in _ITINERARY_PATTERNS:
        if re.search(pat, tl):
            return "ITINERARY"

    # 4. Strong trip-planning signals take priority (case-insensitive)
    for pat in _TRIP_PLANNING_PATTERNS:
        if re.search(pat, tl):
            return "TRIP_PLANNING"
    if _has_trip_origin_phrase(tl):
        return "TRIP_PLANNING"

    # 5. Check for pure tourism/information patterns
    for pat in _TOURISM_QUESTION_PATTERNS:
        if re.search(pat, tl):
            return "TOURISM"

    # 6. Default — treat as trip planning (preserves prior behaviour)
    return "UNKNOWN"

DEVOTIONAL_GREETINGS = [
    "🙏 Jai Mata Di! Let's plan your yatra.",
    "🙏 Jai Mata Di, welcome! Tell me about your trip.",
    "🙏 Jai Mata Di! Happy to help you plan your darshan.",
]
DEVOTIONAL_CONFIRMATIONS = [
    "🙏 Jai Mata Di — your booking is confirmed. Wishing you a blessed yatra!",
    "🙏 Jai Mata Di! May your darshan be peaceful and fulfilling.",
]


def _has_llm():
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def greeting():
    return random.choice(DEVOTIONAL_GREETINGS)


def confirmation_blessing():
    return random.choice(DEVOTIONAL_CONFIRMATIONS)


def understand_request(user_text, current_request=None, api_key=None, base_url=None):
    """Returns a structured trip request dict (pax, origin, category,
    mode, start_date, end_date) - same shape build_plan() expects,
    regardless of which mode produced it, merging with current_request if present."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        try:
            return _understand_with_llm(user_text, current_request=current_request, api_key=key, base_url=base_url)
        except Exception:
            pass  # fall back safely rather than breaking the conversation
    return legacy_agent.parse_request(user_text, current_request=current_request)


def _understand_with_llm(user_text, current_request=None, api_key=None, base_url=None):
    from datetime import date
    from openai import OpenAI

    url = base_url or os.environ.get("OPENAI_BASE_URL", None)
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key, base_url=url) if url else OpenAI(api_key=api_key)
    today = date.today().isoformat()
    prev_state_str = json.dumps(current_request) if current_request else "None"

    system = f"""Extract Vaishno Devi yatra trip details from the pilgrim's message as JSON only.
The message may be in Hindi, Hinglish, English, or another language - understand it regardless of language.
Today's date is {today}.
Previous trip request state: {prev_state_str}
If previous state exists, update and merge any new/clarified details from the message into that state.
Fields: pax (integer, default 1), origin (Indian city name in English, or null),
category (one of "Normal Darshan","VIP Darshan","Helicopter Darshan", or null),
mode (one of "flight","train","bus", or null if no preference stated),
duration_days (integer or null), season (string or null), sightseeing (boolean),
start_date (YYYY-MM-DD), end_date (YYYY-MM-DD). If no dates mentioned, use the next 14 days.
Respond with ONLY valid JSON, no markdown or extra text."""

    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json", "", 1).strip()
    parsed = json.loads(raw)
    return legacy_agent.merge_requests(current_request, parsed, text=user_text)


def format_tourism_reply(tourism_result):
    """Formats a tourism knowledge/content result into a readable, structured reply string
    based on query_kind so questions are answered directly and consistently."""
    import explore_data

    kind = tourism_result.get("query_kind") or "general"
    places = tourism_result.get("matched_places") or []
    primary = tourism_result.get("primary_place") or (places[0] if places else None)
    query = (tourism_result.get("query") or "").lower()
    is_followup = tourism_result.get("is_followup", False)

    # 1. Aarti Timings
    if kind == "aarti":
        aarti = tourism_result.get("aarti_timings") or {}
        morning = aarti.get("morning", {})
        summer = aarti.get("evening_summer", {})
        winter = aarti.get("evening_winter", {})
        return (
            "🙏 **Jai Mata Di!**\n\n"
            "### Aarti Timings at Vaishno Devi Shrine\n"
            "*Darshan pauses completely during these daily Aarti windows at the main Bhawan:*\n\n"
            "**Daily Schedule:**\n"
            f"• **Morning Aarti:** {morning.get('start', '-')} – {morning.get('end', '-')} ({morning.get('note', '')})\n"
            f"• **Evening Aarti (Summer, Apr–Sep):** {summer.get('start', '-')} – {summer.get('end', '-')}\n"
            f"• **Evening Aarti (Winter, Oct–Mar):** {winter.get('start', '-')} – {winter.get('end', '-')}\n\n"
            "**Important Note for Pilgrims:**\n"
            f"{aarti.get('general_note', '')}\n\n"
            "_Would you like to check trek route options or Yatra Slip registration steps next?_"
        )

    # 2. Packing Guidance
    if kind == "packing":
        packing = tourism_result.get("packing_guidance") or {}
        recs = "\n".join(f"• {item}" for item in packing.get("recommended", []))
        restricted = "\n".join(f"• {item}" for item in packing.get("commonly_restricted", []))
        disclaimer = packing.get("disclaimer", "")
        return (
            "🙏 **Jai Mata Di!**\n\n"
            "### Packing Guidance for Vaishno Devi Yatra\n"
            "*Essential items to pack and items to avoid during your trek:*\n\n"
            "**Recommended Essentials:**\n"
            f"{recs}\n\n"
            "**Restricted & Prohibited Items:**\n"
            f"{restricted}\n\n"
            "**Practical Tips:**\n"
            "• Keep your trek bag lightweight. Cloakroom and locker facilities are available at Katra and Bhawan for extra luggage.\n"
            "• Wear well-broken-in sports or trekking shoes to avoid blisters during the 13 km climb.\n\n"
            f"_{disclaimer}_\n\n"
            "_Would you like to check Aarti timings or route options next?_"
        )

    # 3. Yatra Registration
    if kind == "registration":
        reg = tourism_result.get("registration_info") or {}
        steps = "\n".join(f"• {step}" for step in reg.get("how_to_register", []))
        need = "\n".join(f"• {item}" for item in reg.get("what_youll_need", []))
        return (
            "🙏 **Jai Mata Di!**\n\n"
            "### Vaishno Devi Yatra Registration (Yatra Slip / Parchi)\n"
            f"*Yatra registration is mandatory for every pilgrim and is **{reg.get('cost', 'Free')}**.*\n\n"
            "**Key Requirements:**\n"
            f"• {reg.get('mandatory_note', '')}\n\n"
            "**How to Register:**\n"
            f"{steps}\n\n"
            "**What You Need to Bring:**\n"
            f"{need}\n\n"
            f"**Important Reminder:** {reg.get('reminder', '')}\n\n"
            "_Would you like to search travel options to Katra or view trek route options?_"
        )

    # 4. Route Options
    if kind == "routes":
        parts = [
            "🙏 **Jai Mata Di!**\n\n"
            "### Trek & Travel Route Options to Bhawan\n"
            "*Detailed routes available for reaching the main Shrine from Katra base town:*"
        ]
        for route in tourism_result.get("route_options") or []:
            parts.append(
                f"**{route['name']}** ({route.get('distance', '')}, {route.get('duration', '')})\n"
                f"• **Path:** {route.get('path', '')}\n"
                f"• **Details:** {route.get('notes', '')}"
            )
        parts.append("_Would you like to check Aarti timings or places to visit along the trek route?_")
        return "\n\n".join(parts)

    # 5. Helpline
    if kind == "helpline":
        helpline = tourism_result.get("helpline") or {}
        return (
            "🙏 **Jai Mata Di!**\n\n"
            "### Official Yatra Helpline Information\n\n"
            f"• **Toll-Free Helpline:** `{helpline.get('official_yatra_helpline', '-')}`\n"
            f"• **Note:** {helpline.get('note', '')}\n\n"
            "_Feel free to ask about Aarti timings, packing guidance, or registration steps._"
        )

    # 6. Vaishno History
    if kind == "vaishno_history" and not primary:
        sections = tourism_result.get("vaishno_history") or []
        parts = [
            "🙏 **Jai Mata Di!**\n\n"
            "### History & Sacred Legend of Vaishno Devi\n"
            "*Drawn from existing trek-site records documenting the pilgrimage legend:*\n"
        ]
        for section in sections:
            parts.append(f"**{section['name']}**\n{section['historical_background']}")
        if not sections:
            parts.append("I don't have a standalone Vaishno Devi history article in the current knowledge set.")
        parts.append("\n_Would you like to know more about Bhairavnath or Ardhkuwari Cave?_")
        return "\n\n".join(parts)

    # 7. Nearby Places (Concise, no dump)
    if kind == "nearby_places" and places:
        lines = [
            "🙏 **Jai Mata Di!**\n\n"
            "### Key Places to Visit Around Katra\n"
            "*Concise guide to popular shrines and spots along the trek and around Katra town:*\n"
        ]
        for p in places[:7]:
            lines.append(
                f"• **{p['name']}** ({p.get('category', '')}, {p.get('distance', '')}): {p.get('description', '')}"
            )
        lines.append(
            "\n**Local Travel Note:** Private taxis or auto-rickshaws are readily available in Katra town for nearby temples and nature spots.\n"
        )
        lines.append("_Would you like detailed information on any specific place above, or help planning your travel?_")
        return "\n\n".join(lines)

    # 8. Single Place / Place Follow-up Question
    primary = tourism_result.get("primary_place") or (places[0] if (places and kind == "place") else None)
    if primary:
        p = primary
        category = p.get("category", "")
        travel_note = explore_data.get_local_travel_note(category)

        if category == "On the trek route":
            route_pos = "Located directly along the main Vaishno Devi trek route between Katra and Bhawan."
        elif category in ("Nearby temple", "Nature"):
            route_pos = "Located near Katra base town — easily visited as a short excursion before or after the trek."
        elif category in ("Hill station", "Hill station / adventure"):
            route_pos = "A prominent hill station in the Jammu region, commonly visited as a full-day trip from Katra or Jammu."
        else:
            route_pos = "Located in or near Jammu city, convenient for pilgrims arriving or departing via Jammu."

        if is_followup and re.search(r"\b(how far|distance|where is|location)\b", query):
            return (
                f"🙏 **Jai Mata Di!**\n\n"
                f"### Distance & Travel: {p['name']}\n\n"
                f"• **Distance:** {p.get('distance', 'N/A')}\n"
                f"• **Category:** {category}\n"
                f"• **Pilgrimage Route Position:** {route_pos}\n"
                f"• **Local Travel Note:** {travel_note}\n\n"
                f"**Overview:** {p.get('description', '')}\n\n"
                f"_Would you like to know what to do at {p['name']}, or view other nearby places?_"
            )

        if is_followup and re.search(r"\b(what (can|to) (i|we) do|activities|things to do|see)\b", query):
            return (
                f"🙏 **Jai Mata Di!**\n\n"
                f"### What to Do & See at {p['name']}\n\n"
                f"**Main Attractions & Highlights:**\n"
                f"• {p.get('description', '')}\n"
                f"• **Historical / Cultural Background:** {p.get('historical_background', '')}\n\n"
                f"**Practical Information:**\n"
                f"• **Timings:** {p.get('timings', 'Not confirmed')}\n"
                f"• **Entry Fee:** {p.get('entry_fee', 'Free')}\n"
                f"• **Distance:** {p.get('distance', 'N/A')}\n\n"
                f"_Would you like to know how far {p['name']} is, or ask about another place?_"
            )

        return (
            f"🙏 **Jai Mata Di!**\n\n"
            f"### {p['name']}\n"
            f"*{category} · {p.get('distance', '')}*\n\n"
            f"**Overview**\n"
            f"{p.get('description', '')}\n\n"
            f"**Significance in Vaishno Devi Pilgrimage**\n"
            f"{p.get('historical_background', '')}\n\n"
            f"**Pilgrimage Route Position**\n"
            f"{route_pos}\n\n"
            f"**Practical Information**\n"
            f"• **Timings:** {p.get('timings', 'Not confirmed')}\n"
            f"• **Entry Fee:** {p.get('entry_fee', 'Free')}\n"
            f"• **Local Travel:** {travel_note}\n"
            f"• **Video Guide:** [Watch Video Guide]({p.get('video_search', '#')})\n\n"
            f"_Would you like to ask about distance or activities for {p['name']}, or search travel options to Katra?_"
        )

    # 9. Fallback
    return (
        "🙏 **Jai Mata Di!**\n\n"
        "I can help with places around Katra, Aarti timings, packing guidance, Yatra registration, "
        "and historical legends of shrines like Bhairavnath and Ardhkuwari. "
        "Feel free to ask any tourism question or tell me where you're traveling from to plan your trip!"
    )


def craft_reply(user_text, plan_status, context, api_key=None, base_url=None):
    """Generates the natural-language reply shown to the pilgrim,
    adapted to their language if an LLM is available, with devotional
    tone woven in. Falls back to plain templated English otherwise."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        try:
            return _craft_reply_with_llm(user_text, plan_status, context, key, base_url)
        except Exception:
            pass
    return _craft_reply_template(plan_status, context)


def _craft_reply_template(plan_status, context):
    templates = {
        "NEEDS_INFO": f"🙏 Jai Mata Di! {context.get('message', 'Could you share a bit more about your trip?')}",
        "NO_AVAILABILITY": f"🙏 I couldn't find matching options for those dates. {context.get('message', '')}",
        "NO_COMBINATION": f"🙏 {context.get('message', 'No valid combination found for those dates.')}",
        "PLAN_READY": (
            f"🙏 Jai Mata Di! I found {context.get('alt_flights_count', 0)} travel option(s) and "
            f"{context.get('alt_slots_count', 0)} darshan slot option(s). Here are the best matches — "
            "take a look below."
        ),
    }
    return templates.get(plan_status, "🙏 Jai Mata Di! Let me know how I can help with your yatra.")


def _craft_reply_with_llm(user_text, plan_status, context, api_key, base_url=None):
    from openai import OpenAI

    url = base_url or os.environ.get("OPENAI_BASE_URL", None)
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key, base_url=url) if url else OpenAI(api_key=api_key)
    system = """You are a warm, respectful assistant helping pilgrims plan a Vaishno Devi yatra.
Reply in the SAME language/style the pilgrim used in their message (Hindi, Hinglish, English, etc).
Keep replies short (2-3 sentences), naturally include a respectful devotional touch such as
"Jai Mata Di" where it fits, and never invent booking details not present in the context provided."""

    user_msg = f"Pilgrim's message: {user_text}\nSearch result status: {plan_status}\nContext: {context}"
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()

