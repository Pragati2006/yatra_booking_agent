"""
utils/logger.py
Week 10: Structured & Sanitized Logging Framework.

Provides centralized, context-aware, structured logging across all system components:
- Standard log fields: timestamp, level, component, operation, correlation_id, error_category, message, details.
- Automatic data masking on all log records via SanitizingFormatter.
- Correlation ID propagation via contextvars.
- Granular error categories and transparent operational event tracking.
"""

import os
import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from utils.masking import sanitize_log_message, mask_sensitive_data

# Context variable for request / correlation tracking
_current_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Returns the current request correlation ID, or a default fallback."""
    cid = _current_correlation_id.get()
    if not cid:
        return "sys-init"
    return cid


def set_correlation_id(cid: Optional[str]) -> str:
    """Sets the current request correlation ID and returns it."""
    if not cid:
        cid = f"req-{uuid.uuid4().hex[:8]}"
    _current_correlation_id.set(cid)
    return cid


class SanitizingFormatter(logging.Formatter):
    """
    Logging Formatter that intercepts and sanitizes sensitive data (emails, OTPs,
    auth tokens, API keys, credentials) before outputting to streams or files.
    """

    def format(self, record: logging.LogRecord) -> str:
        # 1. Format the original message using standard formatter
        original_msg = super().format(record)
        # 2. Scrub sensitive credentials, keys, OTPs, and emails
        return sanitize_log_message(original_msg)


class StructuredEventLogger:
    """
    Standardized event logging helper emitting consistent operational milestones
    with mandatory component, operation, correlation ID, and error category tracking.
    """

    def __init__(self, logger: logging.Logger, component_name: str):
        self.logger = logger
        self.component_name = component_name

    def log(
        self,
        level: int,
        operation: str,
        message: str,
        correlation_id: Optional[str] = None,
        error_category: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retry_attempt: Optional[int] = None,
        workflow_state: Optional[str] = None,
        human_intervention_required: bool = False,
        final_outcome: Optional[str] = None,
        exc: Optional[Exception] = None,
    ):
        cid = correlation_id or get_correlation_id()
        sanitized_details = mask_sensitive_data(details) if details else {}

        event_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.component_name,
            "operation": operation,
            "correlation_id": cid,
            "message": sanitize_log_message(message),
            "human_intervention_required": human_intervention_required,
        }

        if error_category:
            event_payload["error_category"] = error_category
        if retry_attempt is not None:
            event_payload["retry_attempt"] = retry_attempt
        if workflow_state:
            event_payload["workflow_state"] = workflow_state
        if final_outcome:
            event_payload["final_outcome"] = final_outcome
        if sanitized_details:
            event_payload["details"] = sanitized_details
        if exc:
            event_payload["exception_type"] = type(exc).__name__
            event_payload["exception_message"] = sanitize_log_message(str(exc))

        # Format as structured single-line log for machine observability
        details_str = f" | details={json.dumps(sanitized_details)}" if sanitized_details else ""
        err_str = f" | error_category={error_category}" if error_category else ""
        retry_str = f" | retry={retry_attempt}" if retry_attempt is not None else ""
        state_str = f" | state={workflow_state}" if workflow_state else ""
        hitl_str = " | HITL=True" if human_intervention_required else ""
        outcome_str = f" | outcome={final_outcome}" if final_outcome else ""

        formatted_line = (
            f"[{self.component_name}] [{operation}] [cid:{cid}] "
            f"{sanitize_log_message(message)}"
            f"{err_str}{retry_str}{state_str}{hitl_str}{outcome_str}{details_str}"
        )

        self.logger.log(level, formatted_line, extra={"event_payload": event_payload})


def get_structured_logger(component_name: str) -> StructuredEventLogger:
    """Returns a StructuredEventLogger instance bound to the specified component."""
    base_logger = logging.getLogger(component_name)
    return StructuredEventLogger(base_logger, component_name)


def log_event(
    level_or_logger: Union[int, logging.Logger, StructuredEventLogger],
    component_or_level: Union[int, str, logging.Logger] = logging.INFO,
    operation: str = "OPERATION",
    message: str = "",
    correlation_id: Optional[str] = None,
    error_category: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    retry_attempt: Optional[int] = None,
    workflow_state: Optional[str] = None,
    human_intervention_required: bool = False,
    final_outcome: Optional[str] = None,
    exc: Optional[Exception] = None,
):
    """
    Functional convenience wrapper for emitting structured log events.
    Supports both signatures:
      log_event(level, component, operation, message, ...)
      log_event(logger, level, operation, message, ...)
    """
    if isinstance(level_or_logger, int):
        level = level_or_logger
        comp = str(component_or_level) if isinstance(component_or_level, str) else "system"
        target_logger = logging.getLogger(comp)
        StructuredEventLogger(target_logger, comp).log(
            level=level,
            operation=operation,
            message=message,
            correlation_id=correlation_id,
            error_category=error_category,
            details=details,
            retry_attempt=retry_attempt,
            workflow_state=workflow_state,
            human_intervention_required=human_intervention_required,
            final_outcome=final_outcome,
            exc=exc,
        )
    elif isinstance(level_or_logger, StructuredEventLogger):
        level = int(component_or_level) if isinstance(component_or_level, int) else logging.INFO
        level_or_logger.log(
            level=level,
            operation=operation,
            message=message,
            correlation_id=correlation_id,
            error_category=error_category,
            details=details,
            retry_attempt=retry_attempt,
            workflow_state=workflow_state,
            human_intervention_required=human_intervention_required,
            final_outcome=final_outcome,
            exc=exc,
        )
    else:
        # Standard logging.Logger instance
        base_logger = level_or_logger
        level = int(component_or_level) if isinstance(component_or_level, int) else logging.INFO
        comp = getattr(base_logger, "name", "system")
        StructuredEventLogger(base_logger, comp).log(
            level=level,
            operation=operation,
            message=message,
            correlation_id=correlation_id,
            error_category=error_category,
            details=details,
            retry_attempt=retry_attempt,
            workflow_state=workflow_state,
            human_intervention_required=human_intervention_required,
            final_outcome=final_outcome,
            exc=exc,
        )
