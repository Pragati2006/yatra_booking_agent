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
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List

import agent as legacy_agent  # the existing, tested transport/darshan parsing + ranking logic

# ---------------------------------------------------------------------------
# Supported Darshan Categories (Week 7 RPA Availability Checking)
# ---------------------------------------------------------------------------
SUPPORTED_CATEGORIES = [
    "Normal Darshan",
    "VIP Darshan",
    "Helicopter Darshan",
]

_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_AVAILABILITY_PATTERNS = [
    r"\b(check|find|lookup|see|show|tell me|is there|are there)\b.{0,30}\b(availability|available slots?|open slots?|darshan slots?|yatra slots?|slot status|vacant slots?)\b",
    r"\b(slot|slots|darshan)\s+(availability|status)\b",
    r"\b(check|is|are)\s+(any\s+)?(vip|normal|helicopter)?\s*(darshan)?\s*availability\b",
    r"\b(any slots available|slots available|available slots|open slots)\b",
    r"\bcheck availability\b",
]

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
    r"\b(nearby places|nearby attractions|nearby destinations|places to see|places to visit|tourist spots|sightseeing spots|tourist attractions|attractions)\b",
    r"\b(give me|show me|tell me)\b.{0,50}\b(attraction|attractions|place|places|sightseeing)\b",
    r"\b(bhairavnath|ardhkuwari|charan paduka|ban ganga|shiv khori|patnitop|sanasar|mansar|bahu fort|amar mahal|raghunath|peer kho|himkoti|baba dhansar|jhajjar kotli|nau devi)\b",
    r"\b(vaishno devi history|vaishno devi significance|vaishno devi legend|about vaishno devi|what is vaishno devi|what is (the )?(vaishno devi )?yatra|tell me about (the )?yatra)\b",
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

    # 4. Check for RPA availability checking intent (Week 7)
    for pat in _AVAILABILITY_PATTERNS:
        if re.search(pat, tl):
            return "AVAILABILITY"

    # 5. Strong trip-planning signals take priority (case-insensitive)
    for pat in _TRIP_PLANNING_PATTERNS:
        if re.search(pat, tl):
            return "TRIP_PLANNING"
    if _has_trip_origin_phrase(tl):
        return "TRIP_PLANNING"

    # 6. Check for pure tourism/information patterns
    for pat in _TOURISM_QUESTION_PATTERNS:
        if re.search(pat, tl):
            return "TOURISM"

    # 7. Default — treat as trip planning (preserves prior behaviour)
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Week 7: RPA Availability Parameter Extraction & Natural Language Parsing
# ---------------------------------------------------------------------------

def parse_and_validate_yatra_date(text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[str], bool, bool, Optional[str]]:
    """
    Extracts and validates a date from natural-language user query.
    Returns: (iso_date, raw_matched_str, is_missing, is_invalid, error_reason)
    
    Rules:
    1. Converts understandable natural-language dates to ISO format (YYYY-MM-DD).
    2. Validates calendar correctness (e.g. 2026-02-31 is invalid).
    3. If user says 'Check availability' without a date and context has no unambiguous date,
       returns is_missing=True (do NOT fabricate or invent dates).
    4. Follow-up queries (e.g. 'Are any slots available on that date?') use unambiguous
       context from context.get('last_availability_date') or context.get('requirements', {}).get('start_date').
    """
    if not text:
        text = ""
    t = text.strip()
    tl = t.lower()

    # Relative dates
    ref_date = date.today()
    if re.search(r"\bday after tomorrow\b", tl):
        target = ref_date + timedelta(days=2)
        return target.isoformat(), "day after tomorrow", False, False, None
    elif re.search(r"\btomorrow\b", tl):
        target = ref_date + timedelta(days=1)
        return target.isoformat(), "tomorrow", False, False, None
    elif re.search(r"\btoday\b", tl):
        return ref_date.isoformat(), "today", False, False, None

    # Pattern 1: ISO format YYYY-MM-DD or YYYY/MM/DD
    m_iso = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", t)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        raw = m_iso.group(0)
        try:
            dt = datetime(y, m, d)
            return dt.strftime("%Y-%m-%d"), raw, False, False, None
        except ValueError as ve:
            return None, raw, False, True, str(ve)

    # Pattern 2: DD-MM-YYYY or DD/MM/YYYY
    m_dmy = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", t)
    if m_dmy:
        d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        raw = m_dmy.group(0)
        try:
            dt = datetime(y, m, d)
            return dt.strftime("%Y-%m-%d"), raw, False, False, None
        except ValueError as ve:
            return None, raw, False, True, str(ve)

    # Pattern 3: Natural language: "20 November 2026", "20th Nov 2026", "20 Nov", "20th November"
    # Match: DD [st/nd/rd/th] Month [YYYY]
    m_nat1 = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)(?:\s*,?\s*(\d{4}))?\b",
        tl,
    )
    if m_nat1:
        d = int(m_nat1.group(1))
        m_str = m_nat1.group(2)
        m = _MONTH_MAP[m_str]
        y_str = m_nat1.group(3)
        y = int(y_str) if y_str else 2026  # target baseline year
        raw = m_nat1.group(0)
        try:
            dt = datetime(y, m, d)
            return dt.strftime("%Y-%m-%d"), raw, False, False, None
        except ValueError as ve:
            return None, raw, False, True, str(ve)

    # Pattern 4: Natural language: "November 20, 2026" or "Nov 20th 2026"
    m_nat2 = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b",
        tl,
    )
    if m_nat2:
        m_str = m_nat2.group(1)
        m = _MONTH_MAP[m_str]
        d = int(m_nat2.group(2))
        y_str = m_nat2.group(3)
        y = int(y_str) if y_str else 2026
        raw = m_nat2.group(0)
        try:
            dt = datetime(y, m, d)
            return dt.strftime("%Y-%m-%d"), raw, False, False, None
        except ValueError as ve:
            return None, raw, False, True, str(ve)

    # Check for invalid day expressions like "32nd Nov", "35th October"
    m_inv_day = re.search(r"\b(\d{2,3})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)", tl)
    if m_inv_day and int(m_inv_day.group(1)) > 31:
        return None, m_inv_day.group(0), False, True, f"Day {m_inv_day.group(1)} is invalid for calendar months"

    # Follow-up context resolution: e.g. "on that date", "same date", or follow-up question
    has_date_ref = bool(re.search(r"\b(that date|that day|same date|same day|that time)\b", tl))
    if context:
        ctx_date = context.get("last_availability_date")
        if not ctx_date and isinstance(context.get("requirements"), dict):
            ctx_date = context["requirements"].get("start_date")
        if not ctx_date and isinstance(context.get("current_request"), dict):
            ctx_date = context["current_request"].get("start_date")

        if ctx_date:
            if has_date_ref or ("availability" in tl or "slot" in tl):
                return ctx_date, "previous context date", False, False, None

    # No date supplied
    return None, None, True, False, None


def extract_and_validate_category(text: str) -> Tuple[Optional[str], Optional[str], bool, Optional[str]]:
    """
    Extracts and validates darshan category from user text against supported categories.
    Returns: (normalized_category, raw_matched_str, unsupported_category_flag, unsupported_val)
    """
    if not text:
        return None, None, False, None
    tl = text.lower()

    # Check for unsupported category phrases first
    unsupported_match = re.search(
        r"\b(super\s*vip|royal(?:\s+darshan)?|gold(?:\s+darshan)?|platinum(?:\s+darshan)?|vvip|executive(?:\s+darshan)?|special\s+priority)\b",
        tl,
    )
    if unsupported_match:
        raw_val = unsupported_match.group(0).strip().title()
        return None, raw_val, True, raw_val

    # Helicopter Darshan
    if re.search(r"\b(helicopter|heli)\b", tl):
        return "Helicopter Darshan", "Helicopter Darshan", False, None

    # VIP Darshan
    if re.search(r"\bvip\b", tl):
        return "VIP Darshan", "VIP Darshan", False, None

    # Normal Darshan
    if re.search(r"\b(normal(?:\s+darshan)?|regular(?:\s+darshan)?|general(?:\s+darshan)?|standard(?:\s+darshan)?)\b", tl):
        return "Normal Darshan", "Normal Darshan", False, None

    # None specified
    return None, None, False, None


def extract_availability_parameters(text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    High-level parameter extractor mapping user natural language into structured RPA parameters.
    Ensures:
    - Dates are converted to ISO YYYY-MM-DD.
    - Dates are validated against calendar rules.
    - Category values are checked against supported mock portal categories.
    - Does not invent dates or categories when missing.
    - Accurately reports missing or invalid fields.
    """
    iso_date, raw_date, is_missing, is_invalid, invalid_reason = parse_and_validate_yatra_date(text, context=context)
    cat, raw_cat, unsupported_cat, unsupported_val = extract_and_validate_category(text)

    return {
        "date": iso_date,
        "category": cat,
        "raw_date": raw_date,
        "raw_category": raw_cat,
        "missing_date": is_missing,
        "invalid_date": is_invalid,
        "invalid_date_reason": invalid_reason,
        "unsupported_category": unsupported_cat,
        "unsupported_category_value": unsupported_val,
    }


def format_missing_date_prompt() -> str:
    """Friendly devotional clarification prompt when user has not specified a date."""
    return (
        "🙏 **Jai Mata Di!**\n\n"
        "To check live yatra darshan availability via our Playwright RPA agent, please specify your preferred date "
        "(e.g., **'20 November 2026'** or **'2026-10-20'**).\n\n"
        "You can also specify a category such as **Normal Darshan**, **VIP Darshan**, or **Helicopter Darshan**."
    )


def format_invalid_date_prompt(raw_date: Optional[str], reason: Optional[str] = "") -> str:
    """Devotional prompt rejecting an invalid calendar date."""
    reason_str = f" ({reason})" if reason else ""
    raw_str = f" **'{raw_date}'**" if raw_date else ""
    return (
        "🙏 **Jai Mata Di!**\n\n"
        f"The requested date{raw_str} is invalid{reason_str}. "
        "Please provide a valid calendar date in `YYYY-MM-DD` or `DD Month YYYY` format (e.g., **'20 November 2026'**)."
    )


def format_unsupported_category_prompt(category_val: Optional[str]) -> str:
    """Devotional prompt rejecting an unsupported darshan category."""
    cat_str = f" **'{category_val}'**" if category_val else ""
    return (
        "🙏 **Jai Mata Di!**\n\n"
        f"The requested category{cat_str} is not recognized by the Shrine Board booking system.\n\n"
        "The supported darshan categories are:\n"
        "1. **Normal Darshan** (Standard pilgrim darshan)\n"
        "2. **VIP Darshan** (Special Aarti & priority queue)\n"
        "3. **Helicopter Darshan** (Katra-Sanjhichhat helicopter service)\n\n"
        "Which category would you like to check?"
    )


def format_availability_reply(result: Dict[str, Any], requested_date: str, category: Optional[str] = None) -> str:
    """
    Interprets structured Week 5 & Week 6 RPA availability results and generates
    a warm, natural-language response.
    Handles:
    A. Successful check with slots (capacity, times, price, status)
    B. Empty calendar (no slots open, without describing as system error)
    C. Recovered error (transient failure resolved via Week 6 retry)
    D. Human handover (safe pause, reason, technical details)
    """
    # Case D: Human Handover Required
    if result.get("handover_required") or result.get("status") == "HANDOVER_REQUIRED":
        reason = result.get("handover_reason") or "Automated checking could not safely verify page state."
        guidance = result.get("guidance") or "Please verify slot availability directly on the Shrine Board portal."
        attempts = result.get("retry_attempts_used", 1)
        return (
            "🙏 **Jai Mata Di! Human Handover Notice**\n\n"
            f"Automated availability checking for **{requested_date}** could not safely continue.\n\n"
            f"• **Reason:** {reason}\n"
            f"• **Attempts Made:** {attempts}\n"
            f"• **Safety Protocol:** Our RPA agent safely paused to avoid unverified or misleading availability claims.\n"
            f"• **Pilgrim Guidance:** {guidance}\n\n"
            "_Our pilgrim support team has been notified. You may also check official Shrine Board offline counters at Katra._"
        )

    # Case F: Hard Failure (non-handover failure)
    if result.get("status") == "FAILED" or result.get("status") == "ERROR":
        err_msg = result.get("error") or "Unknown portal communication error."
        return (
            "🙏 **Jai Mata Di!**\n\n"
            f"Unable to retrieve slot availability for **{requested_date}** due to a portal communication issue: {err_msg}.\n\n"
            "Please try again in a few moments or specify another date."
        )

    # Case B: No Available Slots / Empty Calendar
    is_empty = result.get("is_empty", False)
    total_slots = result.get("total_slots", 0)
    slots = result.get("slots", [])

    cat_label = f" for **{category}**" if category else ""

    if is_empty or total_slots == 0:
        return (
            "🙏 **Jai Mata Di! Availability Status**\n\n"
            f"No yatra darshan slots are currently open for **{requested_date}**{cat_label}.\n\n"
            "ℹ️ *Note:* This is not a system error; the quota for this date is either fully allocated or not yet released by the Shrine Board.\n\n"
            "**Recommendation:** Please consider checking adjacent dates (e.g., 2026-10-20 or 2026-10-21) or an alternative darshan category."
        )

    # Case A & C: Successful extraction
    avail_count = result.get("available_count", sum(1 for s in slots if s.get("availability_status") == "available"))
    full_count = result.get("full_count", sum(1 for s in slots if s.get("availability_status") == "full"))
    unavail_count = result.get("unavailable_count", sum(1 for s in slots if s.get("availability_status") == "unavailable"))

    lines = [
        "🙏 **Jai Mata Di! Yatra Slot Availability**\n",
        f"Availability for **{requested_date}**{cat_label}: found **{total_slots}** slot{'s' if total_slots != 1 else ''} "
        f"({avail_count} available, {full_count} full, {unavail_count} unavailable):\n",
    ]

    # Mention Week 6 recovery if applicable
    if result.get("recovered"):
        lines.append("_Note: Slot statuses were successfully extracted after recovering from transient portal latency via automated retry._\n")

    for s in slots:
        slot_id = s.get("slot_id", "SLOT")
        slot_name = s.get("slot_name", "Darshan")
        session = s.get("session", "")
        slot_time = s.get("time", "")
        status = s.get("availability_status", "available")
        capacity = s.get("remaining_capacity")
        price = s.get("price", 0.0)

        price_str = f"₹{int(price)}" if price else "Free (Included)"

        if status == "available":
            cap_str = f"🟢 **Available** ({capacity} seats left)" if capacity is not None else "🟢 **Available**"
        elif status == "full":
            cap_str = "🔴 **Full** (0 seats left)"
        else:
            cap_str = "⚪ **Unavailable**"

        session_str = f" • _{session}_" if session else ""
        time_str = f" • 🕒 {slot_time}" if slot_time else ""

        lines.append(f"• **{slot_id}** — **{slot_name}**{time_str}{session_str}")
        lines.append(f"  - Status: {cap_str} | Fare: **{price_str}**")

    lines.append("\nMay Mata Vaishno Devi grant you a blessed and fulfilling yatra! Would you like to proceed with booking travel and stay for this date?")

    return "\n".join(lines)


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
            route_pos_label = "Pilgrimage Route Position"
            route_pos = p.get("location_route") or "Located directly along the main Vaishno Devi trek route between Katra and Bhawan."
        elif category in ("Nearby temple", "Nature"):
            route_pos_label = "Pilgrimage Route Position"
            route_pos = p.get("location_route") or "Located near Katra base town — easily visited as a short excursion before or after the trek."
        elif category in ("Hill station", "Hill station / adventure"):
            route_pos_label = "Pilgrimage Route Position"
            route_pos = p.get("location_route") or "A prominent hill station in the Jammu region, commonly visited as a full-day trip from Katra or Jammu."
        elif category == "Kashmir" or p.get("region") == "Kashmir":
            route_pos_label = "Location & Route"
            route_pos = p.get("location_route") or "Located in the Kashmir Valley."
        else:
            route_pos_label = "Pilgrimage Route Position"
            route_pos = p.get("location_route") or "Located in or near Jammu city, convenient for pilgrims arriving or departing via Jammu."

        if is_followup and re.search(r"\b(how far|distance|where is|location)\b", query):
            return (
                f"🙏 **Jai Mata Di!**\n\n"
                f"### Distance & Travel: {p['name']}\n\n"
                f"• **Distance:** {p.get('distance', 'N/A')}\n"
                f"• **Category:** {category}\n"
                f"• **{route_pos_label}:** {route_pos}\n"
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
            f"**Significance & Background**\n"
            f"{p.get('historical_background', '')}\n\n"
            f"**{route_pos_label}**\n"
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

