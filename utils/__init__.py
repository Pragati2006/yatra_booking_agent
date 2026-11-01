"""
utils package
Week 10: Ethical Boundary, Compliance, Data Masking, and Structured Logging.
"""

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
    get_structured_logger,
    log_event,
    set_correlation_id,
    get_correlation_id,
)

__all__ = [
    "mask_email",
    "mask_otp",
    "mask_token",
    "mask_api_key",
    "mask_phone",
    "mask_name",
    "mask_sensitive_data",
    "sanitize_log_message",
    "get_structured_logger",
    "log_event",
    "set_correlation_id",
    "get_correlation_id",
]
