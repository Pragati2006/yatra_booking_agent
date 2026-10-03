"""
agents/tools.py
LangChain-compatible tools for tool orchestration and agent dispatch.
Exposes modular data tools for searching transport options, yatra slots,
J&K tourism knowledge, weather guidance, and Playwright RPA automation.
"""

from langchain.tools import tool
import db
import explore_data
import weather
import yatra_info
from agents import rpa_agent


@tool
def search_transport_tool(origin: str, start_date: str, end_date: str, mode: str = None, pax: int = 1) -> list:
    """Searches available transport options (flight, train, bus) from origin city to Jammu/Katra for given dates and passenger count."""
    searchers = {
        "flight": db.search_flights,
        "train": db.search_trains,
        "bus": db.search_buses,
    }
    if mode and mode.lower() in searchers:
        return searchers[mode.lower()](origin, start_date, end_date, min_seats=pax)

    results = []
    for m in ("flight", "train", "bus"):
        results.extend(searchers[m](origin, start_date, end_date, min_seats=pax))
    return results


@tool
def search_yatra_slots_tool(start_date: str, end_date: str, category: str = None, min_seats: int = 1) -> list:
    """Searches available Vaishno Devi yatra darshan slots (Normal Darshan, VIP Darshan, Helicopter Darshan)."""
    return db.search_yatra_slots(start_date, end_date, category=category, min_seats=min_seats)


@tool
def get_tourism_info_tool(place_or_query: str = "") -> dict:
    """Retrieves J&K tourism information, historical background, timings, entry fee, and video search link for Katra/Jammu spots."""
    if not place_or_query:
        return {"places": explore_data.get_places()}

    place = explore_data.get_place_by_name(place_or_query)
    if place:
        return place

    query_lower = place_or_query.lower()
    matched = [
        p for p in explore_data.get_places()
        if query_lower in p["name"].lower() or query_lower in p["category"].lower() or query_lower in p["description"].lower()
    ]
    return {"matched_places": matched if matched else explore_data.get_places()}


@tool
def check_weather_tool(location: str = "Katra") -> dict:
    """Provides seasonal and current weather forecast guidance for Katra and Vaishno Devi trek."""
    try:
        return weather.get_weather_summary(location)
    except Exception as e:
        return {
            "source": "fallback",
            "summary": "Mild and pleasant",
            "low_c": 12,
            "high_c": 24,
            "advisory": f"Weather lookup fallback active: {str(e)}",
        }


@tool
def execute_rpa_booking_tool(user_name: str, pax_count: int, transport_text: str, slot_text: str, total_price: float, headless: bool = True) -> dict:
    """Executes the Playwright mock browser automation workflow for a confirmed yatra booking."""
    return rpa_agent.execute_playwright_mock_booking(
        user_name=user_name,
        pax_count=pax_count,
        transport_text=transport_text,
        slot_text=slot_text,
        total_price=total_price,
        headless=headless,
    )


def get_all_tools():
    """Returns the list of LangChain tool instances for agent orchestration."""
    return [
        search_transport_tool,
        search_yatra_slots_tool,
        get_tourism_info_tool,
        check_weather_tool,
        execute_rpa_booking_tool,
    ]
