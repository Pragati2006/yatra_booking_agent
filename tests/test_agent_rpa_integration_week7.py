"""
tests/test_agent_rpa_integration_week7.py
Comprehensive automated test suite for Week 7 Assignment:
AGENT-RPA INTEGRATION LAYER

Covers all 17 required evaluation scenarios:
1. Availability tool registration with the LangChain agent.
2. Correct tool selection for a natural-language availability request.
3. Correct date extraction and ISO conversion.
4. Correct category extraction.
5. Correct argument passing to the RPA function.
6. Missing date triggers a clarification rather than an invented value.
7. Invalid date is rejected.
8. Unsupported category is rejected.
9. Successful structured availability results are interpreted correctly.
10. Empty availability is handled correctly.
11. Week 6 handover results are presented correctly.
12. General tourism questions do not unnecessarily trigger RPA.
13. Follow-up requests use conversation context correctly.
14. Week 4 booking workflow remains intact.
15. Week 5 availability extraction remains intact.
16. Week 6 retry and error-handling behavior remains intact.
17. Existing authorization and plan-version safeguards remain intact.
"""

import os
import sys
import io
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

# Ensure UTF-8 output encoding on Windows consoles safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi.testclient import TestClient
from backend.main import app

from agents import conversation_agent, coordinator, orchestrator, rpa_agent, session_store, tools, availability_agent
import langchain_tools
from langchain_core.tools import BaseTool


class TestAgentRPAIntegrationWeek7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # =========================================================================
    # 1. Availability tool registration with the LangChain agent
    # =========================================================================
    def test_01_tool_registration_with_langchain_agent(self):
        """Verifies check_yatra_availability_tool is registered as a LangChain BaseTool with correct schema."""
        tool = tools.check_yatra_availability_tool
        self.assertIsInstance(tool, BaseTool)
        self.assertEqual(tool.name, "check_yatra_availability_tool")
        self.assertIn("date", tool.args)
        self.assertIn("category", tool.args)

        # Check in get_all_tools()
        all_tools = tools.get_all_tools()
        self.assertIn(tools.check_yatra_availability_tool, all_tools)

        # Check export in langchain_tools
        self.assertIn(langchain_tools.check_yatra_availability, langchain_tools.ALL_LANGCHAIN_TOOLS)
        self.assertEqual(langchain_tools.check_yatra_availability.name, "check_yatra_availability_tool")

    # =========================================================================
    # 2. Correct tool selection for a natural-language availability request
    # =========================================================================
    def test_02_correct_tool_selection_for_natural_language_request(self):
        """Verifies availability query triggers AVAILABILITY intent and tool selection via LangChain agent."""
        query = "Check VIP Darshan availability for 20 November 2026."
        intent = conversation_agent.detect_intent(query)
        self.assertEqual(intent, "AVAILABILITY")

        # Test tool selection with mock LLM using LangChain bind_tools
        mock_llm = MagicMock()
        mock_bound_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_bound_llm

        mock_tool_call_response = MagicMock()
        mock_tool_call_response.tool_calls = [
            {
                "name": "check_yatra_availability_tool",
                "args": {"date": "2026-11-20", "category": "VIP Darshan"},
            }
        ]
        mock_bound_llm.invoke.return_value = mock_tool_call_response

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_tool_invoke:
            mock_tool_invoke.return_value = {
                "status": "SUCCESS",
                "date": "2026-11-20",
                "category_filter": "VIP Darshan",
                "total_slots": 2,
                "available_count": 2,
                "full_count": 0,
                "unavailable_count": 0,
                "slots": [
                    {"slot_id": "SLOT-501", "slot_name": "VIP Darshan", "time": "06:00", "session": "Morning Aarti", "availability_status": "available", "remaining_capacity": 45, "price": 500.0},
                    {"slot_id": "SLOT-502", "slot_name": "VIP Darshan", "time": "18:00", "session": "Evening Aarti", "availability_status": "available", "remaining_capacity": 18, "price": 500.0},
                ],
                "is_empty": False,
            }

            res = availability_agent.run_availability_agent(query, llm=mock_llm)
            self.assertTrue(res["tool_selected"])
            self.assertEqual(res["tool_name"], "check_yatra_availability_tool")
            self.assertEqual(res["tool_args"]["date"], "2026-11-20")
            self.assertEqual(res["tool_args"]["category"], "VIP Darshan")
            mock_tool_invoke.assert_called_once()

    # =========================================================================
    # 3. Correct date extraction and ISO conversion
    # =========================================================================
    def test_03_correct_date_extraction_and_iso_conversion(self):
        """Verifies natural language dates are correctly parsed and converted to ISO YYYY-MM-DD."""
        test_cases = [
            ("Check VIP Darshan availability for 20 November 2026.", "2026-11-20"),
            ("Check slots for 20th Nov 2026", "2026-11-20"),
            ("Are slots open on 20/11/2026?", "2026-11-20"),
            ("Check availability on 20-11-2026", "2026-11-20"),
            ("Check darshan availability November 20, 2026", "2026-11-20"),
            ("Check slots for 2026-10-20", "2026-10-20"),
        ]

        for text, expected_iso in test_cases:
            params = conversation_agent.extract_availability_parameters(text)
            self.assertEqual(params["date"], expected_iso, f"Failed for text: {text}")
            self.assertFalse(params["missing_date"])
            self.assertFalse(params["invalid_date"])

        # Test relative date: tomorrow
        tmr_params = conversation_agent.extract_availability_parameters("Check availability for tomorrow")
        expected_tmr = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(tmr_params["date"], expected_tmr)

    # =========================================================================
    # 4. Correct category extraction
    # =========================================================================
    def test_04_correct_category_extraction(self):
        """Verifies supported categories (Normal, VIP, Helicopter) are correctly extracted and normalized."""
        p_vip = conversation_agent.extract_availability_parameters("Check VIP Darshan availability for 2026-10-20")
        self.assertEqual(p_vip["category"], "VIP Darshan")

        p_norm = conversation_agent.extract_availability_parameters("Check Normal Darshan slots for 2026-10-20")
        self.assertEqual(p_norm["category"], "Normal Darshan")

        p_heli = conversation_agent.extract_availability_parameters("Check helicopter tickets for 2026-10-20")
        self.assertEqual(p_heli["category"], "Helicopter Darshan")

        p_none = conversation_agent.extract_availability_parameters("Check darshan availability for 2026-10-20")
        self.assertIsNone(p_none["category"])

    # =========================================================================
    # 5. Correct argument passing to the RPA function
    # =========================================================================
    def test_05_correct_argument_passing_to_rpa_function(self):
        """Verifies orchestrator passes extracted date and category accurately to check_yatra_availability_tool."""
        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            mock_rpa.return_value = {
                "status": "SUCCESS",
                "date": "2026-11-20",
                "category_filter": "VIP Darshan",
                "total_slots": 2,
                "available_count": 2,
                "full_count": 0,
                "unavailable_count": 0,
                "slots": [],
                "is_empty": False,
            }

            res = orchestrator.orchestrate_conversational_turn(
                user_text="Check VIP Darshan availability for 20 November 2026."
            )
            self.assertEqual(res["intent"], "AVAILABILITY")
            mock_rpa.assert_called_once_with(requested_date="2026-11-20", category="VIP Darshan", headless=True)

    # =========================================================================
    # 6. Missing date triggers a clarification rather than an invented value
    # =========================================================================
    def test_06_missing_date_triggers_clarification_no_invention(self):
        """Verifies query without a date asks for clarification and does not fabricate a date."""
        res = orchestrator.orchestrate_conversational_turn("Check availability.")
        self.assertEqual(res["intent"], "AVAILABILITY")
        self.assertEqual(res["status"], "NEEDS_INFO")
        self.assertTrue(res["extracted_params"]["missing_date"])
        self.assertIsNone(res["extracted_params"]["date"])
        self.assertIn("specify your preferred date", res["reply"].lower())

    # =========================================================================
    # 7. Invalid date is rejected
    # =========================================================================
    def test_07_invalid_date_is_rejected(self):
        """Verifies mathematically/calendarly impossible dates (e.g., Feb 31) are rejected."""
        res = orchestrator.orchestrate_conversational_turn("Check availability for 31 February 2026.")
        self.assertEqual(res["intent"], "AVAILABILITY")
        self.assertEqual(res["status"], "INVALID_INPUT")
        self.assertTrue(res["extracted_params"]["invalid_date"])
        self.assertIn("invalid", res["reply"].lower())

    # =========================================================================
    # 8. Unsupported category is rejected
    # =========================================================================
    def test_08_unsupported_category_is_rejected(self):
        """Verifies unsupported category triggers polite rejection and supported category listing."""
        res = orchestrator.orchestrate_conversational_turn("Check Super VIP availability for 20 November 2026.")
        self.assertEqual(res["intent"], "AVAILABILITY")
        self.assertEqual(res["status"], "UNSUPPORTED_CATEGORY")
        self.assertTrue(res["extracted_params"]["unsupported_category"])
        self.assertIn("not recognized", res["reply"].lower())
        self.assertIn("Normal Darshan", res["reply"])
        self.assertIn("VIP Darshan", res["reply"])
        self.assertIn("Helicopter Darshan", res["reply"])

    # =========================================================================
    # 9. Successful structured availability results are interpreted correctly
    # =========================================================================
    def test_09_successful_structured_availability_interpreted_correctly(self):
        """Verifies structured slot results are formatted into natural language with times, status, and prices."""
        mock_result = {
            "status": "SUCCESS",
            "date": "2026-11-20",
            "category_filter": "VIP Darshan",
            "total_slots": 2,
            "available_count": 2,
            "full_count": 0,
            "unavailable_count": 0,
            "slots": [
                {"slot_id": "SLOT-501", "slot_name": "VIP Darshan", "time": "06:00", "session": "Morning VIP Aarti", "availability_status": "available", "remaining_capacity": 45, "price": 500.0},
                {"slot_id": "SLOT-502", "slot_name": "VIP Darshan", "time": "18:00", "session": "Evening VIP Aarti", "availability_status": "available", "remaining_capacity": 18, "price": 500.0},
            ],
            "is_empty": False,
        }
        reply = conversation_agent.format_availability_reply(mock_result, "2026-11-20", "VIP Darshan")
        self.assertIn("SLOT-501", reply)
        self.assertIn("06:00", reply)
        self.assertIn("Morning VIP Aarti", reply)
        self.assertIn("45 seats left", reply)
        self.assertIn("₹500", reply)
        self.assertIn("Jai Mata Di", reply)

    # =========================================================================
    # 10. Empty availability is handled correctly
    # =========================================================================
    def test_10_empty_availability_handled_correctly(self):
        """Verifies empty availability calendar is reported clearly and not described as a system error."""
        mock_empty = {
            "status": "SUCCESS",
            "date": "2026-11-28",
            "total_slots": 0,
            "slots": [],
            "is_empty": True,
        }
        reply = conversation_agent.format_availability_reply(mock_empty, "2026-11-28", "Normal Darshan")
        self.assertIn("No yatra darshan slots are currently open", reply)
        self.assertIn("This is not a system error", reply)
        self.assertNotIn("FAILED", reply)

    # =========================================================================
    # 11. Week 6 handover results are presented correctly
    # =========================================================================
    def test_11_week6_handover_results_presented_correctly(self):
        """Verifies Week 6 human handover is presented with clear reason and safety protocol without claiming success."""
        mock_handover = {
            "status": "HANDOVER_REQUIRED",
            "handover_required": True,
            "handover_reason": "Structural page modification: slot container missing.",
            "guidance": "Please verify availability directly on official Shrine Board counters.",
            "retry_attempts_used": 3,
        }
        reply = conversation_agent.format_availability_reply(mock_handover, "2026-10-20")
        self.assertIn("Human Handover Notice", reply)
        self.assertIn("Structural page modification", reply)
        self.assertIn("safely paused", reply)
        self.assertNotIn("found 2 slots", reply)

    # =========================================================================
    # 12. General tourism questions do not unnecessarily trigger RPA
    # =========================================================================
    def test_12_general_tourism_questions_do_not_trigger_rpa(self):
        """Verifies general tourism questions route to TOURISM and do NOT invoke RPA availability checking."""
        tourism_queries = [
            "What is Vaishno Devi Yatra?",
            "Tell me about Ardhkuwari cave",
            "What are the Aarti timings?",
            "What places can I visit near Katra?",
        ]
        for q in tourism_queries:
            intent = conversation_agent.detect_intent(q)
            self.assertEqual(intent, "TOURISM", f"Failed for query: {q}")
            res = orchestrator.orchestrate_conversational_turn(q)
            self.assertEqual(res["intent"], "TOURISM")
            self.assertNotEqual(res.get("tool_execution", {}).get("tool"), "check_yatra_availability_tool")

    # =========================================================================
    # 13. Follow-up requests use conversation context correctly
    # =========================================================================
    def test_13_follow_up_requests_use_conversation_context(self):
        """Verifies follow-up query 'Are any slots available on that date?' uses date from previous turn."""
        session = session_store.create_session(initial_state={
            "last_availability_date": "2026-11-20",
            "last_availability_category": "VIP Darshan",
        })
        sid = session["session_id"]

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            mock_rpa.return_value = {
                "status": "SUCCESS",
                "date": "2026-11-20",
                "total_slots": 1,
                "available_count": 1,
                "full_count": 0,
                "unavailable_count": 0,
                "slots": [],
                "is_empty": False,
            }

            res = orchestrator.orchestrate_conversational_turn(
                user_text="Are any slots available on that date?",
                session_id=sid,
            )
            self.assertEqual(res["intent"], "AVAILABILITY")
            self.assertEqual(res["extracted_params"]["date"], "2026-11-20")

    # =========================================================================
    # 14. Week 4 booking workflow remains intact
    # =========================================================================
    def test_14_week4_booking_workflow_remains_intact(self):
        """Verifies Week 4 Playwright mock booking execution remains intact."""
        booking_res = rpa_agent.execute_playwright_mock_booking(
            user_name="Test-Week7",
            pax_count=2,
            transport_text="train from Delhi",
            slot_text="VIP Darshan",
            total_price=2400.0,
            headless=True,
        )
        self.assertEqual(booking_res["status"].upper(), "SUCCESS")
        self.assertTrue(booking_res["booking_id"].startswith("VD-RPA-"))

    # =========================================================================
    # 15. Week 5 availability extraction remains intact
    # =========================================================================
    def test_15_week5_availability_extraction_remains_intact(self):
        """Verifies Week 5 direct availability navigation and structured slot extraction remains intact."""
        res = rpa_agent.check_yatra_slot_availability(
            requested_date="2026-10-20",
            category="Normal Darshan",
            headless=True,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(res["total_slots"], 0)
        self.assertIn("SLOT-", res["slots"][0]["slot_id"])

    # =========================================================================
    # 16. Week 6 retry and error-handling behavior remains intact
    # =========================================================================
    def test_16_week6_retry_and_error_handling_intact(self):
        """Verifies Week 6 pause-and-handover is triggered when structural portal changes are encountered."""
        malformed_html = "<html><body><div id='calendarSection'><div id='slotsContainer'><div id='slotsList'><div class='slot-card'>BROKEN NO ATTRS</div></div></div></div></body></html>"
        res = rpa_agent.check_yatra_slot_availability(
            requested_date="2026-10-20",
            portal_html=malformed_html,
            headless=True,
            enable_retry=False,
        )
        self.assertEqual(res["status"], "HANDOVER_REQUIRED")
        self.assertTrue(res["handover_required"])

    # =========================================================================
    # 17. Existing authorization and plan-version safeguards remain intact
    # =========================================================================
    def test_17_authorization_and_plan_version_safeguards_intact(self):
        """Verifies availability check is read-only and does NOT bypass human authorization or mutate plan versions."""
        session = session_store.create_session(initial_state={
            "plan_version": 2,
            "authorization": {"granted": False},
        })
        sid = session["session_id"]

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            mock_rpa.return_value = {
                "status": "SUCCESS",
                "date": "2026-11-20",
                "total_slots": 2,
                "slots": [],
                "is_empty": False,
            }

            res = orchestrator.orchestrate_conversational_turn(
                user_text="Check VIP Darshan availability for 20 November 2026.",
                session_id=sid,
            )
            # Plan version must not increment on read-only check
            updated_session = session_store.get_session(sid)
            self.assertEqual(updated_session["state"].get("plan_version", 2), 2)
            # Authorization must remain ungranted
            self.assertFalse(updated_session["state"].get("authorization", {}).get("granted", False))

    # =========================================================================
    # 18. Genuine tool-calling cycle from Orchestrator through LLM to Chat
    # =========================================================================
    def test_18_orchestrator_genuine_tool_calling_cycle(self):
        """Verifies full genuine cycle:
        User -> Orchestrator -> LLM bind_tools -> tool call -> Playwright -> ToolMessage -> LLM interpretation -> Final Reply.
        """
        mock_llm = MagicMock()
        mock_bound_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_bound_llm

        # 1. LLM emits tool call
        mock_tool_call_response = MagicMock()
        mock_tool_call_response.tool_calls = [
            {
                "id": "call_test_orchestrator_1",
                "name": "check_yatra_availability_tool",
                "args": {"date": "2026-11-20", "category": "VIP Darshan"},
            }
        ]
        mock_bound_llm.invoke.return_value = mock_tool_call_response

        # 2. LLM receives ToolMessage and emits final natural language interpretation
        mock_final_response = MagicMock()
        mock_final_response.content = "🙏 Jai Mata Di! The LLM confirms 2 VIP Darshan slots are available on 20 November 2026."
        mock_llm.invoke.return_value = mock_final_response

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            mock_rpa.return_value = {
                "status": "SUCCESS",
                "date": "2026-11-20",
                "category_filter": "VIP Darshan",
                "total_slots": 2,
                "available_count": 2,
                "full_count": 0,
                "unavailable_count": 0,
                "slots": [
                    {"slot_id": "SLOT-501", "slot_name": "VIP Darshan", "time": "06:00", "session": "Morning Aarti", "availability_status": "available", "remaining_capacity": 45, "price": 500.0},
                ],
                "is_empty": False,
            }

            res = orchestrator.orchestrate_conversational_turn(
                user_text="Check VIP Darshan availability for 20 November 2026.",
                llm=mock_llm,
            )

            # Assertions:
            self.assertEqual(res["intent"], "AVAILABILITY")
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["execution_mode"], "llm_tool_calling")
            self.assertEqual(res["tool_execution"]["execution_mode"], "llm_tool_calling")
            self.assertEqual(res["tool_execution"]["tool"], "check_yatra_availability_tool")
            
            # Verify LLM selected tool and passed correct parameters
            mock_bound_llm.invoke.assert_called_once()
            mock_rpa.assert_called_once_with(requested_date="2026-11-20", category="VIP Darshan", headless=True)
            self.assertEqual(mock_rpa.call_count, 1)

            # Verify tool result returned to LLM (Step 6)
            mock_llm.invoke.assert_called_once()
            followup_call_args = mock_llm.invoke.call_args[0][0]
            # Check ToolMessage in conversation history
            from langchain_core.messages import ToolMessage
            tool_msg_found = any(isinstance(m, ToolMessage) and getattr(m, 'tool_call_id', None) == "call_test_orchestrator_1" for m in followup_call_args)
            self.assertTrue(tool_msg_found)

            # Verify final answer reached chat response (Step 7)
            self.assertIn("The LLM confirms 2 VIP Darshan slots", res["reply"])

    # =========================================================================
    # 19. Missing Groq API key triggers deterministic fallback
    # =========================================================================
    def test_19_missing_groq_key_triggers_deterministic_fallback(self):
        """Verifies missing credentials smoothly trigger deterministic fallback with clear metadata."""
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
            availability_agent.get_groq_llm.cache_clear()
            with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
                mock_rpa.return_value = {
                    "status": "SUCCESS",
                    "date": "2026-11-20",
                    "category_filter": "VIP Darshan",
                    "total_slots": 1,
                    "available_count": 1,
                    "full_count": 0,
                    "unavailable_count": 0,
                    "slots": [],
                    "is_empty": False,
                }
                res = orchestrator.orchestrate_conversational_turn(
                    user_text="Check VIP Darshan availability for 20 November 2026."
                )
                self.assertEqual(res["intent"], "AVAILABILITY")
                self.assertEqual(res["execution_mode"], "deterministic_fallback")
                self.assertEqual(res["tool_execution"]["execution_mode"], "deterministic_fallback")
                mock_rpa.assert_called_once()

    # =========================================================================
    # 20. API failure / exception triggers deterministic fallback
    # =========================================================================
    def test_20_api_failure_triggers_deterministic_fallback(self):
        """Verifies that if LLM/API call raises an exception, the agent falls back to deterministic extraction."""
        failing_llm = MagicMock()
        failing_bound_llm = MagicMock()
        failing_llm.bind_tools.return_value = failing_bound_llm
        failing_bound_llm.invoke.side_effect = RuntimeError("Groq API 503 Service Unavailable")

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            mock_rpa.return_value = {
                "status": "SUCCESS",
                "date": "2026-11-20",
                "category_filter": "VIP Darshan",
                "total_slots": 1,
                "available_count": 1,
                "full_count": 0,
                "unavailable_count": 0,
                "slots": [],
                "is_empty": False,
            }
            res = orchestrator.orchestrate_conversational_turn(
                user_text="Check VIP Darshan availability for 20 November 2026.",
                llm=failing_llm,
            )
            self.assertEqual(res["intent"], "AVAILABILITY")
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["execution_mode"], "deterministic_fallback")
            mock_rpa.assert_called_once()

    # =========================================================================
    # 21. Malformed tool call with invalid date does not execute Playwright
    # =========================================================================
    def test_21_malformed_tool_call_invalid_date_rejected_before_playwright(self):
        """Verifies LLM generating an invalid date in tool args is rejected and never calls Playwright."""
        mock_llm = MagicMock()
        mock_bound_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_bound_llm

        mock_tool_call_response = MagicMock()
        mock_tool_call_response.tool_calls = [
            {
                "id": "call_bad_date",
                "name": "check_yatra_availability_tool",
                "args": {"date": "2026-02-31", "category": "Normal Darshan"},
            }
        ]
        mock_bound_llm.invoke.return_value = mock_tool_call_response

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            res = orchestrator.orchestrate_conversational_turn(
                user_text="Check availability for 31 February 2026.",
                llm=mock_llm,
            )
            self.assertEqual(res["intent"], "AVAILABILITY")
            self.assertEqual(res["status"], "INVALID_INPUT")
            self.assertIn("invalid", res["reply"].lower())
            # Playwright MUST NOT have been called
            mock_rpa.assert_not_called()

    # =========================================================================
    # 22. Malformed tool call with unsupported category rejected before Playwright
    # =========================================================================
    def test_22_malformed_tool_call_unsupported_category_rejected_before_playwright(self):
        """Verifies LLM generating an unsupported category in tool args is rejected and never calls Playwright."""
        mock_llm = MagicMock()
        mock_bound_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_bound_llm

        mock_tool_call_response = MagicMock()
        mock_tool_call_response.tool_calls = [
            {
                "id": "call_bad_cat",
                "name": "check_yatra_availability_tool",
                "args": {"date": "2026-11-20", "category": "Super VIP"},
            }
        ]
        mock_bound_llm.invoke.return_value = mock_tool_call_response

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            res = orchestrator.orchestrate_conversational_turn(
                user_text="Check Super VIP availability for 20 November 2026.",
                llm=mock_llm,
            )
            self.assertEqual(res["intent"], "AVAILABILITY")
            self.assertEqual(res["status"], "UNSUPPORTED_CATEGORY")
            self.assertIn("Normal Darshan", res["reply"])
            # Playwright MUST NOT have been called
            mock_rpa.assert_not_called()

    # =========================================================================
    # 23. Verification of single Playwright execution (no duplicates)
    # =========================================================================
    def test_23_no_duplicate_playwright_invocation(self):
        """Verifies that throughout the turn, Playwright is invoked exactly once and never duplicated."""
        mock_llm = MagicMock()
        mock_bound_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_bound_llm

        mock_tool_call_response = MagicMock()
        mock_tool_call_response.tool_calls = [
            {
                "id": "call_once",
                "name": "check_yatra_availability_tool",
                "args": {"date": "2026-11-20", "category": "Normal Darshan"},
            }
        ]
        mock_bound_llm.invoke.return_value = mock_tool_call_response
        mock_llm.invoke.return_value = MagicMock(content="Verified once.")

        with patch("agents.rpa_agent.check_yatra_slot_availability") as mock_rpa:
            mock_rpa.return_value = {
                "status": "SUCCESS",
                "date": "2026-11-20",
                "category_filter": "Normal Darshan",
                "total_slots": 1,
                "available_count": 1,
                "full_count": 0,
                "unavailable_count": 0,
                "slots": [],
                "is_empty": False,
            }
            res = orchestrator.orchestrate_conversational_turn(
                user_text="Check Normal Darshan slots for 20 November 2026.",
                llm=mock_llm,
            )
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(mock_rpa.call_count, 1)


if __name__ == "__main__":
    unittest.main()
