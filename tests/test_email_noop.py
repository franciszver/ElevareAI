"""
Email delivery is disabled for this demo app (AWS/SES access removed).
These tests verify send_nudge_email is a log-only no-op: it succeeds with
AWS credentials absent, makes no network call, and logs that delivery is
disabled instead of the message body.
"""

import os

import pytest

from src.services.nudges.email_service import send_nudge_email


def test_send_nudge_email_succeeds_without_aws_env(monkeypatch, caplog):
    # Ensure no AWS/SES env vars are present.
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "SES_FROM_EMAIL",
        "SES_REGION",
    ):
        monkeypatch.delenv(var, raising=False)

    with caplog.at_level("INFO"):
        result = send_nudge_email(
            to_email="student@example.com",
            message="Time to keep your streak going!",
            nudge_id="nudge-123",
        )

    assert result is True

    log_text = caplog.text
    assert "disabled" in log_text.lower()
    assert "student@example.com" in log_text
    assert "Your Study Companion - Quick Update" in log_text
    # Body content itself must not be logged, only its length.
    assert "Time to keep your streak going!" not in log_text
