"""
agents/recommendation_agent.py
Personalized Trip Recommendation Engine for Vaishno Devi Yatra.

Analyzes pilgrim preferences (group type, travel style, trip focus, budget,
duration, and passenger count) and generates grounded, explainable travel
recommendations using existing project data (explore_data & yatra_info).

Does not invent prices, availability, or places outside the local dataset.
"""

import explore_data
import yatra_info


def extract_preferences(text: str) -> dict:
    """Rule-based extraction of travel preference fields from free text."""
    if not text:
        return {}
    t = text.lower()
    prefs = {}

    # 1. Group Type
    if any(w in t for w in ["family", "parents", "children", "kids", "wife", "husband", "relatives", "son", "daughter"]):
        prefs["group_type"] = "family"
    elif any(w in t for w in ["couple", "husband and wife", "me and my wife", "me and my husband", "just two of us"]):
        prefs["group_type"] = "couple"
    elif any(w in t for w in ["friends", "buddies", "colleagues", "mates"]):
        prefs["group_type"] = "friends"
    elif any(w in t for w in ["group", "tour group", "large group", "batch"]):
        prefs["group_type"] = "group"
    elif any(w in t for w in ["solo", "alone", "by myself", "single traveler", "myself"]):
        prefs["group_type"] = "solo"

    # 2. Travel Style / Pacing
    if any(w in t for w in ["relaxed", "comfortable", "unhurried", "leisurely", "slow pace", "no rush", "less hectic", "peaceful"]):
        prefs["travel_style"] = "relaxed"
    elif any(w in t for w in ["packed", "hectic", "fast", "busy", "maximum places", "cover everything", "tight"]):
        prefs["travel_style"] = "packed"
    elif any(w in t for w in ["balanced", "moderate", "standard pace"]):
        prefs["travel_style"] = "balanced"

    # 3. Trip Focus
    if any(w in t for w in ["both", "mixed", "pilgrimage and sightseeing", "darshan and sightseeing", "worship and tour"]):
        prefs["trip_focus"] = "mixed"
    elif any(w in t for w in ["devotional", "pilgrimage", "darshan focus", "main purpose is darshan", "mainly want the vaishno", "only pilgrimage", "worship"]):
        prefs["trip_focus"] = "devotional"
    elif any(w in t for w in ["sightseeing", "tourist", "tourism", "see more places", "explore nearby", "visit places"]):
        prefs["trip_focus"] = "sightseeing"

    # 4. Budget Preference
    if any(w in t for w in ["budget", "budget friendly", "cheap", "economical", "low cost", "affordable"]):
        prefs["budget_preference"] = "budget"
    elif any(w in t for w in ["spending more", "premium", "luxury", "top tier"]):
        prefs["budget_preference"] = "premium"
    elif any(w in t for w in ["comfortable", "mid-range", "standard"]):
        prefs["budget_preference"] = "comfortable"

    return prefs


def generate_recommendation(request: dict) -> dict:
    """Generates a structured, grounded recommendation based on user trip request preferences.
    Never invents data or prices."""
    req = request or {}
    pax = req.get("pax", 1)
    duration = req.get("duration_days", 4) or 4
    group_type = req.get("group_type") or ("family" if pax > 1 else "solo")
    travel_style = req.get("travel_style") or "balanced"

    sightseeing_flag = req.get("sightseeing", False)
    trip_focus = req.get("trip_focus")
    if not trip_focus:
        trip_focus = "mixed" if sightseeing_flag else "devotional"

    budget = req.get("budget_preference") or "comfortable"

    # Determine recommended pacing & approach bullets
    approach_bullets = []
    if duration <= 3:
        approach_bullets.append("Focus primarily on the core Vaishno Devi darshan & Bhairavnath Temple.")
        approach_bullets.append("Keep onward travel buffers tight to maximize shrine time.")
    elif duration <= 5:
        approach_bullets.append("Allocate 2 dedicated days for Yatra trek, darshan, and Bhairavnath Temple.")
        if travel_style == "relaxed":
            approach_bullets.append("Include generous rest buffer in Katra after the trek before any local sightseeing.")
        else:
            approach_bullets.append("Dedicate Days 4 & 5 to exploring scenic spots around Katra.")
    else:
        approach_bullets.append("Full 2-day Yatra trek & darshan with zero rush.")
        approach_bullets.append("Multi-day excursion to nearby destinations like Patnitop, Mansar Lake, or Shiv Khori.")

    if group_type == "family":
        approach_bullets.append("Select easily accessible, family-friendly shrines and nature spots around Katra.")
    elif group_type == "couple":
        approach_bullets.append("Combine sacred darshan with quiet, scenic nature stops around Katra.")
    elif group_type in ("solo", "friends"):
        approach_bullets.append("Flexible pacing allowing optional hill-station treks or adventure spots.")

    # Select recommended places deterministically from existing explore_data
    all_places = explore_data.get_places()
    shrine_names = ["Bhairavnath Temple", "Ardhkuwari Cave", "Charan Paduka", "Nau Devi Cave Temple", "Ban Ganga"]
    scenic_names = ["Baba Dhansar", "Patnitop", "Jhajjar Kotli", "Mansar Lake", "Sanasar", "Bahu Fort & Bagh-e-Bahu"]

    suggested_places = []
    by_name = {p["name"]: p for p in all_places}

    if trip_focus == "devotional":
        target_names = shrine_names
    elif trip_focus == "sightseeing":
        target_names = scenic_names
    else:  # mixed
        target_names = ["Bhairavnath Temple", "Baba Dhansar", "Patnitop", "Charan Paduka", "Nau Devi Cave Temple"]

    # Filter based on group_type and travel_style
    max_spots = 2 if (travel_style == "relaxed" or duration <= 3) else (4 if travel_style == "packed" else 3)

    for name in target_names:
        if len(suggested_places) >= max_spots:
            break
        if name in by_name:
            p = by_name[name]
            # Family filter: avoid heavy treks if extra
            if group_type == "family" and p["category"] == "Hill station / adventure":
                continue
            suggested_places.append(p)

    # Explainability / Reasoning
    reasoning_parts = []
    reasoning_parts.append(f"Since you are travelling as a {group_type} group ({pax} pilgrim{'s' if pax > 1 else ''}) for {duration} days")

    if travel_style == "relaxed":
        reasoning_parts.append("and prefer a relaxed pace, the recommendation avoids packing too many activities onto pilgrimage days and leaves generous buffer time after the trek.")
    elif travel_style == "packed":
        reasoning_parts.append("and prefer a packed itinerary, the recommendation maximizes sightseeing opportunities across nearby Katra spots.")
    else:
        reasoning_parts.append("with a balanced schedule, the plan combines core darshan with manageable local sightseeing.")

    reasoning = " ".join(reasoning_parts)

    # Budget Note
    if budget == "budget":
        budget_note = "Budget preference recorded: prioritizing train/bus transport and budget-friendly Katra stay options. Final cost depends on real-time availability."
    elif budget == "premium":
        budget_note = "Comfort & premium preference recorded: prioritizing flight options and premium hotel properties in Katra."
    else:
        budget_note = "Budget preference recorded; final cost depends on available transport/stay options."

    # Format Markdown Card
    card_lines = [
        "<!-- PERSONALIZED TRIP RECOMMENDATION -->",
        "### ✨ YOUR PERSONALIZED YATRA PLAN",
        "*Designed around your travel preferences*",
        "",
        "**TRIP SNAPSHOT**",
        f"• **Travellers:** {pax} pilgrim{'s' if pax > 1 else ''}",
        f"• **Group Type:** {group_type.title()}",
        f"• **Duration:** {duration} days",
        f"• **Pacing & Style:** {travel_style.title()} pace",
        f"• **Trip Focus:** {trip_focus.title()} ({'Pilgrimage + Sightseeing' if trip_focus=='mixed' else trip_focus.title()})",
        f"• **Budget Preference:** {budget.title()}",
        "",
        "**Recommended Approach**",
    ]
    for b in approach_bullets:
        card_lines.append(f"• {b}")

    card_lines.append("\n**Suggested Places to Visit**")
    for sp in suggested_places:
        card_lines.append(f"• **{sp['name']}** ({sp['category']}, {sp['distance']}): {sp['description']}")

    card_lines.append(f"\n**Why This Suits You**\n\"{reasoning}\"\n")
    card_lines.append(f"💰 **BUDGET:** {budget.title()}\n_{budget_note}_\n")
    card_lines.append("**NEXT ACTIONS:**\n• [Generate Itinerary →]\n• [Search Travel →]")

    formatted_card = "\n".join(card_lines)

    return {
        "profile": {
            "pax": pax,
            "group_type": group_type,
            "duration_days": duration,
            "travel_style": travel_style,
            "trip_focus": trip_focus,
            "budget_preference": budget,
        },
        "approach_bullets": approach_bullets,
        "suggested_places": suggested_places,
        "reasoning": reasoning,
        "budget_note": budget_note,
        "formatted_card": formatted_card,
    }
