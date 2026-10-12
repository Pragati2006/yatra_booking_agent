import functools
from mongo_db import tourist_attractions, yatra_information
import explore_data
import yatra_info


def _local_search_tourist_attraction(query):
    places = explore_data.get_places()
    q = query.strip().lower()
    if not q:
        return []
    # 1. Exact match
    exact = [p for p in places if p["name"].lower() == q]
    if exact:
        return exact
    # 2. Name contains query
    name_m = [p for p in places if q in p["name"].lower()]
    if name_m:
        return name_m
    # 3. Region/category match
    reg_m = [p for p in places if q in p.get("region", "").lower() or q in p.get("category", "").lower()]
    if reg_m:
        return reg_m
    # 4. Description match
    desc_m = [p for p in places if q in p.get("description", "").lower()]
    return desc_m


_ATTRACTION_CACHE = {}


def search_tourist_attraction(query):
    """
    Search MongoDB for tourist attractions with local fallback.

    Results are prioritized in this order:
    1. Exact name match
    2. Name contains query
    3. Region/category match
    4. Description match
    """
    query = query.strip()
    if not query:
        return []
    # Handle nearby/around Katra queries separately.
    nearby_keywords = (
        "around katra",
        "near katra",
        "nearby katra",
        "places around katra",
        "places near katra",
        "visit around katra",
        "visit near katra",
    )

    q_lower = query.lower()

    if any(keyword in q_lower for keyword in nearby_keywords):
        nearby_query = "Katra"

        nearby_results = []

        if tourist_attractions is not None:
            try:
                # Search descriptions, routes and categories for Katra-area places.
                nearby_results = list(
                    tourist_attractions.find(
                        {
                            "$or": [
                                {"location_route": {"$regex": nearby_query, "$options": "i"}},
                                {"description": {"$regex": nearby_query, "$options": "i"}},
                                {"region": {"$regex": "Jammu", "$options": "i"}},
                            ]
                        },
                        {"_id": 0},
                    )
                )
            except Exception:
                nearby_results = []

        # Remove the Katra base-town document itself.
        nearby_results = [
            place
            for place in nearby_results
            if place.get("name", "").strip().lower() != "katra"
        ]

        if nearby_results:
            _ATTRACTION_CACHE[q_key] = nearby_results
            return nearby_results

        # Use the existing local tourism dataset as fallback.
        local_places = _local_search_tourist_attraction("Jammu")

        local_places = [
            place
            for place in local_places
            if place.get("name", "").strip().lower() != "katra"
        ]

        _ATTRACTION_CACHE[q_key] = local_places
        return local_places
    q_key = query.lower()
    if q_key in _ATTRACTION_CACHE:
        return _ATTRACTION_CACHE[q_key]

    if tourist_attractions is not None:
        try:
            regex = {"$regex": query, "$options": "i"}

            # 1. Exact name match
            exact_results = list(
                tourist_attractions.find(
                    {"name": {"$regex": f"^{query}$", "$options": "i"}},
                    {"_id": 0},
                )
            )
            if exact_results:
                _ATTRACTION_CACHE[q_key] = exact_results
                return exact_results

            # 2. Name contains query
            name_results = list(
                tourist_attractions.find(
                    {"name": regex},
                    {"_id": 0},
                )
            )
            if name_results:
                _ATTRACTION_CACHE[q_key] = name_results
                return name_results

            # 3. Region/category match
            region_results = list(
                tourist_attractions.find(
                    {
                        "$or": [
                            {"region": regex},
                            {"category": regex},
                        ]
                    },
                    {"_id": 0},
                )
            )
            if region_results:
                _ATTRACTION_CACHE[q_key] = region_results
                return region_results

            # 4. Description match
            description_results = list(
                tourist_attractions.find(
                    {"description": regex},
                    {"_id": 0},
                )
            )
            if description_results:
                _ATTRACTION_CACHE[q_key] = description_results
                return description_results
        except Exception:
            pass

    fallback_res = _local_search_tourist_attraction(query)
    _ATTRACTION_CACHE[q_key] = fallback_res
    return fallback_res


def _local_get_yatra_information(topic):
    topic = topic.strip().lower()
    if topic in ("aarti_timings", "aarti", "arti"):
        return {
            "topic": "aarti_timings",
            "title": "Aarti Timings & Holy Darshan Windows",
            "category": "Rituals",
            "content": (
                "Morning Aarti: 6:00 AM – 8:00 AM. Evening Aarti (Summer): 7:00 PM – 9:00 PM. "
                "Evening Aarti (Winter): 6:30 PM – 8:30 PM. Line movement pauses during holy rituals."
            ),
        }
    if topic in ("registration", "yatra_registration"):
        reg = yatra_info.get_registration_info()
        return {
            "topic": "registration",
            "title": "Mandatory Yatra Registration & RFID Slip",
            "category": "Registration",
            "content": f"Cost: {reg.get('cost', 'Free')}. Mandatory for all pilgrims. {reg.get('mandatory_note', '')}",
        }
    if topic in ("routes", "trek"):
        routes = yatra_info.get_route_options()
        txt = " · ".join([f"{r['name']} ({r['distance']}, {r['duration']})" for r in routes])
        return {
            "topic": "routes",
            "title": "Trek Route Options to Bhawan",
            "category": "Trek Routes",
            "content": txt,
        }
    if topic in ("facilities", "amenities"):
        fac = yatra_info.get_facilities()
        txt = " · ".join([f"{k.capitalize()}: {v}" for k, v in fac.items()])
        return {
            "topic": "facilities",
            "title": "Pilgrim Facilities & Amenities Along the Trek",
            "category": "Facilities",
            "content": txt,
        }
    if topic in ("packing", "clothing"):
        pkg = yatra_info.get_packing_guidance()
        return {
            "topic": "packing",
            "title": "Clothing & Packing Guidance for Vaishno Devi",
            "category": "Packing",
            "content": f"Recommended: {', '.join(pkg.get('recommended', []))}. Restricted: {', '.join(pkg.get('commonly_restricted', []))}",
        }
    if topic in ("helpline", "emergency"):
        hl = yatra_info.get_helpline()
        txt = " · ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in hl.items()])
        return {
            "topic": "helpline",
            "title": "Official Helpline & Emergency Contact Numbers",
            "category": "Emergency",
            "content": txt,
        }
    return None


def get_yatra_information(topic):
    """
    Retrieve Yatra information from MongoDB with local fallback.
    """
    topic = topic.strip().lower()
    if not topic:
        return None

    if yatra_information is not None:
        try:
            result = yatra_information.find_one(
                {"topic": topic},
                {"_id": 0},
            )
            if result:
                return result
        except Exception:
            pass

    return _local_get_yatra_information(topic)


_YATRA_SEARCH_CACHE = {}


def search_yatra_information(query):
    """
    Search Yatra information intelligently using the user's query.

    Supports natural-language queries such as:
    - "Aarti timings at Vaishno Devi"
    - "How do I register for the Yatra?"
    - "What facilities are available?"
    """
    query = query.strip().lower()
    if not query:
        return []

    if query in _YATRA_SEARCH_CACHE:
        return _YATRA_SEARCH_CACHE[query]

    topic_keywords = {
        "aarti": "aarti_timings",
        "arti": "aarti_timings",
        "timing": "aarti_timings",
        "timings": "aarti_timings",
        "registration": "registration",
        "register": "registration",
        "registration slip": "registration",
        "yatra slip": "registration",
        "parchi": "registration",
        "route": "routes",
        "routes": "routes",
        "reach bhawan": "routes",
        "trek": "routes",
        "facility": "facilities",
        "facilities": "facilities",
        "medical": "facilities",
        "langar": "facilities",
        "packing": "packing",
        "pack": "packing",
        "things to carry": "packing",
        "helpline": "helpline",
        "help line": "helpline",
        "contact": "helpline",
        "emergency": "helpline",
    }

    matched_topics = set()
    for keyword, topic in topic_keywords.items():
        if keyword in query:
            matched_topics.add(topic)

    if matched_topics:
        if yatra_information is not None:
            try:
                results = list(
                    yatra_information.find(
                        {"topic": {"$in": list(matched_topics)}},
                        {"_id": 0},
                    )
                )
                if results:
                    _YATRA_SEARCH_CACHE[query] = results
                    return results
            except Exception:
                pass

        # Fallback to local
        fb_results = []
        for t in matched_topics:
            item = _local_get_yatra_information(t)
            if item:
                fb_results.append(item)
        if fb_results:
            _YATRA_SEARCH_CACHE[query] = fb_results
            return fb_results

    # Fallback: search stored text fields
    if yatra_information is not None:
        try:
            regex = {"$regex": query, "$options": "i"}
            results = list(
                yatra_information.find(
                    {
                        "$or": [
                            {"topic": regex},
                            {"title": regex},
                            {"category": regex},
                        ]
                    },
                    {"_id": 0},
                )
            )
            if results:
                _YATRA_SEARCH_CACHE[query] = results
                return results
        except Exception:
            pass

    _YATRA_SEARCH_CACHE[query] = []
    return []


if __name__ == "__main__":

    print("=" * 60)
    print("MONGODB RETRIEVAL TEST")
    print("=" * 60)

    print("\n1. Searching for Gulmarg...")

    attractions = search_tourist_attraction("Gulmarg")

    for attraction in attractions:
        print(attraction)

    print("\n2. Retrieving Aarti timings...")

    aarti = get_yatra_information("aarti_timings")

    print(aarti)

    print("\n3. Searching Yatra information for registration...")

    registration = search_yatra_information("registration")

    for item in registration:
        print(item)

    print("\n" + "=" * 60)
    print("RETRIEVAL TEST COMPLETE")
    print("=" * 60)