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

import agent as legacy_agent  # the existing, tested transport/darshan parsing + ranking logic

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
    new_req = legacy_agent.parse_request(user_text)
    return legacy_agent.merge_requests(current_request, new_req, text=user_text)


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

