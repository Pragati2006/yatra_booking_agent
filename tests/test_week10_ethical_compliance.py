"""
tests/test_week10_ethical_compliance.py
Week 10: Ethical Boundary, Data Masking, Structured Logging & Compliance Test Suite.

Covers all 23 mandatory verification areas:
Part A - Data Masking Tests:
  1. Email masking (pragati@example.com -> p*****i@example.com)
  2. OTP redaction (123456 -> [REDACTED])
  3. Session-token redaction (abc123... -> [REDACTED])
  4. API-key redaction (gsk_... -> [REDACTED])
  5. Masking nested dictionaries and request metadata
  6. Handling missing, None, and malformed values gracefully
  7. Confirming that sensitive values never appear in captured logs

Part B - Logging Tests:
  8. Successful RPA workflow logging (milestones, INFO level)
  9. Failed RPA workflow logging (handover, ERROR level)
  10. Retry logging (bounded retry, WARNING level)
  11. Human-handover logging (safety invariants, human_intervention_required)
  12. LangChain tool execution logging (sanitized parameters, tool result)
  13. Authentication failure logging (sanitized, zero plain OTPs)
  14. Safe exception logging (scrubbed tracebacks/messages)
  15. Request/correlation ID propagation (ContextVar and headers)
  16. Correct log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

Part C - Compliance and Privacy Tests:
  17. Official Shrine Board portal (maavaishnodevi.org) is NEVER targeted by automated Playwright routines
  18. Local mock portal availability checking continues to work cleanly
  19. Guest access continues without mandatory authentication
  20. Authenticated user data remains strictly isolated
  21. OTP values are never stored or logged in plaintext
  22. Logout and session revocation continue to revoke access
  23. Existing human authorization safeguards remain strictly enforced
"""

import os
import sys
import io
import time
import uuid
import tempfile
import logging
import inspect
import sqlite3
import unittest
from unittest.mock import patch, MagicMock

# Ensure UTF-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from backend.main import app
import agents.auth_service as auth_module
import agents.session_store as session_store
import agents.rpa_agent as rpa_agent
import agents.coordinator as coordinator
from utils.masking import (
    mask_email,
    mask_otp,
    mask_token,
    mask_api_key,
    mask_phone,
    mask_name,
    mask_sensitive_data,
    sanitize_log_message,
)
from utils.logger import (
    log_event,
    set_correlation_id,
    get_correlation_id,
    SanitizingFormatter,
    StructuredEventLogger,
)


class TestWeek10DataMasking(unittest.TestCase):
    """Part A: Unit tests for data masking utilities."""

    def test_01_email_masking(self):
        """Test standard, edge-case, and malformed email masking."""
        self.assertEqual(mask_email("pragati@example.com"), "p*****i@example.com")
        self.assertEqual(mask_email("john.doe@subdomain.org"), "j******e@subdomain.org")
        # Short usernames
        self.assertEqual(mask_email("ab@domain.com"), "a*b@domain.com")
        self.assertEqual(mask_email("a@domain.com"), "*@domain.com")
        # Missing or invalid emails
        self.assertEqual(mask_email(""), "")
        self.assertEqual(mask_email(None), "")
        self.assertEqual(mask_email("not-an-email"), "[INVALID_EMAIL]")

    def test_02_otp_redaction(self):
        """Test OTP redaction to [REDACTED]."""
        self.assertEqual(mask_otp("123456"), "[REDACTED]")
        self.assertEqual(mask_otp(654321), "[REDACTED]")
        self.assertEqual(mask_otp("9876"), "[REDACTED]")
        self.assertEqual(mask_otp(""), "")
        self.assertEqual(mask_otp(None), "")

    def test_03_session_token_redaction(self):
        """Test session token redaction."""
        self.assertEqual(mask_token("tok_9876543210abcdef"), "[REDACTED]")
        self.assertEqual(mask_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"), "[REDACTED]")
        self.assertEqual(mask_token(""), "")
        self.assertEqual(mask_token(None), "")

    def test_04_api_key_redaction(self):
        """Test API key and secret redaction."""
        self.assertEqual(mask_api_key("gsk_secret1234567890abcdef"), "[REDACTED]")
        self.assertEqual(mask_api_key("sk-ant-api03-abcdef"), "[REDACTED]")
        self.assertEqual(mask_api_key(""), "")
        self.assertEqual(mask_api_key(None), "")

    def test_05_mask_nested_dicts_and_metadata(self):
        """Test recursive masking of sensitive fields in dictionaries and lists."""
        sensitive_payload = {
            "email": "user@example.com",
            "otp_code": "654321",
            "auth_token": "secret_session_token_12345",
            "api_key": "gsk_prod_secret_key_8899",
            "phone_number": "9876543210",
            "user_name": "Ramesh Kumar",
            "operation": "check_availability",
            "plan_version": 2,
            "metadata": {
                "admin_email": "admin@temple.org",
                "request_id": "req-999",
                "nested_secrets": {
                    "token": "tok_deeply_nested",
                    "otp": "112233",
                },
                "travelers": [
                    {"name": "Sita Sharma", "contact": "9876543211"},
                    {"name": "Gita Sharma", "email": "gita@test.com"},
                ],
            },
        }

        masked = mask_sensitive_data(sensitive_payload)

        # Sensitive keys should be redacted or masked
        self.assertEqual(masked["email"], "u**r@example.com")
        self.assertEqual(masked["otp_code"], "[REDACTED]")
        self.assertEqual(masked["auth_token"], "[REDACTED]")
        self.assertEqual(masked["api_key"], "[REDACTED]")
        self.assertEqual(masked["phone_number"], "98*****210")
        self.assertEqual(masked["user_name"], "R***** K*****")

        # Harmless keys must remain untouched
        self.assertEqual(masked["operation"], "check_availability")
        self.assertEqual(masked["plan_version"], 2)

        # Nested metadata
        self.assertEqual(masked["metadata"]["admin_email"], "a***n@temple.org")
        self.assertEqual(masked["metadata"]["request_id"], "req-999")
        self.assertEqual(masked["metadata"]["nested_secrets"]["token"], "[REDACTED]")
        self.assertEqual(masked["metadata"]["nested_secrets"]["otp"], "[REDACTED]")

        # Nested list of travelers
        self.assertEqual(masked["metadata"]["travelers"][0]["name"], "S***** S*****")
        self.assertEqual(masked["metadata"]["travelers"][1]["email"], "g**a@test.com")

    def test_06_handling_missing_and_malformed_values(self):
        """Test masking robustness with None, empty strings, numbers, booleans, and malformed objects."""
        self.assertIsNone(mask_sensitive_data(None))
        self.assertEqual(mask_sensitive_data(""), "")
        self.assertEqual(mask_sensitive_data(123), 123)
        self.assertEqual(mask_sensitive_data(True), True)
        self.assertEqual(mask_phone("123"), "123")  # too short for 10-digit phone
        self.assertEqual(mask_name(""), "")
        self.assertEqual(mask_name(None), "")

    def test_07_sensitive_values_never_appear_in_captured_logs(self):
        """Test regex sanitizer removes emails, API keys, OTPs, MongoDB URIs, and cookies from freeform log strings."""
        raw_msg = (
            "User pragati.test@example.com requested OTP 654321 with key gsk_testsecret12345 "
            "and bearer Bearer secret-auth-token-123456, "
            "connecting to mongodb+srv://admin_user:SuperSecretPassword123@cluster0.mongodb.net/yatra "
            "with cookie yatra_auth_session=abcdef1234567890abcdef"
        )
        sanitized = sanitize_log_message(raw_msg)

        self.assertNotIn("pragati.test@example.com", sanitized)
        self.assertIn("p**********t@example.com", sanitized)
        self.assertNotIn("654321", sanitized)
        self.assertNotIn("gsk_testsecret12345", sanitized)
        self.assertNotIn("secret-auth-token-123456", sanitized)
        self.assertNotIn("SuperSecretPassword123", sanitized)
        self.assertNotIn("admin_user", sanitized)
        self.assertIn("mongodb+srv://[REDACTED]:[REDACTED]@cluster0.mongodb.net/yatra", sanitized)
        self.assertNotIn("abcdef1234567890abcdef", sanitized)
        self.assertIn("yatra_auth_session=[REDACTED]", sanitized)


class TestWeek10StructuredLogging(unittest.TestCase):
    """Part B: Unit tests for structured logging framework and log levels."""

    def setUp(self):
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setFormatter(SanitizingFormatter("%(levelname)s | %(name)s | %(message)s"))
        self.root_logger = logging.getLogger()
        self.root_logger.addHandler(self.handler)
        self.root_logger.setLevel(logging.DEBUG)

    def tearDown(self):
        self.root_logger.removeHandler(self.handler)

    def test_08_successful_rpa_workflow_logging(self):
        """Test logging of successful RPA workflow events."""
        set_correlation_id("test-corr-08")
        log_event(
            logging.INFO,
            "rpa_agent",
            "RPA_AVAILABILITY_CHECK_STARTED",
            "RPA availability check started for date=2026-10-20",
            details={"requested_date": "2026-10-20"}
        )
        log_event(
            logging.INFO,
            "rpa_agent",
            "RPA_WORKFLOW_COMPLETED",
            "RPA availability check completed successfully with 4 slots",
            final_outcome="SUCCESS",
            details={"total_slots": 4}
        )

        log_output = self.log_stream.getvalue()
        self.assertIn("RPA_AVAILABILITY_CHECK_STARTED", log_output)
        self.assertIn("RPA_WORKFLOW_COMPLETED", log_output)
        self.assertIn("test-corr-08", log_output)
        self.assertIn("INFO", log_output)

    def test_09_failed_rpa_workflow_logging(self):
        """Test logging of failed RPA workflows."""
        log_event(
            logging.ERROR,
            "rpa_agent",
            "RPA_WORKFLOW_FAILED",
            "RPA availability check failed due to network timeout",
            error_category="NETWORK_TIMEOUT",
            final_outcome="FAILED",
            human_intervention_required=True
        )
        log_output = self.log_stream.getvalue()
        self.assertIn("RPA_WORKFLOW_FAILED", log_output)
        self.assertIn("NETWORK_TIMEOUT", log_output)
        self.assertIn("ERROR", log_output)

    def test_10_retry_logging(self):
        """Test logging of bounded retry events."""
        log_event(
            logging.WARNING,
            "rpa_agent",
            "RPA_RETRY_INITIATED",
            "Recoverable error in check_yatra_slot_availability. Retrying...",
            error_category="RECOVERABLE_RPA_ERROR",
            retry_attempt=1,
            details={"delay_seconds": 0.5}
        )
        log_output = self.log_stream.getvalue()
        self.assertIn("RPA_RETRY_INITIATED", log_output)
        self.assertIn("WARNING", log_output)
        self.assertIn("retry=1", log_output)

    def test_11_human_handover_logging(self):
        """Test logging of human handover events."""
        log_event(
            logging.ERROR,
            "rpa_agent",
            "RPA_HUMAN_HANDOVER",
            "Human intervention required: structural DOM change detected",
            error_category="STRUCTURAL_CHANGE",
            retry_attempt=3,
            human_intervention_required=True,
            workflow_state="HANDOVER_REQUIRED",
            final_outcome="FAILED"
        )
        log_output = self.log_stream.getvalue()
        self.assertIn("RPA_HUMAN_HANDOVER", log_output)
        self.assertIn("STRUCTURAL_CHANGE", log_output)
        self.assertIn("HITL=True", log_output)

    def test_12_langchain_tool_execution_logging(self):
        """Test logging of agent tool execution events."""
        log_event(
            logging.INFO,
            "agent.availability",
            "AGENT_TOOL_SELECTED",
            "LangChain agent selected tool: check_slot_availability_rpa",
            details={"tool": "check_slot_availability_rpa", "parameters": {"date": "2026-10-20"}}
        )
        log_event(
            logging.INFO,
            "agent.availability",
            "AGENT_TOOL_RESULT",
            "Tool execution completed: returned 4 slots",
            final_outcome="SUCCESS",
            details={"tool": "check_slot_availability_rpa", "status": "SUCCESS"}
        )
        log_output = self.log_stream.getvalue()
        self.assertIn("AGENT_TOOL_SELECTED", log_output)
        self.assertIn("AGENT_TOOL_RESULT", log_output)

    def test_13_authentication_failure_logging(self):
        """Test logging of authentication failures without leaking secrets."""
        log_event(
            logging.WARNING,
            "auth_service",
            "AUTH_VERIFY_FAILED",
            "OTP verification failed for user p*****i@example.com: invalid code",
            error_category="AUTHENTICATION_ERROR",
            details={"email": mask_email("pragati@example.com"), "reason": "code_mismatch"}
        )
        log_output = self.log_stream.getvalue()
        self.assertIn("AUTH_VERIFY_FAILED", log_output)
        self.assertIn("p*****i@example.com", log_output)
        self.assertNotIn("pragati@example.com", log_output)

    def test_14_safe_exception_logging(self):
        """Test that exception logs pass through SanitizingFormatter."""
        try:
            raise ValueError("Exception with secret key gsk_internal_secret_key_123 and user secret@test.com")
        except ValueError as exc:
            self.root_logger.error("Operation failed: %s", exc)

        log_output = self.log_stream.getvalue()
        self.assertNotIn("gsk_internal_secret_key_123", log_output)
        self.assertNotIn("secret@test.com", log_output)
        self.assertIn("s****t@test.com", log_output)

    def test_15_correlation_id_propagation(self):
        """Test correlation ID propagation in structured logger."""
        cid = f"req-{uuid.uuid4().hex[:8]}"
        set_correlation_id(cid)
        self.assertEqual(get_correlation_id(), cid)

        log_event(
            logging.INFO,
            "test_module",
            "TEST_OPERATION",
            "Testing correlation ID propagation"
        )
        log_output = self.log_stream.getvalue()
        self.assertIn(cid, log_output)

    def test_16_correct_log_levels(self):
        """Verify correct usage of log levels."""
        log_event(logging.DEBUG, "module", "DEBUG_OP", "Debug message")
        log_event(logging.INFO, "module", "INFO_OP", "Info message")
        log_event(logging.WARNING, "module", "WARN_OP", "Warning message")
        log_event(logging.ERROR, "module", "ERROR_OP", "Error message")
        log_event(logging.CRITICAL, "module", "CRIT_OP", "Critical message")

        log_output = self.log_stream.getvalue()
        self.assertIn("DEBUG", log_output)
        self.assertIn("INFO", log_output)
        self.assertIn("WARNING", log_output)
        self.assertIn("ERROR", log_output)
        self.assertIn("CRITICAL", log_output)


class TestWeek10ComplianceAndPrivacy(unittest.TestCase):
    """Part C: Compliance and privacy boundary verification tests."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db_path = ":memory:"

    def setUp(self):
        self.client.cookies.clear()
        self.mock_provider = auth_module.MockEmailProvider()
        auth_module.set_email_provider(self.mock_provider)

    def tearDown(self):
        self.mock_provider.clear()
        self.client.cookies.clear()

    def test_17_official_portal_never_targeted_by_playwright(self):
        """
        Compliance Invariant: The official Shrine Board portal (maavaishnodevi.org)
        must NEVER be automated, scraped, or targeted with Playwright page.goto.
        Only local mock portal HTML (file:///) is permitted for automation.
        """
        rpa_source = inspect.getsource(rpa_agent)

        # Inspect all page.goto calls in rpa_agent
        lines = rpa_source.splitlines()
        for idx, line in enumerate(lines, 1):
            if "page.goto(" in line:
                # The destination must be html_url, target_url (derived from html_url), or local file:///
                self.assertNotIn("maavaishnodevi.org", line, f"Line {idx} violates boundary: {line}")
                self.assertTrue(
                    "html_url" in line or "target_url" in line or "file:///" in line,
                    f"Automated navigation line {idx} must target local mock: {line}"
                )

        # Ensure target_url is strictly constructed from html_url (local mock portal)
        self.assertIn('target_url = f"{html_url}', rpa_source)
        self.assertIn('target_url = html_url', rpa_source)

        # Also assert the official domain is not defined as an automation target
        self.assertNotIn('page.goto("https://maavaishnodevi.org', rpa_source)
        self.assertNotIn('page.goto("http://maavaishnodevi.org', rpa_source)

    def test_18_local_mock_portal_availability_continues_working(self):
        """Verify that the local mock portal availability checking continues working cleanly."""
        res = rpa_agent.check_yatra_slot_availability(
            requested_date="2026-10-20",
            headless=True,
            enable_retry=False,
            take_screenshot=False
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(res["total_slots"], 0)
        self.assertFalse(res["is_empty"])
        self.assertIsInstance(res["slots"], list)

    def test_19_guest_access_continues_without_mandatory_authentication(self):
        """Verify that guest users can query the API without authentication tokens."""
        # Tourism query
        resp1 = self.client.post("/api/yatra/", json={"message": "What is the best time to visit Vaishno Devi?"})
        self.assertEqual(resp1.status_code, 200)

        # Permitted mock availability check as guest
        resp2 = self.client.post("/api/yatra/rpa/availability", json={"date": "2026-10-20"})
        self.assertEqual(resp2.status_code, 200)
        data = resp2.json()
        self.assertEqual(data.get("status"), "SUCCESS")

    def test_20_authenticated_user_data_remains_isolated(self):
        """Verify cross-user data isolation: User 1 saved items cannot be seen or retrieved by User 2."""
        u1_email = f"user1_{uuid.uuid4().hex[:8]}@example.com"
        self.client.post("/api/auth/request-otp", json={"email": u1_email})
        u1_otp = self.mock_provider.get_latest_otp_for(u1_email)
        u1_token = self.client.post("/api/auth/verify-otp", json={"email": u1_email, "otp_code": u1_otp}).json()["session_token"]

        # Save private conversation for User 1
        save_res = self.client.post(
            "/api/auth/save-conversation",
            json={"title": "User 1 Secret Yatra Plan", "messages": [{"role": "user", "content": "secret"}]},
            headers={"Authorization": f"Bearer {u1_token}"}
        )
        self.assertEqual(save_res.status_code, 200)

        # Register User 2
        u2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
        self.client.post("/api/auth/request-otp", json={"email": u2_email})
        u2_otp = self.mock_provider.get_latest_otp_for(u2_email)
        u2_token = self.client.post("/api/auth/verify-otp", json={"email": u2_email, "otp_code": u2_otp}).json()["session_token"]

        # User 1 should retrieve 1 conversation
        u1_convs = self.client.get("/api/auth/saved-conversations", headers={"Authorization": f"Bearer {u1_token}"}).json()["conversations"]
        self.assertEqual(len(u1_convs), 1)
        self.assertEqual(u1_convs[0]["title"], "User 1 Secret Yatra Plan")

        # User 2 must see 0 conversations (complete isolation)
        u2_convs = self.client.get("/api/auth/saved-conversations", headers={"Authorization": f"Bearer {u2_token}"}).json()["conversations"]
        self.assertEqual(len(u2_convs), 0)

    def test_21_otp_values_never_logged_or_exposed(self):
        """Verify that OTP values are never stored in plaintext and never leaked in logs."""
        test_email = f"compliance.test.{uuid.uuid4().hex[:6]}@example.com"

        # Capture logs during OTP request
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(SanitizingFormatter("%(message)s"))
        root = logging.getLogger()
        root.addHandler(handler)

        try:
            req_res = self.client.post("/api/auth/request-otp", json={"email": test_email})
            self.assertEqual(req_res.status_code, 200)

            # Retrieve actual OTP sent
            actual_otp = self.mock_provider.get_latest_otp_for(test_email)
            self.assertIsNotNone(actual_otp)

            # Check database: OTP must NOT be stored in plaintext
            with sqlite3.connect(auth_module.DEFAULT_AUTH_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT otp_hash FROM otp_challenges WHERE email = ?", (auth_module.normalize_email(test_email),))
                rows = cursor.fetchall()
                self.assertGreater(len(rows), 0)
                stored_hash = rows[0][0]
                self.assertNotEqual(stored_hash, actual_otp)
                self.assertEqual(len(stored_hash), 64)  # SHA-256 HMAC hex digest

            # Check logs: actual_otp must NOT appear anywhere in captured logs
            captured_logs = log_stream.getvalue()
            self.assertNotIn(actual_otp, captured_logs)
            self.assertNotIn(test_email, captured_logs)  # email must also be masked
        finally:
            root.removeHandler(handler)

    def test_22_logout_and_session_revocation_continue_to_work(self):
        """Verify that session revocation on logout invalidates the token."""
        test_email = f"logout.test.{uuid.uuid4().hex[:6]}@example.com"
        self.client.post("/api/auth/request-otp", json={"email": test_email})
        otp = self.mock_provider.get_latest_otp_for(test_email)
        res = self.client.post("/api/auth/verify-otp", json={"email": test_email, "otp_code": otp}).json()
        token = res["session_token"]

        # Session should be active
        me_resp = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_resp.status_code, 200)
        self.assertTrue(me_resp.json().get("authenticated"))

        # Perform logout
        logout_res = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # /me should now report guest mode
        me_after_logout = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertFalse(me_after_logout.get("authenticated"))
        self.assertEqual(me_after_logout.get("status"), "guest")

        # Protected saved-itineraries endpoint must fail with 401 Unauthorized
        revoked_resp = self.client.get("/api/auth/saved-itineraries", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(revoked_resp.status_code, 401)

    def test_23_existing_human_authorization_safeguards_remain_active(self):
        """Verify that RPA workflow initiation is strictly blocked when human authorization has not been granted."""
        # Create session with plan revision 2 but authorization NOT granted
        test_sid = f"test_auth_guard_{uuid.uuid4().hex[:8]}"
        session_store.create_session(
            session_id=test_sid,
            initial_state={
                "plan_version": 2,
                "authorization": {"granted": False},
                "authorized_plan_version": 0,
            }
        )

        resp = self.client.post(
            "/api/yatra/rpa/workflow/start",
            json={
                "session_id": test_sid,
                "plan_version": 2,
                "human_authorized": False,
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "authorization_required")
        self.assertIn("Server-side human authorization has not been granted", data.get("message", ""))


if __name__ == "__main__":
    unittest.main()
