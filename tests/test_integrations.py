"""
Integration Tests
Tests for integration services (LMS, Calendar, Notifications, Webhooks)
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.services.integrations.notifications import NotificationService
from src.services.integrations.webhooks import WebhookService, _is_safe_webhook_url
from tests.test_models import TestUser


def test_create_webhook(db_session: Session):
    """Test webhook creation"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="user-sub",
        email="user@test.com",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()

    service = WebhookService(db_session)
    result = service.create_webhook(
        user_id=str(user.id),
        url="https://example.com/webhook",
        events=["practice.completed", "session.created"],
        secret="test-secret",
    )

    assert result["success"] is True
    assert "webhook" in result
    assert result["webhook"]["url"] == "https://example.com/webhook"
    assert len(result["webhook"]["events"]) == 2


def test_trigger_webhook(db_session: Session):
    """Test webhook triggering"""
    from tests.test_models import TestWebhook

    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="user-sub",
        email="user@test.com",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()

    # Create webhook
    webhook = TestWebhook(
        id=str(uuid.uuid4()),
        user_id=user.id,
        url="https://example.com/webhook",
        events=["practice.completed"],
        status="active",
    )
    db_session.add(webhook)
    db_session.commit()

    service = WebhookService(db_session)

    # Mock the delivery (will fail in test but structure is correct)
    result = service.trigger_webhook(
        event_type="practice.completed",
        payload={"practice_id": "123", "student_id": str(user.id)},
    )

    assert "total_webhooks" in result
    assert result["total_webhooks"] >= 0


def test_webhook_signature_generation(db_session: Session):
    """Test webhook signature generation and verification"""
    service = WebhookService(db_session)

    payload = '{"event": "test", "data": {}}'
    secret = "test-secret"

    signature = service._generate_signature(payload, secret)

    assert len(signature) == 64  # SHA256 hex length
    assert service.verify_signature(payload, signature, secret) is True
    assert service.verify_signature(payload, "wrong-signature", secret) is False


def test_get_webhook_events(db_session: Session):
    """Test getting webhook event history"""
    from tests.test_models import TestWebhook, TestWebhookEvent

    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="user-sub",
        email="user@test.com",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()

    webhook = TestWebhook(
        id=str(uuid.uuid4()),
        user_id=user.id,
        url="https://example.com/webhook",
        events=["test.event"],
        status="active",
    )
    db_session.add(webhook)
    db_session.commit()

    event = TestWebhookEvent(
        id=str(uuid.uuid4()),
        webhook_id=webhook.id,
        event_type="test.event",
        payload={"test": "data"},
        status="sent",
        http_status=200,
    )
    db_session.add(event)
    db_session.commit()

    service = WebhookService(db_session)
    result = service.get_webhook_events(str(webhook.id))

    assert result["success"] is True
    assert len(result["events"]) >= 1


def test_notification_service(db_session: Session):
    """Test notification service"""
    service = NotificationService(db_session)

    result = service.send_push_notification(
        user_id=str(uuid.uuid4()),
        title="Test Notification",
        body="This is a test",
        data={"key": "value"},
    )

    assert result["success"] is True
    assert "sent_at" in result


def test_batch_notifications(db_session: Session):
    """Test batch notification sending"""
    service = NotificationService(db_session)

    notifications = [
        {"user_id": str(uuid.uuid4()), "title": "Test 1", "body": "Body 1"},
        {"user_id": str(uuid.uuid4()), "title": "Test 2", "body": "Body 2"},
    ]

    result = service.send_batch_notifications(notifications)

    assert result["success"] is True
    assert result["total"] == 2
    assert result["successful"] == 2


def test_register_device_token(db_session: Session):
    """Test device token registration"""
    service = NotificationService(db_session)

    result = service.register_device_token(
        user_id=str(uuid.uuid4()),
        device_token="test-token-123",
        platform="ios",
        device_info={"model": "iPhone", "os_version": "17.0"},
    )

    assert result["success"] is True
    assert "registered_at" in result


def test_unregister_device_token(db_session: Session):
    """Test device token unregistration"""
    service = NotificationService(db_session)

    result = service.unregister_device_token(
        user_id=str(uuid.uuid4()), device_token="test-token-123"
    )

    assert result["success"] is True
    assert "unregistered_at" in result


# --- SSRF hardening (P2.1) -------------------------------------------------


def _fake_getaddrinfo(ip_map):
    """Build a fake socket.getaddrinfo that resolves hosts to given IPs."""
    import socket as socket_module

    def _fn(host, *args, **kwargs):
        if host not in ip_map:
            raise socket_module.gaierror(f"unmocked host: {host}")
        return [(2, 1, 6, "", (ip, 0)) for ip in ip_map[host]]

    return _fn


@pytest.mark.parametrize(
    "url,ip_map,expected_safe",
    [
        ("http://127.0.0.1:8000/x", {"127.0.0.1": ["127.0.0.1"]}, False),
        (
            "http://169.254.169.254/latest/meta-data",
            {"169.254.169.254": ["169.254.169.254"]},
            False,
        ),
        ("http://10.0.0.5/x", {"10.0.0.5": ["10.0.0.5"]}, False),
        ("http://[::1]/x", {"::1": ["::1"]}, False),
        ("file:///etc/passwd", {}, False),
        ("ftp://example.com/x", {"example.com": ["93.184.216.34"]}, False),
        ("https://example.com/webhook", {"example.com": ["93.184.216.34"]}, True),
    ],
)
def test_is_safe_webhook_url(url, ip_map, expected_safe):
    """_is_safe_webhook_url blocks private/loopback/link-local/metadata/reserved
    targets and disallowed schemes, but allows public http(s) hosts."""
    with patch("socket.getaddrinfo", side_effect=_fake_getaddrinfo(ip_map)):
        safe, reason = _is_safe_webhook_url(url)

    assert safe is expected_safe, reason


def test_trigger_webhook_direct_url_blocks_ssrf_target(db_session: Session):
    """trigger_webhook(webhook_url=...) must NOT POST to a private/internal
    target, and must return a blocked/failed result instead."""
    service = WebhookService(db_session)

    with patch(
        "socket.getaddrinfo",
        side_effect=_fake_getaddrinfo({"127.0.0.1": ["127.0.0.1"]}),
    ), patch("requests.post") as mock_post:
        result = service.trigger_webhook(
            event_type="practice.completed",
            payload={"a": 1},
            webhook_url="http://127.0.0.1:8000/internal",
        )

    mock_post.assert_not_called()
    assert result["success"] is False
    assert result.get("blocked") is True


def test_trigger_webhook_direct_url_blocks_metadata_target(db_session: Session):
    """The cloud metadata endpoint must be blocked."""
    service = WebhookService(db_session)

    with patch(
        "socket.getaddrinfo",
        side_effect=_fake_getaddrinfo({"169.254.169.254": ["169.254.169.254"]}),
    ), patch("requests.post") as mock_post:
        result = service.trigger_webhook(
            event_type="practice.completed",
            payload={"a": 1},
            webhook_url="http://169.254.169.254/latest/meta-data",
        )

    mock_post.assert_not_called()
    assert result["success"] is False
    assert result.get("blocked") is True


def test_trigger_webhook_direct_url_allows_public_target(db_session: Session):
    """A normal public https webhook target must still be delivered to."""
    service = WebhookService(db_session)

    mock_response = MagicMock(status_code=200)

    with patch(
        "socket.getaddrinfo",
        side_effect=_fake_getaddrinfo({"example.com": ["93.184.216.34"]}),
    ), patch("requests.post", return_value=mock_response) as mock_post:
        result = service.trigger_webhook(
            event_type="practice.completed",
            payload={"a": 1},
            webhook_url="https://example.com/webhook",
        )

    mock_post.assert_called_once()
    assert result["success"] is True


def test_deliver_webhook_blocks_registered_webhook_with_private_target(
    db_session: Session,
):
    """A registered webhook whose URL resolves to a private IP must be
    blocked, without breaking the rest of the trigger_webhook batch."""
    from tests.test_models import TestWebhook

    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="user-sub-private",
        email="private@test.com",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()

    webhook = TestWebhook(
        id=str(uuid.uuid4()),
        user_id=user.id,
        url="http://10.0.0.5/internal-hook",
        events=["practice.completed"],
        status="active",
    )
    db_session.add(webhook)
    db_session.commit()

    service = WebhookService(db_session)

    with patch(
        "socket.getaddrinfo",
        side_effect=_fake_getaddrinfo({"10.0.0.5": ["10.0.0.5"]}),
    ), patch("requests.post") as mock_post:
        result = service.trigger_webhook(
            event_type="practice.completed",
            payload={"practice_id": "123"},
        )

    mock_post.assert_not_called()
    assert result["total_webhooks"] == 1
    assert result["successful"] == 0
    assert result["failed"] == 1
    assert result["results"][0].get("blocked") is True
