"""
test_ui_flows.py
Tests the 7 requested functional flows through the coordinator / app agent integration:
A. "What places can I visit around Katra?"
B. "Tell me about Bhairavnath."
C. "Plan a 5-day trip from Bhopal for 4 people."
D. "Make it 6 days."
E. "Show my itinerary."
F. "What's the weather in Katra?"
G. Booking flow & Human confirmation gate
"""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from agents import coordinator

def test_flows():
    print("=" * 70)
    print("RUNNING MANUAL FUNCTIONAL REVIEW TESTS (FLOWS A - G)")
    print("=" * 70)

    session = {
        "trip_request": None,
        "itinerary": None,
        "last_tourism_place": None,
        "last_itinerary_context": None,
        "pending_options": None,
    }

    # FLOW A: Tourism query
    print("\n--- FLOW A: 'What places can I visit around Katra?' ---")
    res_a = coordinator.route_message("What places can I visit around Katra?")
    print(f"Intent detected: {res_a.get('intent')}")
    print(f"Reply summary:\n{res_a.get('reply')[:300]}...")
    assert res_a.get("intent") == "TOURISM"
    assert "Katra" in res_a.get("reply") or "Ban Ganga" in res_a.get("reply")

    # FLOW B: Tourism follow-up
    print("\n--- FLOW B: 'Tell me about Bhairavnath.' ---")
    res_b = coordinator.route_message("Tell me about Bhairavnath.", last_tourism_place=res_a.get("last_tourism_place"))
    print(f"Intent detected: {res_b.get('intent')}")
    print(f"Reply summary:\n{res_b.get('reply')[:300]}...")
    assert res_b.get("intent") == "TOURISM"
    assert "Bhairavnath" in res_b.get("reply")

    # FLOW C: Trip planning query
    print("\n--- FLOW C: 'Plan a 5-day trip from Bhopal for 4 people.' ---")
    res_c = coordinator.route_message("Plan a 5-day trip from Bhopal for 4 people.")
    print(f"Intent detected: {res_c.get('intent')}")
    req_c = res_c.get("request") or {}
    print(f"Captured Request: Origin={req_c.get('origin')}, Duration={req_c.get('duration_days')}, Pax={req_c.get('pax')}")
    print(f"Plan status: {(res_c.get('plan') or {}).get('status')}")
    session["trip_request"] = req_c
    session["itinerary"] = res_c.get("itinerary")
    session["pending_options"] = res_c.get("pending_options")
    assert req_c.get("origin") == "Bhopal"
    assert req_c.get("duration_days") == 5
    assert req_c.get("pax") == 4

    # FLOW D: Trip editing (Make it 6 days)
    print("\n--- FLOW D: 'Make it 6 days.' ---")
    res_d = coordinator.route_message("Make it 6 days.", current_request=session["trip_request"], current_itinerary=session["itinerary"])
    print(f"Intent detected: {res_d.get('intent')}")
    req_d = res_d.get("request") or {}
    print(f"Updated Request: Origin={req_d.get('origin')}, Duration={req_d.get('duration_days')}, Pax={req_d.get('pax')}")
    session["trip_request"] = req_d
    session["itinerary"] = res_d.get("itinerary")
    assert req_d.get("origin") == "Bhopal"  # Preserved
    assert req_d.get("duration_days") == 6  # Updated
    assert req_d.get("pax") == 4            # Preserved

    # FLOW E: Show itinerary
    print("\n--- FLOW E: 'Show my itinerary.' ---")
    res_e = coordinator.route_message("Show my itinerary.", current_request=session["trip_request"], current_itinerary=session["itinerary"])
    print(f"Intent detected: {res_e.get('intent')}")
    print(f"Reply summary:\n{res_e.get('reply')[:300]}...")
    assert res_e.get("intent") == "ITINERARY"
    assert len(session["itinerary"]) == 6

    # FLOW F: Katra Weather query
    print("\n--- FLOW F: 'What\\'s the weather in Katra?' ---")
    res_f = coordinator.route_message("What's the weather in Katra?", current_request=session["trip_request"])
    print(f"Intent detected: {res_f.get('intent')}")
    print(f"Reply summary:\n{res_f.get('reply')[:300]}...")
    assert res_f.get("intent") == "WEATHER"

    # FLOW G: Booking flow & HITL Confirmation Gate
    print("\n--- FLOW G: Booking flow & HITL Confirmation Gate ---")
    res_g_gate = coordinator.route_message("I want to book option 1", current_request=session["trip_request"])
    print(f"Intent detected: {res_g_gate.get('intent')}")
    print(f"Gate status: {res_g_gate.get('tool_execution', {}).get('status')}")
    print(f"Reply summary:\n{res_g_gate.get('reply')[:300]}...")
    assert res_g_gate.get("intent") == "BOOKING"
    assert res_g_gate.get("tool_execution", {}).get("status") == "pending_human_confirmation"

    res_g_confirm = coordinator.route_message("Yes, proceed and confirm booking", current_request=session["trip_request"])
    print(f"Execution status: {res_g_confirm.get('tool_execution', {}).get('status')}")
    assert res_g_confirm.get("tool_execution", {}).get("status") == "success"

    print("\n" + "=" * 70)
    print("ALL 7 FUNCTIONAL FLOWS (A - G) PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_flows()
