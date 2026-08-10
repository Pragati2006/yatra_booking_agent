"""
agents/coordinator.py
The orchestrator. Owns no data-fetching logic itself - it routes a
pilgrim's free-text message to the right specialist agent(s) and
assembles their outputs into one response, which is the core of the
"multi-agent" architecture:

  ConversationAgent  -> understands the message (any language) and
                         phrases replies with devotional warmth
  TransportAgent /
  DarshanAgent        -> (agent.py's build_plan, already tested) finds
                         and ranks real-timing-safe transport + darshan
                         combinations
  HotelAgent           -> (db.search_hotels) finds hotel options
  SightseeingAgent      -> (explore_data.py via ContentAgent) suggests
                         places, with real history + video links
  ItineraryAgent         -> assembles the final day-wise plan

This module doesn't touch Streamlit at all - app.py calls into it and
handles all rendering, so the agent logic stays testable on its own.
"""

import agent as legacy_agent
import db
from agents import conversation_agent, content_agent, itinerary_agent


def get_greeting():
    return conversation_agent.greeting()


def process_trip_message(user_text, api_key=None):
    """Entry point for the initial conversational trip search.
    Returns a dict: {reply, plan} where plan is build_plan()'s output
    (status, options, etc.) and reply is the natural-language message
    to show the pilgrim."""
    request = conversation_agent.understand_request(user_text, api_key=api_key)
    plan = legacy_agent.build_plan(request)
    reply = conversation_agent.craft_reply(user_text, plan["status"], plan, api_key=api_key)
    return {"reply": reply, "plan": plan, "request": request}


def get_hotel_options(check_in_date, category=None):
    """HotelAgent duty - thin wrapper kept here so the coordinator is
    the single place app.py talks to for every agent's output."""
    return db.search_hotels(check_in_date, category=category)


def get_sightseeing_places(category=None):
    """SightseeingAgent duty - real places with history + video links attached."""
    return content_agent.get_all_places_enriched(category)


def get_place_content(place_name):
    return content_agent.get_enriched_place(place_name)


def build_final_itinerary(option, hotel=None, hotel_nights=0, sightseeing_places=None):
    return itinerary_agent.build_itinerary(option, hotel=hotel, hotel_nights=hotel_nights, sightseeing_places=sightseeing_places)


def confirm_booking(option, pax, user_name, hotel=None, hotel_nights=0, sightseeing_places=None):
    """Delegates to the existing, tested booking logic, then adds a
    devotional confirmation message on top."""
    booking_id = legacy_agent.confirm_booking(
        option, pax, user_name,
        hotel=hotel, hotel_nights=hotel_nights,
        sightseeing_places=sightseeing_places,
    )
    blessing = conversation_agent.confirmation_blessing()
    return booking_id, blessing
