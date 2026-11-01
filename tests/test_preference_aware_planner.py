"""
tests/test_preference_aware_planner.py
Phase 8 — Preference-Aware Sightseeing & Itinerary Engine Tests.

Validates:
1. User-selected sightseeing destinations are passed to the planner and scheduled when feasible.
2. Infeasible sightseeing selections are evaluated by the deterministic engine and returned
   in infeasible_places with actual explanations, without being silently dropped.
3. User's explicit choice to decide sightseeing later ('later') preserves that choice without
   forcing recommendations or default excursions onto the schedule.
4. Recommendation behavior when no destinations are selected adheres to duration and pace limits.
5. NEEDS_INFO responses suppress misleading completed itineraries and recommendation cards.
6. Total-group versus per-person budget extraction and calculation.
7. Exact trip duration and trek/recovery constraints survive the full orchestrator flow.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

# Ensure UTF-8 output on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    elif hasattr(sys.stdout, "buffer") and not sys.stdout.buffer.closed:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

import db
from agents import itinerary_agent, orchestrator, session_store


class TestPreferenceAwarePlanner(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_sessions.db")
        self.orig_db_path = session_store.DEFAULT_DB_PATH
        session_store.DEFAULT_DB_PATH = self.temp_db_path
        session_store.init_db(self.temp_db_path)
        db.ensure_live_data()

    def tearDown(self):
        session_store.DEFAULT_DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. User-selected destinations passed and scheduled
    # -------------------------------------------------------------------------
    def test_user_selected_destinations_passed_and_scheduled(self):
        """Selected destinations are passed to the planner and scheduled on feasible intermediate days."""
        req = {
            "origin": "Delhi",
            "duration_days": 4,
            "pax": 2,
            "sightseeing_places": ["Nau Devi Cave Temple"],
            "travel_style": "balanced",
        }
        plan_res = orchestrator.coordinate_plan(req)
        self.assertEqual(plan_res["status"], "PLAN_READY")

        # Feasible places must include the user's choice
        feasible = plan_res.get("feasible_places", [])
        self.assertIn("Nau Devi Cave Temple", feasible)
        self.assertEqual(len(plan_res.get("infeasible_places", [])), 0)

        # Itinerary must be exactly 4 days
        itinerary = plan_res.get("itinerary") or []
        self.assertEqual(len(itinerary), 4)

        # Day 3 (recovery day) must schedule Nau Devi Cave Temple
        day3 = itinerary[2]
        self.assertEqual(day3["day_number"], 3)
        self.assertTrue(any("Nau Devi" in act for act in day3["activities"]))

    # -------------------------------------------------------------------------
    # 2. Feasible vs Infeasible destination reporting
    # -------------------------------------------------------------------------
    def test_infeasible_destinations_reported_with_engine_explanations(self):
        """Infeasible destinations (e.g. Patnitop on 3-day trip) are not silently dropped;
        they are returned in infeasible_places with actual deterministic explanations."""
        req = {
            "origin": "Delhi",
            "duration_days": 3,
            "pax": 2,
            "sightseeing_places": ["Patnitop"],
            "travel_style": "balanced",
        }
        plan_res = orchestrator.coordinate_plan(req)
        self.assertEqual(plan_res["status"], "PLAN_READY")

        # Infeasible places list must contain Patnitop with explanation
        infeasible = plan_res.get("infeasible_places", [])
        self.assertEqual(len(infeasible), 1)
        pat_inf = infeasible[0]
        self.assertEqual(pat_inf["place"], "Patnitop")
        self.assertIn("85 km", pat_inf["reason"])
        self.assertIn("physical exhaustion", pat_inf["reason"])
        self.assertTrue(bool(pat_inf.get("suggestion")))

        # Patnitop must not be in feasible_places
        self.assertNotIn("Patnitop", plan_res.get("feasible_places", []))

        # Itinerary must still be exactly 3 days and Day 2 must be exclusive trek
        itinerary = plan_res.get("itinerary") or []
        self.assertEqual(len(itinerary), 3)
        self.assertEqual(itinerary[1]["title"], "Dedicated Holy Yatra & Darshan Trek")
        self.assertFalse(any("Patnitop" in act for act in itinerary[1]["activities"]))

        # Consolidated reply must include the feasibility advisory
        reply = plan_res.get("reply", "")
        self.assertIn("Sightseeing Feasibility Advisory", reply)
        self.assertIn("Patnitop", reply)

    # -------------------------------------------------------------------------
    # 3. User decision to choose sightseeing later
    # -------------------------------------------------------------------------
    def test_sightseeing_choice_later_preserves_choice_without_forced_places(self):
        """When user explicitly decides to choose sightseeing later, no recommendations
        are forced onto the itinerary, and Day 3 remains an open Katra leisure/recovery day."""
        req = {
            "origin": "Delhi",
            "duration_days": 4,
            "pax": 2,
            "sightseeing_choice": "later",
            "sightseeing_places": [],
        }
        plan_res = orchestrator.coordinate_plan(req)
        self.assertEqual(plan_res["status"], "PLAN_READY")

        # Feasible places must remain empty
        feasible = plan_res.get("feasible_places", [])
        self.assertEqual(len(feasible), 0)
        self.assertEqual(len(plan_res.get("infeasible_places", [])), 0)

        # Day 3 must be Katra Leisure without forced Baba Dhansar or Patnitop
        itinerary = plan_res.get("itinerary") or []
        self.assertEqual(len(itinerary), 4)
        day3 = itinerary[2]
        self.assertIn("Katra Town Leisure", day3["title"])
        self.assertFalse(any("Patnitop" in act for act in day3["activities"]))
        self.assertFalse(any("Baba Dhansar" in act for act in day3["activities"]))

    # -------------------------------------------------------------------------
    # 4. Recommendation behavior when no destinations are selected
    # -------------------------------------------------------------------------
    def test_recommendation_behavior_adheres_to_duration_and_pace(self):
        """When no destinations are selected and user wants recommendations,
        short trips (<= 3 days) only recommend nearby Katra spots, never Patnitop."""
        # 3-day trip
        req_3d = {
            "origin": "Delhi",
            "duration_days": 3,
            "pax": 2,
            "sightseeing_choice": "recommend",
            "sightseeing_places": [],
        }
        res_3d = orchestrator.coordinate_plan(req_3d)
        feasible_3d = res_3d.get("feasible_places", [])
        self.assertNotIn("Patnitop", feasible_3d)

        # 5-day trip
        req_5d = {
            "origin": "Delhi",
            "duration_days": 5,
            "pax": 2,
            "sightseeing_choice": "recommend",
            "sightseeing_places": [],
        }
        res_5d = orchestrator.coordinate_plan(req_5d)
        feasible_5d = res_5d.get("feasible_places", [])
        self.assertIn("Patnitop", feasible_5d)
        self.assertIn("Baba Dhansar", feasible_5d)

    # -------------------------------------------------------------------------
    # 5. NEEDS_INFO responses suppress completed plan and recommendations
    # -------------------------------------------------------------------------
    def test_needs_info_suppresses_misleading_completed_itinerary(self):
        """When mandatory fields are missing, orchestrator returns NEEDS_INFO with
        None for itinerary and recommendation, avoiding misleading cards."""
        res = orchestrator.orchestrate_conversational_turn("I want to visit Vaishno Devi with family")
        self.assertEqual(res["status"], "NEEDS_INFO")
        self.assertIsNone(res.get("itinerary"))
        self.assertIsNone(res.get("recommendation"))
        self.assertIn("origin", res.get("missing_fields", []))

    # -------------------------------------------------------------------------
    # 6. Total vs per-person budget extraction and calculation
    # -------------------------------------------------------------------------
    def test_per_person_vs_total_budget_handling(self):
        """Orchestrator correctly computes total budget when per-person phrasing is used."""
        req = orchestrator.extract_trip_requirements("We are 3 pilgrims from Delhi with a budget of 6000 per person")
        self.assertEqual(req["pax"], 3)
        self.assertEqual(req["origin"], "Delhi")
        self.assertEqual(req["budget_type"], "per_person")
        self.assertEqual(req["budget_per_person"], 6000.0)
        self.assertEqual(req["total_budget"], 18000.0)

    # -------------------------------------------------------------------------
    # 7. Conversational replanning with sightseeing update
    # -------------------------------------------------------------------------
    def test_conversational_replanning_with_sightseeing_update(self):
        """Modifying a confirmed plan to add an infeasible distant destination
        properly updates the plan and surfaces the feasibility advisory."""
        # Initial turn: complete 4-day plan
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 people with Baba Dhansar"
        )
        self.assertEqual(res1["status"], "PLAN_READY")
        sid = res1["session_id"]

        # User attempts to add Sinthan Top (requires 6 days) in a replanning query
        res2 = orchestrator.orchestrate_conversational_turn(
            "Can we also add Sinthan Top to our trip?",
            session_id=sid,
        )
        self.assertIn(res2["status"], ["PLAN_REVISED", "PLAN_READY"])
        infeasible = res2.get("infeasible_places", [])
        self.assertTrue(any(inf["place"] == "Sinthan Top" for inf in infeasible))

    # -------------------------------------------------------------------------
    # Regression Test 1: Uncatalogued destination is not marked feasible
    # -------------------------------------------------------------------------
    def test_uncatalogued_destination_rejected_as_infeasible(self):
        """Uncatalogued destinations (e.g. 'Eiffel Tower') must not be given default
        logistics profiles, must not be marked feasible, and must be returned in infeasible_places."""
        req = {
            "origin": "Delhi",
            "duration_days": 4,
            "pax": 2,
            "sightseeing_places": ["Eiffel Tower"],
            "travel_style": "balanced",
        }
        plan_res = orchestrator.coordinate_plan(req)
        self.assertEqual(plan_res["status"], "PLAN_READY")

        feasible = plan_res.get("feasible_places", [])
        self.assertNotIn("Eiffel Tower", feasible)

        infeasible = plan_res.get("infeasible_places", [])
        self.assertEqual(len(infeasible), 1)
        self.assertEqual(infeasible[0]["place"], "Eiffel Tower")
        self.assertIn("could not be verified against the supported", infeasible[0]["reason"])

        # Logistics profile must be None for ungrounded destination
        self.assertIsNone(itinerary_agent.get_destination_logistics("Eiffel Tower"))

    # -------------------------------------------------------------------------
    # Regression Test 2: Baba Dhansar on 3-day trip reported as infeasible
    # -------------------------------------------------------------------------
    def test_baba_dhansar_on_three_day_trip_explicitly_infeasible(self):
        """Baba Dhansar has no intermediate scheduling slot on a 3-day trip (Day 1 arrival,
        Day 2 trek, Day 3 departure) and must be explicitly reported in infeasible_places,
        never silently dropped; while trek-route shrines (Bhairavnath) remain feasible."""
        req = {
            "origin": "Delhi",
            "duration_days": 3,
            "pax": 2,
            "sightseeing_places": ["Baba Dhansar", "Bhairavnath Temple"],
            "travel_style": "balanced",
        }
        plan_res = orchestrator.coordinate_plan(req)
        self.assertEqual(plan_res["status"], "PLAN_READY")

        # Baba Dhansar must be reported in infeasible_places
        infeasible = plan_res.get("infeasible_places", [])
        inf_names = [inf["place"] for inf in infeasible]
        self.assertIn("Baba Dhansar", inf_names)
        bd_inf = next(inf for inf in infeasible if inf["place"] == "Baba Dhansar")
        self.assertIn("3-day trip reserves Day 1 for arrival", bd_inf["reason"])
        self.assertIn("no intermediate days available", bd_inf["reason"])

        # Bhairavnath Temple is on the trek route and IS feasible on Day 2
        feasible = plan_res.get("feasible_places", [])
        self.assertIn("Bhairavnath Temple", feasible)
        self.assertNotIn("Baba Dhansar", feasible)

        # Itinerary must be exactly 3 days and Day 2 must include Bhairavnath
        itinerary = plan_res.get("itinerary") or []
        self.assertEqual(len(itinerary), 3)
        self.assertTrue(any("Bhairavnath" in act for act in itinerary[1]["activities"]))
        # Baba Dhansar must not appear in any itinerary day
        for d in itinerary:
            self.assertFalse(any("Baba Dhansar" in act for act in d["activities"]))

    # -------------------------------------------------------------------------
    # Regression Test 3: Patnitop not scheduled on immediate recovery day (Day 3)
    # -------------------------------------------------------------------------
    def test_patnitop_not_scheduled_on_recovery_day_on_five_day_trip(self):
        """On a 5-day trip, Day 3 immediately follows the 26 km Vaishno Devi trek and must
        be preserved for gentle recovery. Patnitop must be scheduled strictly on Day 4+,
        never on Day 3."""
        req = {
            "origin": "Delhi",
            "duration_days": 5,
            "pax": 2,
            "sightseeing_places": ["Patnitop"],
            "travel_style": "balanced",
        }
        plan_res = orchestrator.coordinate_plan(req)
        self.assertEqual(plan_res["status"], "PLAN_READY")

        feasible = plan_res.get("feasible_places", [])
        self.assertIn("Patnitop", feasible)

        itinerary = plan_res.get("itinerary") or []
        self.assertEqual(len(itinerary), 5)

        # Day 2 is the holy trek
        day2 = itinerary[1]
        self.assertIn("Dedicated Holy Yatra", day2["title"])
        self.assertFalse(any("Patnitop" in act for act in day2["activities"]))

        # Day 3 is Post-Trek Recovery (protected gentle leisure)
        day3 = itinerary[2]
        self.assertIn("Post-Trek Recovery", day3["title"])
        self.assertEqual(day3["exertion_level"], "Light")
        self.assertFalse(any("Patnitop" in act for act in day3["activities"]))

        # Day 4 is the Regional Excursion Day where Patnitop is scheduled
        day4 = itinerary[3]
        self.assertIn("Patnitop", day4["title"])
        self.assertTrue(any("Patnitop" in act for act in day4["activities"]))

    # -------------------------------------------------------------------------
    # Regression Test 4: 'Also add Patnitop to our trip' updates active plan
    # -------------------------------------------------------------------------
    def test_add_patnitop_replanning_updates_active_plan_not_generic_tourism(self):
        """When an active plan exists, 'Also add Patnitop to our trip' must route to
        replanning, updating plan_version and itinerary, not generic tourism Q&A."""
        # 1. Establish initial 5-day confirmed plan
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 5-day trip from Delhi for 2 people with Baba Dhansar"
        )
        self.assertEqual(res1["status"], "PLAN_READY")
        sid = res1["session_id"]
        v1 = res1["plan_version"]

        # 2. Issue itinerary modification query
        res2 = orchestrator.orchestrate_conversational_turn(
            "Also add Patnitop to our trip",
            session_id=sid,
        )
        self.assertEqual(res2["intent"], "TRIP_PLANNING")
        self.assertIn(res2["status"], ["PLAN_REVISED", "PLAN_READY"])
        self.assertEqual(res2["plan_version"], v1 + 1)

        # Patnitop must now be in feasible places and scheduled on Day 4
        feasible = res2.get("feasible_places", [])
        self.assertIn("Patnitop", feasible)
        itinerary = res2.get("itinerary") or []
        self.assertEqual(len(itinerary), 5)
        day4 = itinerary[3]
        self.assertTrue(any("Patnitop" in act for act in day4["activities"]))

    # -------------------------------------------------------------------------
    # Regression Test 5: Normal question about Patnitop returns tourism answer
    # -------------------------------------------------------------------------
    def test_informational_question_about_patnitop_receives_tourism_answer(self):
        """When an active plan exists, a normal informational question like
        'Tell me about Patnitop' must receive a pure tourism answer, without
        triggering replanning or mutating the plan version."""
        # 1. Establish initial confirmed plan
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 4-day trip from Delhi for 2 people with Baba Dhansar"
        )
        self.assertEqual(res1["status"], "PLAN_READY")
        sid = res1["session_id"]
        v1 = res1["plan_version"]

        # 2. Informational tourism inquiry
        res2 = orchestrator.orchestrate_conversational_turn(
            "Tell me about Patnitop",
            session_id=sid,
        )
        self.assertEqual(res2["intent"], "TOURISM")
        reply = res2.get("reply", "")
        self.assertIn("Patnitop", reply)

        # Plan version must NOT increment; plan must remain unchanged
        session = session_store.get_session(sid)
        self.assertEqual(session["state"]["plan_version"], v1)

    # -------------------------------------------------------------------------
    # Regression Test 6: Every selected destination is scheduled or in infeasible_places
    # -------------------------------------------------------------------------
    def test_every_selected_destination_accounted_for(self):
        """Every selected destination must either appear in the itinerary's day activities
        or be explicitly listed in infeasible_places with a verified reason. No destination
        can be silently omitted."""
        test_cases = [
            # 3-day trip with 1 trek shrine and 2 off-trek spots
            {
                "duration": 3,
                "places": ["Bhairavnath Temple", "Baba Dhansar", "Eiffel Tower"],
            },
            # 5-day trip with 1 local recovery, 1 distant excursion, and 1 ungrounded spot
            {
                "duration": 5,
                "places": ["Baba Dhansar", "Patnitop", "Atlantis"],
            },
        ]
        for tc in test_cases:
            req = {
                "origin": "Delhi",
                "duration_days": tc["duration"],
                "pax": 2,
                "sightseeing_places": list(tc["places"]),
                "travel_style": "balanced",
            }
            plan_res = orchestrator.coordinate_plan(req)
            self.assertEqual(plan_res["status"], "PLAN_READY")

            itinerary = plan_res.get("itinerary") or []
            all_acts_text = " ".join(" ".join(d.get("activities", [])) + " " + d.get("title", "") for d in itinerary)
            infeasible = plan_res.get("infeasible_places", [])
            infeasible_names = {inf["place"].lower() for inf in infeasible}

            for p in tc["places"]:
                canonical = itinerary_agent.match_place_name(p) or p
                in_itinerary = (p.lower() in all_acts_text.lower()) or (canonical.lower() in all_acts_text.lower())
                in_infeasible = (p.lower() in infeasible_names) or (canonical.lower() in infeasible_names)

                # Destination must be scheduled OR reported infeasible, NEVER silently dropped
                self.assertTrue(
                    in_itinerary or in_infeasible,
                    f"Destination '{p}' was silently omitted! Neither scheduled in itinerary nor present in infeasible_places.",
                )

    # -------------------------------------------------------------------------
    # Regression Test 7: Replanning preserves authorization invalidation & lifecycle
    # -------------------------------------------------------------------------
    def test_replanning_preserves_authorization_invalidation_and_lifecycle(self):
        """When an authorized plan is modified via replanning:
        1. plan_version increments.
        2. authorized_plan_version is invalidated (set to None).
        3. authorization state is revoked with reason 'plan_modified'.
        4. Prior booking is tracked in booking history."""
        # 1. Establish initial plan
        res1 = orchestrator.orchestrate_conversational_turn(
            "Plan a 5-day trip from Delhi for 2 people with Baba Dhansar"
        )
        sid = res1["session_id"]
        v1 = res1["plan_version"]

        # 2. Confirm booking -> Authorization granted for Revision 1 and booking created
        res_confirm1 = orchestrator.orchestrate_conversational_turn(
            "Confirm booking",
            session_id=sid,
        )
        self.assertEqual(res_confirm1["status"], "success")
        self.assertEqual(res_confirm1["plan_version"], v1)
        booking_id = res_confirm1["booking_id"]

        s_auth = session_store.get_session(sid)
        self.assertEqual(s_auth["state"]["authorized_plan_version"], v1)
        self.assertTrue(s_auth["state"]["authorization"]["granted"])

        # 3. Trigger replanning query to modify sightseeing
        res2 = orchestrator.orchestrate_conversational_turn(
            "Also add Patnitop to our trip",
            session_id=sid,
        )
        self.assertEqual(res2["status"], "PLAN_REVISED")
        v2 = res2["plan_version"]
        self.assertEqual(v2, v1 + 1)

        # 5. Verify server-side session protections
        updated_session = session_store.get_session(sid)
        state = updated_session["state"]
        self.assertEqual(state["plan_version"], v2)
        # Authorization must be invalidated
        self.assertIsNone(state["authorized_plan_version"])
        self.assertFalse(state["authorization"]["granted"])
        self.assertEqual(state["authorization"]["revoked_reason"], "plan_modified")

        # Booking history must preserve the revision 1 booking
        history = state.get("booking_history", [])
        self.assertTrue(any(b["booking_id"] == booking_id for b in history))
        self.assertEqual(state["rpa_execution"]["status"], "PENDING_RECONFIRMATION")


if __name__ == "__main__":
    unittest.main()

