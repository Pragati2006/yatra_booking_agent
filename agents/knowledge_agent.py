"""
agents/knowledge_agent.py
Tourism Knowledge Retrieval Agent for Jammu & Kashmir.
Indexes and retrieves deep cultural, historical, route, and pilgrim guidance
for Katra, Vaishno Devi, Jammu, Shiv Khori, and Patnitop.
"""

import explore_data
import yatra_info
import weather


def get_jk_tourism_knowledge(query: str = "") -> dict:
    """Retrieves curated J&K tourism facts, historical backgrounds, route options,
    Aarti timings, packing guidance, and local travel notes based on a query."""
    q = query.lower().strip() if query else ""
    
    places = explore_data.get_places()
    matched_places = []
    
    if q:
        for p in places:
            if (q in p["name"].lower() or 
                q in p["category"].lower() or 
                q in p["description"].lower() or 
                q in p["historical_background"].lower()):
                matched_places.append(p)
    
    if not matched_places:
        matched_places = places

    return {
        "matched_places": matched_places,
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
    return explore_data.get_place_by_name(name)


def get_personalized_recommendations(travel_preferences: dict = None) -> list:
    """Generates personalized tourist place recommendations in J&K based on pilgrim preferences.
    Preferences can include: 'category', 'max_distance', 'has_children', 'spirituality_level'."""
    prefs = travel_preferences or {}
    category = prefs.get("category")
    places = explore_data.get_places(category=category if category != "All" else None)
    
    # Simple scoring for personalization
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
