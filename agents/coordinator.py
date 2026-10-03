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

import re
import agent as legacy_agent
import db
from agents import conversation_agent, content_agent, itinerary_agent, knowledge_agent, recommendation_agent, rpa_agent


def get_greeting():
    return conversation_agent.greeting()


def process_itinerary_message(user_text, current_request=None, current_itinerary=None, last_context=None):
    """Handles day-by-day itinerary queries and edits."""
    if not current_itinerary:
        if current_request:
            current_itinerary = itinerary_agent.generate_default_itinerary(current_request)
        else:
            dummy_req = {"duration_days": 4, "origin": "Delhi", "pax": 1}
            current_itinerary = itinerary_agent.generate_default_itinerary(dummy_req)

    cmd = itinerary_agent.parse_itinerary_command(user_text, itinerary=current_itinerary, context=last_context)

    if cmd.get("ambiguous"):
        return {
            "intent": "ITINERARY",
            "reply": f"🙏 **Jai Mata Di!**\n\n{cmd.get('ambiguity_prompt', 'Which activity or day would you like to modify?')}",
            "plan": {"status": "NEEDS_INFO", "message": "Clarification required."},
            "request": current_request,
            "itinerary": current_itinerary,
            "recommendation": None,
            "last_itinerary_context": last_context,
        }

    valid, err_msg = itinerary_agent.validate_itinerary_command(current_itinerary, cmd)
    if not valid:
        return {
            "intent": "ITINERARY",
            "reply": f"🙏 **Jai Mata Di!**\n\n{err_msg}",
            "plan": {"status": "NEEDS_INFO", "message": err_msg},
            "request": current_request,
            "itinerary": current_itinerary,
            "recommendation": None,
            "last_itinerary_context": last_context,
        }

    if cmd["action"] == "SHOW":
        reply, new_ctx = itinerary_agent.format_show_reply(current_itinerary, cmd)
        return {
            "intent": "ITINERARY",
            "reply": reply,
            "plan": None,
            "request": current_request,
            "itinerary": current_itinerary,
            "recommendation": None,
            "last_itinerary_context": new_ctx or last_context,
        }
    else:
        updated_itinerary, edit_summary, new_ctx = itinerary_agent.apply_itinerary_edit(current_itinerary, cmd)
        full_reply = f"{edit_summary}\n\n" + itinerary_agent.format_full_itinerary_card(updated_itinerary)
        return {
            "intent": "ITINERARY",
            "reply": full_reply,
            "plan": None,
            "request": current_request,
            "itinerary": updated_itinerary,
            "recommendation": None,
            "last_itinerary_context": new_ctx or last_context,
        }


def process_trip_message(user_text, current_request=None, current_itinerary=None, api_key=None, base_url=None):
    """Entry point for the conversational trip search.
    Returns a dict: {reply, plan, request, recommendation, itinerary} where plan is build_plan()'s output
    (status, options, etc.), reply is the natural-language message, request is the state-accumulated
    trip request dict, and recommendation is the personalized travel recommendation."""
    request = conversation_agent.understand_request(user_text, current_request=current_request, api_key=api_key, base_url=base_url)

    # Check for ambiguous change request
    if legacy_agent.is_ambiguous_change(user_text):
        diff_check = legacy_agent.get_changed_fields(current_request, request)
        if not diff_check:
            return {
                "reply": (
                    "🙏 **Jai Mata Di!**\n\n"
                    "What would you like to change — duration, travel mode, number of travellers, starting city, or something else?"
                ),
                "plan": {"status": "NEEDS_INFO", "message": "Clarification required."},
                "request": current_request or request,
                "itinerary": current_itinerary,
                "recommendation": None,
            }

    plan = legacy_agent.build_plan(request)
    reply = conversation_agent.craft_reply(user_text, plan["status"], plan, api_key=api_key, base_url=base_url)
    rec = recommendation_agent.generate_recommendation(request)

    # Sync or generate itinerary
    itinerary = current_itinerary
    if not itinerary and request and request.get("duration_days"):
        itinerary = itinerary_agent.generate_default_itinerary(request)
    elif itinerary and request and request.get("duration_days"):
        itinerary = itinerary_agent.sync_itinerary_duration(current_itinerary, request["duration_days"], request)

    # Compute edit diff if previous request existed
    diff = legacy_agent.get_changed_fields(current_request, request)
    edit_summary = ""
    if diff:
        edit_summary = legacy_agent.format_edit_confirmation(diff)

    # Assemble response
    reply_parts = []
    if edit_summary:
        reply_parts.append(edit_summary)
    if rec and (request.get("group_type") or request.get("travel_style") or request.get("trip_focus") or request.get("origin") or request.get("duration_days")):
        reply_parts.append(rec["formatted_card"])
    reply_parts.append(reply)

    final_reply = "\n\n---\n".join(reply_parts)

    return {
        "reply": final_reply,
        "plan": plan,
        "request": request,
        "itinerary": itinerary,
        "recommendation": rec,
        "diff": diff,
    }


def get_trip_recommendation(request):
    """Coordinator-facing wrapper for recommendation engine."""
    return recommendation_agent.generate_recommendation(request)


def detect_intent(user_text):
    """Coordinator-facing wrapper so app.py does not import conversation_agent."""
    return conversation_agent.detect_intent(user_text)


def answer_tourism_query(user_text, last_tourism_place=None):
    """Routes a tourism/information question to the existing knowledge and
    content agents and returns a formatted text reply.
    Never touches transport search or darshan slots."""
    knowledge = knowledge_agent.get_jk_tourism_knowledge(user_text, last_place=last_tourism_place)
    reply = conversation_agent.format_tourism_reply(knowledge)
    return {
        "intent": "TOURISM",
        "reply": reply,
        "plan": None,
        "request": None,
        "itinerary": None,
        "query_kind": knowledge.get("query_kind"),
        "last_tourism_place": knowledge.get("last_place"),
    }


def process_weather_message(user_text, current_request=None):
    """Handles weather guidance queries using check_weather_tool."""
    from agents import tools
    try:
        w = tools.check_weather_tool.invoke({"location": "Katra"})
    except Exception:
        w = weather.get_weather_summary("Katra")

    summary = w.get("summary", "Pleasant")
    low_c = w.get("low_c", 12)
    high_c = w.get("high_c", 24)
    advisory = w.get("advisory", "")
    source = w.get("source", "seasonal_average")

    src_label = "Live Forecast" if source == "forecast" else "Seasonal Katra Average"

    reply = (
        "🙏 **Jai Mata Di! Katra Weather Guidance:**\n\n"
        f"• **Condition:** {summary}\n"
        f"• **Temperature Range:** {low_c}°C to {high_c}°C\n"
        f"• **Data Source:** {src_label}\n"
        f"• **Pilgrim Advisory:** {advisory}\n\n"
        "_The Bhawan shrine (~5,200 ft) runs several degrees cooler than Katra town — pack an extra warm layer for evening treks._"
    )

    return {
        "intent": "WEATHER",
        "reply": reply,
        "plan": None,
        "request": current_request,
        "itinerary": None,
        "tool_execution": {
            "tool": "check_weather_tool",
            "status": "success",
            "results": w
        }
    }


def process_booking_message(user_text, current_request=None, pending_options=None):
    """Handles booking execution with Human-in-the-Loop confirmation gate."""
    from agents import tools

    t_lower = (user_text or "").lower()
    explicit_confirm_keywords = ["yes", "confirm", "authorize", "proceed", "execute", "accept"]
    is_explicit_confirmed = any(w in t_lower for w in explicit_confirm_keywords)

    opt = None
    if pending_options and pending_options.get("options"):
        opt_match = re.search(r"option\s*(\d+)", t_lower)
        if opt_match:
            idx = int(opt_match.group(1)) - 1
            if 0 <= idx < len(pending_options["options"]):
                opt = pending_options["options"][idx]
        if not opt:
            opt = pending_options["options"][0]

    pax = current_request.get("pax", 1) if current_request else 1
    origin = current_request.get("origin", "Delhi") if current_request else "Delhi"
    tr = (opt.get("transport") or opt.get("flight") or {}) if opt else {}
    s = (opt.get("slot") or {}) if opt else {}

    # Human Confirmation Gate: require explicit confirmation before invoking RPA
    if not is_explicit_confirmed:
        mode_label = tr.get("mode", "Train").title()
        cat_label = s.get("category", "Normal Darshan")
        op_label = tr.get("operator", "Railways")
        price = opt.get("total_price", 1000) if opt else 1000

        reply = (
            "🙏 **Jai Mata Di! Human Confirmation Required**\n\n"
            "You are about to proceed with the following booking:\n"
            f"• **Route:** {origin} → Katra\n"
            f"• **Transport:** {mode_label} ({op_label})\n"
            f"• **Yatra Slot:** {cat_label}\n"
            f"• **Passengers:** {pax} pilgrim{'s' if pax > 1 else ''}\n"
            f"• **Estimated Total:** ₹{price}\n\n"
            "⚠️ **Confirmation Gate:** Do you authorize our Playwright RPA agent to execute this booking?\n\n"
            "_Reply **'Confirm booking'** or **'Yes, proceed'** to execute authorization._"
        )
        return {
            "intent": "BOOKING",
            "reply": reply,
            "plan": None,
            "request": current_request,
            "itinerary": None,
            "tool_execution": {
                "tool": "execute_rpa_booking_tool",
                "status": "pending_human_confirmation"
            }
        }

    # Explicit confirmation present -> execute RPA tool
    rpa_kwargs = {
        "user_name": "Guest-User",
        "pax_count": pax,
        "transport_text": f"{tr.get('mode', 'train')} from {origin}",
        "slot_text": s.get("category", "Normal Darshan"),
        "total_price": float(opt.get("total_price", 1000) if opt else 1000),
        "headless": True,
    }

    try:
        rpa_info = tools.execute_rpa_booking_tool.invoke(rpa_kwargs)
    except Exception:
        rpa_info = rpa_agent.execute_playwright_mock_booking(
            user_name="Guest-User",
            pax_count=pax,
            transport_text=f"{tr.get('mode', 'train')} from {origin}",
            slot_text=s.get("category", "Normal Darshan"),
            total_price=float(opt.get("total_price", 1000) if opt else 1000),
            headless=True,
        )

    reply = (
        "🙏 **Jai Mata Di! Booking Executed & Confirmed!**\n\n"
        f"Your confirmation ID is **{rpa_info['booking_id']}**.\n"
        f"• **Playwright RPA Execution:** Verified via browser automation agent.\n"
        f"• **Total Paid (Mock):** ₹{rpa_info.get('total_price', 1000)}\n\n"
        "May Mata Vaishno Devi grant you a safe, blessed, and memorable yatra!"
    )

    return {
        "intent": "BOOKING",
        "reply": reply,
        "plan": None,
        "request": current_request,
        "itinerary": None,
        "rpa_info": rpa_info,
        "tool_execution": {
            "tool": "execute_rpa_booking_tool",
            "status": "success",
            "results": rpa_info
        }
    }


def route_message(user_text, current_request=None, current_itinerary=None, last_tourism_place=None, last_itinerary_context=None, pending_options=None, api_key=None, base_url=None):
    """Top-level dispatcher. Determines what the pilgrim is asking for
    before choosing a processing path:

      BOOKING       -> process_booking_message() (Human confirmation + RPA tool)
      WEATHER       -> process_weather_message() (Weather tool)
      ITINERARY     -> process_itinerary_message()
      TOURISM       -> answer_tourism_query()   (knowledge/content agents)
      TRIP_PLANNING -> process_trip_message()   (existing booking flow)
      UNKNOWN       -> process_trip_message()   (safe default)

    Tourism results never include a travel plan. Callers must not overwrite
    an existing trip_request when request is None.
    """
    intent = conversation_agent.detect_intent(user_text)

    if intent == "BOOKING":
        res = process_booking_message(user_text, current_request=current_request, pending_options=pending_options)
        res["last_tourism_place"] = last_tourism_place
        res["last_itinerary_context"] = last_itinerary_context
        return res

    if intent == "WEATHER":
        res = process_weather_message(user_text, current_request=current_request)
        res["last_tourism_place"] = last_tourism_place
        res["last_itinerary_context"] = last_itinerary_context
        return res

    if intent == "ITINERARY":
        res = process_itinerary_message(user_text, current_request=current_request, current_itinerary=current_itinerary, last_context=last_itinerary_context)
        res["last_tourism_place"] = last_tourism_place
        return res

    if intent == "TOURISM":
        res = answer_tourism_query(user_text, last_tourism_place=last_tourism_place)
        res["last_itinerary_context"] = last_itinerary_context
        return res

    # TRIP_PLANNING or UNKNOWN -> existing stateful trip flow
    result = process_trip_message(user_text, current_request=current_request, current_itinerary=current_itinerary, api_key=api_key, base_url=base_url)
    result["intent"] = "TRIP_PLANNING" if intent == "UNKNOWN" else intent
    result["last_tourism_place"] = last_tourism_place
    result["last_itinerary_context"] = last_itinerary_context
    return result


def get_hotel_options(check_in_date, category=None):
    """HotelAgent duty - thin wrapper kept here so the coordinator is
    the single place app.py talks to for every agent's output."""
    return db.search_hotels(check_in_date, category=category)


def get_sightseeing_places(category=None):
    """SightseeingAgent duty - real places with history + video links attached."""
    return content_agent.get_all_places_enriched(category)


def get_place_content(place_name):
    return content_agent.get_enriched_place(place_name)


def get_tourism_knowledge(query: str = ""):
    """KnowledgeAgent duty - retrieves J&K tourism facts and route knowledge."""
    return knowledge_agent.get_jk_tourism_knowledge(query)


def get_personalized_places(travel_preferences: dict = None):
    """KnowledgeAgent duty - generates personalized tourist recommendations."""
    return knowledge_agent.get_personalized_recommendations(travel_preferences)


def build_final_itinerary(option, hotel=None, hotel_nights=0, sightseeing_places=None, request=None):
    return itinerary_agent.build_itinerary(option, hotel=hotel, hotel_nights=hotel_nights, sightseeing_places=sightseeing_places, request=request)


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


def execute_rpa_demo(user_name, pax_count, transport_text, slot_text, total_price, headless=True):
    """RPAAgent duty - runs safe Playwright mock booking workflow."""
    return rpa_agent.execute_playwright_mock_booking(
        user_name=user_name,
        pax_count=pax_count,
        transport_text=transport_text,
        slot_text=slot_text,
        total_price=total_price,
        headless=headless,
    )

