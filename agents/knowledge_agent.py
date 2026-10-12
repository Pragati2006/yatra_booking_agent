"""
agents/knowledge_agent.py
Tourism Knowledge Retrieval Agent for Jammu & Kashmir.
Indexes and retrieves deep cultural, historical, route, and pilgrim guidance
for Katra, Vaishno Devi, Jammu, Shiv Khori, and Patnitop.

Retrieval is keyword-based over the existing explore_data / yatra_info
datasets. It does not invent places or copy those datasets into a second
store.
"""

import re

import explore_data
import yatra_info

# Common informal names that should resolve to an existing place record.
_PLACE_ALIASES = {
    "katra": "Katra",
    "katra town": "Katra",
    "bhairavnath": "Bhairavnath Temple",
    "bhairav nath": "Bhairavnath Temple",
    "bhairav": "Bhairavnath Temple",
    "bhairon": "Bhairavnath Temple",
    "bhaironath": "Bhairavnath Temple",
    "bhairon baba": "Bhairavnath Temple",
    "bhairon nath": "Bhairavnath Temple",
    "ardhkuwari": "Ardhkuwari Cave",
    "adhkuwari": "Ardhkuwari Cave",
    "garbh joon": "Ardhkuwari Cave",
    "charan paduka": "Charan Paduka",
    "charanpaduka": "Charan Paduka",
    "ban ganga": "Ban Ganga",
    "banganga": "Ban Ganga",
    "nau devi": "Nau Devi Cave Temple",
    "navdevi": "Nau Devi Cave Temple",
    "baba dhansar": "Baba Dhansar",
    "dhansar": "Baba Dhansar",
    "jhajjar kotli": "Jhajjar Kotli",
    "jhajjar": "Jhajjar Kotli",
    "patnitop": "Patnitop",
    "sanasar": "Sanasar",
    "mansar": "Mansar Lake",
    "mansar lake": "Mansar Lake",
    "raghunath": "Raghunath Temple, Jammu",
    "bahu fort": "Bahu Fort & Bagh-e-Bahu",
    "bahu": "Bahu Fort & Bagh-e-Bahu",
    "bagh-e-bahu": "Bahu Fort & Bagh-e-Bahu",
    "amar palace": "Amar Mahal Palace",
    "amar mahal palace": "Amar Mahal Palace",
    "amar mahal": "Amar Mahal Palace",
    "himkoti": "Himkoti",
    "dera baba": "Dera Baba Banda Bahadur",
    "banda bahadur": "Dera Baba Banda Bahadur",
    "shiv khori": "Shiv Khori",
    "shivkhori": "Shiv Khori",
    "peer kho": "Peer Kho Cave Temple",
    "peerkho": "Peer Kho Cave Temple",
    "srinagar": "Srinagar (Dal Lake & Gardens)",
    "dal lake": "Srinagar (Dal Lake & Gardens)",
    "gulmarg": "Gulmarg (Snow Meadow)",
    "pahalgam": "Pahalgam (Valley of Shepherds)",
    "sonamarg": "Sonamarg (Meadow of Gold)",
    "sonmarg": "Sonamarg (Meadow of Gold)",
    "kashmir valley": "Kashmir Valley",
    "kashmir": "Kashmir Valley",
    "shankaracharya": "Shankaracharya Temple, Srinagar",
    "shankaracharya temple": "Shankaracharya Temple, Srinagar",
    "kheer bhawani": "Kheer Bhawani Temple, Tulmulla",
    "kheer bhawani temple": "Kheer Bhawani Temple, Tulmulla",
    "tulmulla": "Kheer Bhawani Temple, Tulmulla",
    "verinag": "Verinag Spring and Mughal Garden",
    "verinag spring": "Verinag Spring and Mughal Garden",
    "achabal": "Achabal Mughal Garden",
    "achabal garden": "Achabal Mughal Garden",
    "martand": "Martand Sun Temple, Mattan",
    "martand sun temple": "Martand Sun Temple, Mattan",
    "mattan": "Martand Sun Temple, Mattan",
    "sinthan top": "Sinthan Top",
    "sinthan": "Sinthan Top",
}

_STOPWORDS = {
    "what", "which", "where", "when", "how", "who", "tell", "me", "about",
    "the", "a", "an", "of", "for", "to", "in", "on", "at", "around", "near",
    "nearby", "can", "i", "we", "you", "is", "are", "should", "do", "does",
    "visit", "visiting", "see", "places", "place", "please", "my", "our",
    "yatra", "trip", "info", "information", "details", "some", "any",
}

# Trek-route + Katra-local sites used for "places around Katra" answers.
_NEARBY_KATRA_CATEGORIES = {"On the trek route", "Nearby temple"}
_NEARBY_KATRA_EXTRA = {"Ban Ganga", "Baba Dhansar", "Jhajjar Kotli"}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).strip()


def _tokens(text: str):
    return [t for t in _normalize(text).split() if t and t not in _STOPWORDS]


def is_place_followup(query: str) -> bool:
    """True if query appears to be a follow-up question about a previously discussed place."""
    if not query:
        return False
    q = query.lower()
    patterns = [
        r"\b(how far|distance|how to reach|how to get|how do i reach|where is it|where located)\b",
        r"\b(what (can|to) (i|we) do|activities|things to do|what to see)\b",
        r"\b(tell me more|more details|more info|about it|about this place|tell me about it)\b",
        r"\b(timings|entry fee|ticket|cost|entry)\b",
        r"\b(it|there|that place)\b",
    ]
    return any(re.search(p, q) for p in patterns)


def classify_tourism_topic(query: str, last_place: str = None) -> str:
    """Classifies an information question so replies use the right existing source."""
    q = (query or "").lower()

    if re.search(r"\b(pack|packing|carry|bring|wear|what to pack|what to bring|what to carry|what to wear)\b", q):
        return "packing"
    if re.search(r"\b(aarti|aarthi)\b", q):
        return "aarti"
    if re.search(r"\b(register|registration|yatra slip|yatra parchi|how to register)\b", q):
        return "registration"
    if re.search(r"\b(trek route|route options|how to reach bhawan|tarakote|helicopter route)\b", q) and not find_specific_places(query):
        return "routes"
    if re.search(r"\b(helpline|contact number|phone number)\b", q):
        return "helpline"
    if re.search(r"\b(history|historical|heritage|mythology|legend|significance|background)\b", q) and re.search(
        r"\b(vaishno|vaishnavi|mata|shrine|bhawan|goddess)\b", q
    ) and not find_specific_places(query) and not (last_place and is_place_followup(query)):
        return "vaishno_history"
    specific_places = find_specific_places(query)
    non_katra_places = [p for p in specific_places if p["name"] != "Katra"]

# Broad destination/sightseeing questions should be treated as
# nearby-place queries before checking for a specific place.
    if re.search(
        r"\b(nearby|around katra|around jammu|places to (see|visit)|what places|tourist spots|sightseeing spots|places can i visit)\b",
        q,
    ):
        if not non_katra_places:
            return "nearby_places"
    
    if specific_places or (last_place and is_place_followup(query)):
        return "place"
    if find_specific_places(query) or (last_place and is_place_followup(query)):
        return "place"
    if re.search(r"\b(history|historical|heritage|mythology|legend)\b", q):
        return "vaishno_history"
    return "general"


def find_specific_places(query: str) -> list:
    """Returns existing place dicts whose names/aliases appear in the query.
    Does not fall back to the full catalogue."""
    if not query:
        return []

    q = _normalize(query)
    places = explore_data.get_places()
    by_name = {p["name"]: p for p in places}
    matched = []
    seen = set()

    for alias, canonical in sorted(_PLACE_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in q and canonical in by_name and canonical not in seen:
            matched.append(by_name[canonical])
            seen.add(canonical)

    query_tokens = set(_tokens(query))
    for p in places:
        if p["name"] in seen:
            continue
        name_tokens = set(_tokens(p["name"]))
        # Require a distinctive name token (ignore generic temple/cave/lake).
        distinctive = name_tokens - {"temple", "cave", "lake", "palace", "fort", "jammu"}
        if distinctive and distinctive <= query_tokens:
            matched.append(p)
            seen.add(p["name"])
            continue
        # Substring: "bhairavnath" inside "bhairavnath temple"
        name_compact = "".join(_tokens(p["name"]))
        query_compact = "".join(_tokens(query))
        if name_compact and len(name_compact) >= 6 and name_compact in query_compact:
            matched.append(p)
            seen.add(p["name"])

    return matched


def get_nearby_katra_places() -> list:
    """Relevant subset around Katra / the trek — not the full J&K catalogue."""
    selected = []
    seen = set()
    priority = ["Ban Ganga", "Charan Paduka", "Ardhkuwari Cave", "Bhairavnath Temple", "Baba Dhansar", "Nau Devi Cave Temple", "Jhajjar Kotli"]
    by_name = {p["name"]: p for p in explore_data.get_places()}
    for name in priority:
        if name in by_name and name not in seen:
            selected.append(by_name[name])
            seen.add(name)

    for p in explore_data.get_places():
        distance = (p.get("distance") or "").lower()
        from_katra = "katra" in distance or "trek" in distance or "bhawan" in distance
        if p["category"] in _NEARBY_KATRA_CATEGORIES or p["name"] in _NEARBY_KATRA_EXTRA or from_katra:
            if p["name"] not in seen:
                selected.append(p)
                seen.add(p["name"])
    return selected


def get_vaishno_devi_history() -> list:
    """History drawn only from existing trek-site records that document the legend."""
    names = ("Bhairavnath Temple", "Ardhkuwari Cave", "Charan Paduka", "Ban Ganga")
    sections = []
    for name in names:
        place = explore_data.get_place_by_name(name)
        if place:
            sections.append({
                "name": place["name"],
                "historical_background": place["historical_background"],
            })
    return sections


def get_jk_tourism_knowledge(query: str = "", last_place: str = None) -> dict:
    """Retrieves curated J&K tourism facts from existing local datasets, with
    support for follow-up questions referencing a previous place."""
    topic = classify_tourism_topic(query, last_place=last_place)
    specific = find_specific_places(query) if query else []

    is_followup = False
    primary_place = None

    # Broad sightseeing queries take priority over generic place matching.
    non_hub_specific = [p for p in specific if p["name"] not in ("Katra", "Jammu")]
    has_pronoun_ref = bool(re.search(r"\b(it|its|there|that place|this place)\b", query, re.IGNORECASE)) if query else False

    if topic == "nearby_places":
        matched_places = get_nearby_katra_places()

    elif last_place and is_place_followup(query) and (not non_hub_specific or has_pronoun_ref):
        resolved = search_place_by_name(last_place)
        if resolved:
            primary_place = resolved
            matched_places = [resolved]
            topic = "place"
            is_followup = True
        else:
            matched_places = []

    elif specific:
        primary_place = specific[0]
        matched_places = specific
        topic = "place"

    elif last_place and is_place_followup(query):
        resolved = search_place_by_name(last_place)
        if resolved:
            primary_place = resolved
            matched_places = [resolved]
            topic = "place"
            is_followup = True
        else:
            matched_places = []

    else:
        matched_places = []
    active_last_place = primary_place["name"] if primary_place else (last_place if is_followup else None)

    return {
        "query": query,
        "query_kind": topic,
        "matched_places": matched_places,
        "primary_place": primary_place,
        "last_place": active_last_place,
        "is_followup": is_followup,
        "vaishno_history": get_vaishno_devi_history() if topic == "vaishno_history" else [],
        "aarti_timings": yatra_info.get_aarti_timings(),
        "registration_info": yatra_info.get_registration_info(),
        "route_options": yatra_info.get_route_options(),
        "packing_guidance": yatra_info.get_packing_guidance(),
        "facilities": yatra_info.get_facilities(),
        "helpline": yatra_info.get_helpline(),
        "taxi_info": explore_data.get_taxi_info(),
    }


def search_place_by_name(name: str):
    """Retrieves full enriched dictionary for a specific place by name."""
    exact = explore_data.get_place_by_name(name)
    if exact:
        return exact
    found = find_specific_places(name)
    return found[0] if found else None


def get_personalized_recommendations(travel_preferences: dict = None) -> list:
    """Generates personalized tourist place recommendations in J&K based on pilgrim preferences.
    Preferences can include: 'category', 'max_distance', 'has_children', 'spirituality_level'."""
    prefs = travel_preferences or {}
    category = prefs.get("category")
    places = explore_data.get_places(category=category if category != "All" else None)

    scored_places = []
    for p in places:
        score = 10
        if prefs.get("has_children") and "trek" in p["category"].lower():
            score -= 2
        if prefs.get("spirituality_level") == "high" and ("temple" in p["category"].lower() or "trek" in p["category"].lower()):
            score += 3
        if prefs.get("nature_focused") and ("nature" in p["category"].lower() or "hill" in p["category"].lower()):
            score += 3
        scored_places.append({"place": p, "relevance_score": score})

    scored_places.sort(key=lambda x: x["relevance_score"], reverse=True)
    return [item["place"] for item in scored_places]
