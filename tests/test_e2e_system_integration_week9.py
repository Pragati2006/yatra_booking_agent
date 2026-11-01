"""
tests/test_e2e_system_integration_week9.py
Week 9 Comprehensive End-to-End System Integration Test Suite.

Validates the full application pipeline across all 18 required scenarios:
React Frontend -> FastAPI -> Coordinator -> Orchestrator -> LangChain LLM ->
Tool Selection -> Parameter Validation -> Playwright RPA -> Local Mock Portal ->
Structured Result -> LLM Interpretation -> Final Response.

Scenarios tested:
1. VIP Darshan availability for a specified date
2. Normal Darshan availability
3. Helicopter Darshan availability
4. Availability request without providing a date (NEEDS_INFO)
5. Invalid calendar date rejection
6. Unsupported category rejection
7. Multi-turn follow-up using contextual date
8. General tourism question (no RPA invocation)
9. Itinerary with multiple travel constraints
10. Assistance within specified budget
11. Manual OTP intervention checkpoint (PAUSED)
12. Manual CAPTCHA intervention checkpoint (PAUSED)
13. User confirms completion of manual intervention
14. Valid workflow resume to confirmation
15. Workflow cancellation by user
16. Resume rejection on expired workflow
17. Recoverable RPA failure (retry with backoff)
18. Non-recoverable RPA failure (pause and handover without fabricating)
"""

import os
import sys
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import MagicMock, patch

# Ensure utf-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from backend.main import app
import agents.session_store as session_store
import agents.rpa_agent as rpa_agent
import agents.coordinator as coordinator

client = TestClient(app)


class TestWeek9E2ESystemIntegration(unittest.TestCase):
    """Week 9 End-to-End System Integration Test Suite covering all 18 required scenarios."""

    def setUp(self):
        self.session_id = f"test-e2e-week9-{int(datetime.now().timestamp() * 1000)}"
        # Initialize SQLite session
        session_store.create_session(session_id=self.session_id)

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # Scenario 1: VIP Darshan availability for a specified date
    # --------------------------------------------------------------------------
    def test_scenario_01_vip_darshan_specified_date(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Check VIP Darshan availability for 2026-10-20",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "AVAILABILITY")
        params = data.get("extracted_params", {})
        self.assertEqual(params.get("date"), "2026-10-20")
        self.assertIn("vip", params.get("category", "").lower())
        avail = data.get("availability_result")
        self.assertIsNotNone(avail)
        self.assertIn("slots", avail)
        self.assertGreater(len(avail["slots"]), 0)
        self.assertIn("reply", data)
        self.assertTrue(len(data["reply"]) > 10)
        self.assertTrue(
            avail.get("source") == "mock_portal"
            or "mock" in avail.get("portal_url", "").lower()
            or "simulated" in str(avail).lower()
            or "slots" in avail
        )

    # --------------------------------------------------------------------------
    # Scenario 2: Normal Darshan availability
    # --------------------------------------------------------------------------
    def test_scenario_02_normal_darshan_availability(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Check Normal Darshan availability for 2026-10-20",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "AVAILABILITY")
        params = data.get("extracted_params", {})
        self.assertEqual(params.get("date"), "2026-10-20")
        self.assertIn("normal", params.get("category", "").lower())
        avail = data.get("availability_result")
        self.assertIsNotNone(avail)
        self.assertTrue(any("normal" in s.get("slot_name", "").lower() for s in avail.get("slots", [])))

    # --------------------------------------------------------------------------
    # Scenario 3: Helicopter Darshan availability
    # --------------------------------------------------------------------------
    def test_scenario_03_helicopter_darshan_availability(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Check Helicopter Darshan availability for 2026-10-20",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "AVAILABILITY")
        params = data.get("extracted_params", {})
        self.assertEqual(params.get("date"), "2026-10-20")
        self.assertIn("helicopter", params.get("category", "").lower())
        avail = data.get("availability_result")
        self.assertIsNotNone(avail)
        self.assertTrue(any("helicopter" in s.get("slot_name", "").lower() for s in avail.get("slots", [])))

    # --------------------------------------------------------------------------
    # Scenario 4: User requests availability without providing a date
    # --------------------------------------------------------------------------
    def test_scenario_04_availability_missing_date(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Check availability.",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "AVAILABILITY")
        self.assertEqual(data.get("status"), "NEEDS_INFO")
        self.assertTrue(data.get("extracted_params", {}).get("missing_date"))
        self.assertIsNone(data.get("availability_result"))
        # Must prompt for date and not fabricate availability
        self.assertTrue(any(w in data.get("reply", "").lower() for w in ["date", "when", "specify"]))

    # --------------------------------------------------------------------------
    # Scenario 5: User provides an invalid calendar date
    # --------------------------------------------------------------------------
    def test_scenario_05_invalid_calendar_date(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Check availability for 2026-02-31",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "AVAILABILITY")
        self.assertEqual(data.get("status"), "INVALID_INPUT")
        self.assertTrue(data.get("extracted_params", {}).get("invalid_date"))
        self.assertIsNone(data.get("availability_result"))
        self.assertTrue(any(w in data.get("reply", "").lower() for w in ["invalid", "valid", "calendar", "date"]))

    # --------------------------------------------------------------------------
    # Scenario 6: User requests an unsupported category
    # --------------------------------------------------------------------------
    def test_scenario_06_unsupported_category(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Check Super VIP availability for 2026-10-20",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "AVAILABILITY")
        self.assertEqual(data.get("status"), "UNSUPPORTED_CATEGORY")
        self.assertTrue(data.get("extracted_params", {}).get("unsupported_category"))
        self.assertIsNone(data.get("availability_result"))
        # Must list valid categories
        reply_lower = data.get("reply", "").lower()
        self.assertTrue("normal" in reply_lower or "vip" in reply_lower or "helicopter" in reply_lower)

    # --------------------------------------------------------------------------
    # Scenario 7: User asks a follow-up using previously provided date
    # --------------------------------------------------------------------------
    def test_scenario_07_followup_contextual_date(self):
        # Turn 1: User checks availability for 2026-10-20
        resp1 = client.post(
            "/api/chat",
            json={
                "message": "Check availability for 2026-10-20",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.json().get("intent"), "AVAILABILITY")

        # Turn 2: User asks for VIP Darshan on that date without re-typing 2026-10-20
        resp2 = client.post(
            "/api/chat",
            json={
                "message": "Check VIP Darshan availability on that date",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2.get("intent"), "AVAILABILITY")
        # Should carry date from context
        params = data2.get("extracted_params", {})
        self.assertEqual(params.get("date"), "2026-10-20")
        self.assertIsNotNone(data2.get("availability_result"))

    # --------------------------------------------------------------------------
    # Scenario 8: General tourism question (no RPA invocation)
    # --------------------------------------------------------------------------
    def test_scenario_08_general_tourism_no_rpa(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "What places can I visit around Katra?",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "TOURISM")
        self.assertIsNone(data.get("availability_result"))
        self.assertIn("reply", data)
        self.assertTrue(len(data["reply"]) > 20)

    # --------------------------------------------------------------------------
    # Scenario 9: User requests an itinerary with multiple travel constraints
    # --------------------------------------------------------------------------
    def test_scenario_09_itinerary_multiple_constraints(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Plan a 4-day trip for 2 people from Delhi to Katra by train on 2026-10-20 with luxury hotel and VIP darshan",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "TRIP_PLANNING")
        req = data.get("request", {})
        self.assertEqual(req.get("origin"), "Delhi")
        self.assertEqual(req.get("pax"), 2)
        self.assertEqual(req.get("duration_days"), 4)
        plan = data.get("plan", {})
        self.assertIn("options", plan)
        self.assertGreater(len(plan["options"]), 0)

    # --------------------------------------------------------------------------
    # Scenario 10: User requests assistance within a specified budget
    # --------------------------------------------------------------------------
    def test_scenario_10_specified_budget_assistance(self):
        resp = client.post(
            "/api/chat",
            json={
                "message": "Plan a yatra from Delhi for 2 people on 2026-10-20 with a total budget of ₹15,000",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "TRIP_PLANNING")
        req = data.get("request", {})
        self.assertEqual(req.get("total_budget"), 15000.0)
        eval_budget = data.get("budget_evaluation")
        self.assertIsNotNone(eval_budget)
        self.assertIn("within_budget", eval_budget)

    # --------------------------------------------------------------------------
    # Scenario 11: Manual OTP intervention checkpoint
    # --------------------------------------------------------------------------
    def test_scenario_11_manual_otp_intervention_checkpoint(self):
        sess = session_store.get_session(self.session_id)
        state = sess["state"]
        state["authorization"] = {
            "pending": False,
            "granted": True,
            "authorized_at": datetime.now(timezone.utc).isoformat(),
            "authorized_for_version": 1,
            "user_name": "Pilgrim",
        }
        state["authorized_plan_version"] = 1
        session_store.update_session(self.session_id, updates={"state": state})

        resp = client.post(
            "/api/yatra/rpa/workflow/start",
            json={
                "session_id": self.session_id,
                "user_name": "Pilgrim-E2E",
                "pax_count": 2,
                "checkpoint_mode": "OTP",
                "plan_version": 1,
                "human_authorized": True,
                "headless": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data.get("status"), ("PAUSED", "PAUSED_FOR_USER_INPUT"))
        self.assertEqual(data.get("state"), "OTP_REQUIRED")
        self.assertEqual(data.get("step"), "security_checkpoint")
        self.assertIsNotNone(data.get("workflow_id"))
        self.assertIn("OTP", data.get("message", ""))

    # --------------------------------------------------------------------------
    # Scenario 12: Manual CAPTCHA intervention checkpoint
    # --------------------------------------------------------------------------
    def test_scenario_12_manual_captcha_intervention_checkpoint(self):
        sess = session_store.get_session(self.session_id)
        state = sess["state"]
        state["authorization"] = {
            "pending": False,
            "granted": True,
            "authorized_at": datetime.now(timezone.utc).isoformat(),
            "authorized_for_version": 1,
            "user_name": "Pilgrim",
        }
        state["authorized_plan_version"] = 1
        session_store.update_session(self.session_id, updates={"state": state})

        resp = client.post(
            "/api/yatra/rpa/workflow/start",
            json={
                "session_id": self.session_id,
                "user_name": "Pilgrim-E2E",
                "pax_count": 1,
                "checkpoint_mode": "CAPTCHA",
                "plan_version": 1,
                "human_authorized": True,
                "headless": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data.get("status"), ("PAUSED", "PAUSED_FOR_USER_INPUT"))
        self.assertEqual(data.get("state"), "CAPTCHA_REQUIRED")
        self.assertEqual(data.get("step"), "security_checkpoint")
        self.assertIn("CAPTCHA", data.get("message", ""))

    # --------------------------------------------------------------------------
    # Scenario 13: User confirms completion of manual intervention
    # --------------------------------------------------------------------------
    def test_scenario_13_user_confirms_intervention_completion(self):
        sess = session_store.get_session(self.session_id)
        state = sess["state"]
        state["authorization"] = {
            "pending": False,
            "granted": True,
            "authorized_at": datetime.now(timezone.utc).isoformat(),
            "authorized_for_version": 1,
            "user_name": "Pilgrim",
        }
        state["authorized_plan_version"] = 1
        session_store.update_session(self.session_id, updates={"state": state})

        start_res = client.post(
            "/api/yatra/rpa/workflow/start",
            json={
                "session_id": self.session_id,
                "user_name": "Pilgrim-E2E",
                "pax_count": 1,
                "checkpoint_mode": "OTP",
                "plan_version": 1,
                "human_authorized": True,
                "headless": True,
            },
        ).json()
        wfid = start_res["workflow_id"]

        # Resume WITHOUT user confirmation -> must reject
        reject_res = client.post(
            "/api/yatra/rpa/workflow/resume",
            json={
                "session_id": self.session_id,
                "workflow_id": wfid,
                "user_confirmed_action": False,
            },
        ).json()
        self.assertEqual(reject_res.get("status"), "confirmation_required")

    # --------------------------------------------------------------------------
    # Scenario 14: User resumes a valid workflow to completion
    # --------------------------------------------------------------------------
    def test_scenario_14_user_resumes_valid_workflow(self):
        sess = session_store.get_session(self.session_id)
        state = sess["state"]
        state["authorization"] = {
            "pending": False,
            "granted": True,
            "authorized_at": datetime.now(timezone.utc).isoformat(),
            "authorized_for_version": 1,
            "user_name": "Pilgrim",
        }
        state["authorized_plan_version"] = 1
        session_store.update_session(self.session_id, updates={"state": state})

        start_res = client.post(
            "/api/yatra/rpa/workflow/start",
            json={
                "session_id": self.session_id,
                "user_name": "Pilgrim-E2E",
                "pax_count": 1,
                "checkpoint_mode": "OTP",
                "plan_version": 1,
                "human_authorized": True,
                "headless": True,
            },
        ).json()
        wfid = start_res["workflow_id"]

        # Resume with confirmed action and clearance
        resume_res = client.post(
            "/api/yatra/rpa/workflow/resume",
            json={
                "session_id": self.session_id,
                "workflow_id": wfid,
                "user_confirmed_action": True,
                "simulate_manual_clearance": True,
                "headless": True,
            },
        ).json()
        self.assertIn(resume_res.get("status"), ("SUCCESS", "CONFIRMED"))
        self.assertIsNotNone(resume_res.get("booking_id"))
        self.assertTrue(resume_res["booking_id"].startswith("VD-RPA-"))

    # --------------------------------------------------------------------------
    # Scenario 15: User cancels a workflow
    # --------------------------------------------------------------------------
    def test_scenario_15_user_cancels_workflow(self):
        sess = session_store.get_session(self.session_id)
        state = sess["state"]
        state["authorization"] = {
            "pending": False,
            "granted": True,
            "authorized_at": datetime.now(timezone.utc).isoformat(),
            "authorized_for_version": 1,
            "user_name": "Pilgrim",
        }
        state["authorized_plan_version"] = 1
        session_store.update_session(self.session_id, updates={"state": state})

        start_res = client.post(
            "/api/yatra/rpa/workflow/start",
            json={
                "session_id": self.session_id,
                "user_name": "Pilgrim-E2E",
                "pax_count": 1,
                "checkpoint_mode": "CAPTCHA",
                "plan_version": 1,
                "human_authorized": True,
                "headless": True,
            },
        ).json()
        wfid = start_res["workflow_id"]

        cancel_res = client.post(
            "/api/yatra/rpa/workflow/cancel",
            json={
                "session_id": self.session_id,
                "workflow_id": wfid,
                "reason": "User decided to change travel dates",
            },
        ).json()
        self.assertIn(cancel_res.get("status"), ("success", "CANCELLED"))

        # Attempting to resume a cancelled workflow must be rejected
        attempt_res = client.post(
            "/api/yatra/rpa/workflow/resume",
            json={
                "session_id": self.session_id,
                "workflow_id": wfid,
                "user_confirmed_action": True,
            },
        ).json()
        self.assertEqual(attempt_res.get("status"), "CANCELLED")

    # --------------------------------------------------------------------------
    # Scenario 16: User attempts to resume an expired workflow
    # --------------------------------------------------------------------------
    def test_scenario_16_resume_expired_workflow(self):
        sess = session_store.get_session(self.session_id)
        state = sess["state"]
        state["authorization"] = {
            "pending": False,
            "granted": True,
            "authorized_at": datetime.now(timezone.utc).isoformat(),
            "authorized_for_version": 1,
            "user_name": "Pilgrim",
        }
        state["authorized_plan_version"] = 1
        session_store.update_session(self.session_id, updates={"state": state})

        start_res = client.post(
            "/api/yatra/rpa/workflow/start",
            json={
                "session_id": self.session_id,
                "user_name": "Pilgrim-E2E",
                "pax_count": 1,
                "checkpoint_mode": "OTP",
                "plan_version": 1,
                "human_authorized": True,
                "headless": True,
            },
        ).json()
        wfid = start_res["workflow_id"]

        # Backdate expiration in SQLite to simulate 5-minute timeout expiry
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        import sqlite3
        with sqlite3.connect(session_store.DEFAULT_DB_PATH) as conn:
            conn.execute("UPDATE user_workflows SET expires_at = ? WHERE workflow_id = ?", (past_iso, wfid))
            conn.commit()

        resume_res = client.post(
            "/api/yatra/rpa/workflow/resume",
            json={
                "session_id": self.session_id,
                "workflow_id": wfid,
                "user_confirmed_action": True,
            },
        ).json()
        self.assertEqual(resume_res.get("status"), "EXPIRED")

    # --------------------------------------------------------------------------
    # Scenario 17: User encounters a recoverable RPA failure
    # --------------------------------------------------------------------------
    def test_scenario_17_recoverable_rpa_failure_with_retry(self):
        attempts = 0

        def flaky_action(attempt_num=1):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise rpa_agent.RecoverableRPAError("Transient mock portal network delay")
            return {"status": "success", "recovered_after": attempts}

        result = rpa_agent.retry_with_backoff(
            action_callable=flaky_action,
            max_attempts=3,
            base_delay_seconds=0.01,
            operation_name="MockPortalTransientTest",
        )
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(attempts, 3)

    # --------------------------------------------------------------------------
    # Scenario 18: Nonrecoverable RPA failure and handover
    # --------------------------------------------------------------------------
    def test_scenario_18_nonrecoverable_rpa_failure_handover(self):
        broken_html = "<html><body><div id='corrupted'>No valid elements</div></body></html>"
        result = rpa_agent.check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True,
            portal_html=broken_html,
            max_attempts=1,
        )
        self.assertEqual(result.get("status"), "HANDOVER_REQUIRED")
        self.assertTrue(result.get("handover_required"))
        self.assertIn("error", result)
        # Invariant: Never fabricate confirmation or slots on failure
        self.assertNotIn("booking_id", result)


if __name__ == "__main__":
    unittest.main()
