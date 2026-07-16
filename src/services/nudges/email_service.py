"""
Email Service
Email delivery is disabled for this demo app (AWS/SES access removed).
Sending is a log-only no-op that preserves the original function signature
and return shape.
"""

import logging

logger = logging.getLogger(__name__)


def send_nudge_email(to_email: str, message: str, nudge_id: str) -> bool:
    """
    Log-only no-op replacement for the previous AWS SES send.

    Returns:
        bool: True (success-shaped, matching the previous "sent successfully" contract)
    """
    subject = "Your Study Companion - Quick Update"
    logger.info(
        "Email delivery disabled (log-only no-op): recipient=%s subject=%r body_length=%d nudge_id=%s",
        to_email,
        subject,
        len(message),
        nudge_id,
    )
    return True
