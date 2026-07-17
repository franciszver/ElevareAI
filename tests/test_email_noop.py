"""
Email delivery is disabled for this demo app (AWS/SES access removed).
These tests verify EmailService.send_email is a log-only no-op: it succeeds
with AWS credentials absent, makes no network call, and logs that delivery
is disabled instead of the message body.
"""

import pytest

from src.services.notifications.email import EmailService


def test_send_email_succeeds_without_aws_env(db_session, monkeypatch, caplog):
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

    service = EmailService(db_session)

    with caplog.at_level("INFO"):
        result = service.send_email(
            to_email="student@example.com",
            subject="Your Study Companion - Quick Update",
            body_text="Time to keep your streak going!",
        )

    assert result["success"] is True

    log_text = caplog.text
    assert "disabled" in log_text.lower()
    assert "student@example.com" in log_text
    assert "Your Study Companion - Quick Update" in log_text
    # Body content itself must not be logged, only its length.
    assert "Time to keep your streak going!" not in log_text
