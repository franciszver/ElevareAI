"""
Webhook Service
Webhook delivery and management
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from sqlalchemy.orm import Session

# Import models - will use test models if available
try:
    from tests.test_models import TestWebhook, TestWebhookEvent

    USE_TEST_MODELS = True
except ImportError:
    USE_TEST_MODELS = False
    from src.models.integration import Webhook, WebhookEvent

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for webhook management and delivery"""

    def __init__(self, db: Session):
        self.db = db

    def create_webhook(
        self,
        user_id: Optional[str],
        url: str,
        events: List[str],
        secret: Optional[str] = None,
    ) -> Dict:
        """
        Create a new webhook

        Args:
            user_id: Optional user ID (None for system webhooks)
            user_id: User ID
            url: Webhook URL
            events: List of events to subscribe to
            secret: Optional secret for signature verification

        Returns:
            Created webhook
        """
        if USE_TEST_MODELS:
            WebhookModel = TestWebhook
        else:
            WebhookModel = Webhook

        # Handle user_id - keep as string for test models, convert to UUID for production
        if USE_TEST_MODELS:
            user_uuid = user_id  # Test models use strings
        else:
            try:
                from uuid import UUID as UUIDType

                user_uuid = (
                    UUIDType(user_id)
                    if user_id and isinstance(user_id, str)
                    else user_id
                )
            except (ValueError, TypeError):
                user_uuid = user_id

        webhook = WebhookModel(
            user_id=user_uuid, url=url, secret=secret, events=events, status="active"
        )

        self.db.add(webhook)
        self.db.commit()
        self.db.refresh(webhook)

        return {
            "success": True,
            "webhook": {
                "id": str(webhook.id),
                "url": webhook.url,
                "events": webhook.events,
                "status": webhook.status,
                "created_at": webhook.created_at.isoformat()
                if hasattr(webhook.created_at, "isoformat")
                else str(webhook.created_at),
            },
        }

    def trigger_webhook(
        self,
        event_type: str,
        payload: Dict,
        webhook_url: Optional[str] = None,
        webhook_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Trigger webhook for an event

        Args:
            event_type: Event type (e.g., "practice.completed", "session.created")
            payload: Event payload data
            webhook_url: Optional direct webhook URL - if provided, sends
                directly instead of looking up registered webhooks
            webhook_id: Optional specific webhook ID
            user_id: Optional user ID to filter webhooks

        Returns:
            Trigger results
        """
        # If a direct webhook URL is provided, send directly without
        # looking up registered webhooks
        if webhook_url:
            webhook_payload = {
                "event": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": payload,
            }

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "AI-Study-Companion-Webhook/1.0",
            }

            try:
                response = requests.post(
                    webhook_url, json=webhook_payload, headers=headers, timeout=10
                )
                return {
                    "success": response.status_code < 400,
                    "http_status": response.status_code,
                    "url": webhook_url,
                }
            except Exception as e:
                logger.error(f"Direct webhook delivery error: {str(e)}")
                return {"success": False, "error": str(e), "url": webhook_url}

        if USE_TEST_MODELS:
            WebhookModel = TestWebhook
            WebhookEventModel = TestWebhookEvent
        else:
            WebhookModel = Webhook
            WebhookEventModel = WebhookEvent

        # Find webhooks that subscribe to this event
        query = self.db.query(WebhookModel).filter(
            WebhookModel.status == "active", WebhookModel.events.contains([event_type])
        )

        if webhook_id:
            try:
                from uuid import UUID as UUIDType

                webhook_uuid = (
                    UUIDType(webhook_id) if isinstance(webhook_id, str) else webhook_id
                )
                query = query.filter(WebhookModel.id == webhook_uuid)
            except (ValueError, TypeError):
                query = query.filter(WebhookModel.id == webhook_id)

        if user_id:
            try:
                from uuid import UUID as UUIDType

                user_uuid = UUIDType(user_id) if isinstance(user_id, str) else user_id
                query = query.filter(WebhookModel.user_id == user_uuid)
            except (ValueError, TypeError):
                query = query.filter(WebhookModel.user_id == user_id)

        webhooks = query.all()

        results = []
        for webhook in webhooks:
            result = self._deliver_webhook(webhook, event_type, payload)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))

        return {
            "success": True,
            "total_webhooks": len(webhooks),
            "successful": success_count,
            "failed": len(webhooks) - success_count,
            "results": results,
        }

    def _deliver_webhook(self, webhook, event_type: str, payload: Dict) -> Dict:
        """Deliver webhook to URL"""
        if USE_TEST_MODELS:
            WebhookEventModel = TestWebhookEvent
        else:
            WebhookEventModel = WebhookEvent

        # Create webhook event record
        event = WebhookEventModel(
            webhook_id=webhook.id,
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        self.db.add(event)
        self.db.commit()

        # Prepare webhook payload
        webhook_payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }

        # Add signature if secret exists
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AI-Study-Companion-Webhook/1.0",
        }

        if webhook.secret:
            signature = self._generate_signature(
                json.dumps(webhook_payload), webhook.secret
            )
            headers["X-Webhook-Signature"] = signature

        try:
            response = requests.post(
                webhook.url, json=webhook_payload, headers=headers, timeout=10
            )

            # Update event status
            event.status = "sent" if response.status_code < 400 else "failed"
            event.http_status = response.status_code
            event.response_body = response.text[:1000]  # Limit response size
            event.sent_at = datetime.utcnow()
            event.attempts = 1

            # Update webhook stats
            webhook.last_triggered_at = datetime.utcnow()
            if response.status_code < 400:
                webhook.success_count += 1
            else:
                webhook.error_count += 1
                webhook.last_error = (
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )

            self.db.commit()

            return {
                "success": response.status_code < 400,
                "webhook_id": str(webhook.id),
                "http_status": response.status_code,
                "event_id": str(event.id),
            }

        except Exception as e:
            logger.error(f"Webhook delivery error: {str(e)}")

            # Update event status
            event.status = "failed"
            event.response_body = "Delivery failed due to internal error"
            event.attempts = 1
            event.next_retry_at = datetime.utcnow() + timedelta(minutes=5)

            # Update webhook stats
            webhook.error_count += 1
            webhook.last_error = "Internal delivery error occurred"

            self.db.commit()

            return {
                "success": False,
                "webhook_id": str(webhook.id),
                "error": "Internal webhook delivery error",
                "event_id": str(event.id),
            }

    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook"""
        return hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify webhook signature"""
        expected_signature = self._generate_signature(payload, secret)
        return hmac.compare_digest(expected_signature, signature)

    def get_webhook_events(
        self, webhook_id: str, status: Optional[str] = None, limit: int = 100
    ) -> Dict:
        """Get webhook event history"""
        if USE_TEST_MODELS:
            WebhookEventModel = TestWebhookEvent
        else:
            WebhookEventModel = WebhookEvent

        # Handle webhook_id - keep as string for test models, convert to UUID for production
        if USE_TEST_MODELS:
            webhook_uuid = webhook_id  # Test models use strings
        else:
            try:
                from uuid import UUID as UUIDType

                webhook_uuid = (
                    UUIDType(webhook_id) if isinstance(webhook_id, str) else webhook_id
                )
            except (ValueError, TypeError):
                webhook_uuid = webhook_id

        query = self.db.query(WebhookEventModel).filter(
            WebhookEventModel.webhook_id == webhook_uuid
        )

        if status:
            query = query.filter(WebhookEventModel.status == status)

        events = query.order_by(WebhookEventModel.created_at.desc()).limit(limit).all()

        return {
            "success": True,
            "events": [
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "status": e.status,
                    "http_status": e.http_status,
                    "attempts": e.attempts,
                    "created_at": e.created_at.isoformat()
                    if hasattr(e.created_at, "isoformat")
                    else str(e.created_at),
                    "sent_at": e.sent_at.isoformat()
                    if e.sent_at and hasattr(e.sent_at, "isoformat")
                    else str(e.sent_at)
                    if e.sent_at
                    else None,
                }
                for e in events
            ],
            "total": len(events),
        }

    def retry_failed_webhook(self, event_id: str) -> Dict:
        """Retry a failed webhook event"""
        if USE_TEST_MODELS:
            WebhookEventModel = TestWebhookEvent
            WebhookModel = TestWebhook
        else:
            WebhookEventModel = WebhookEvent
            WebhookModel = Webhook

        try:
            from uuid import UUID as UUIDType

            event_uuid = UUIDType(event_id) if isinstance(event_id, str) else event_id
        except (ValueError, TypeError):
            event_uuid = event_id

        event = (
            self.db.query(WebhookEventModel)
            .filter(WebhookEventModel.id == event_uuid)
            .first()
        )

        if not event:
            return {"success": False, "error": "Event not found"}

        webhook = (
            self.db.query(WebhookModel)
            .filter(WebhookModel.id == event.webhook_id)
            .first()
        )

        if not webhook:
            return {"success": False, "error": "Webhook not found"}

        # Retry delivery
        result = self._deliver_webhook(webhook, event.event_type, event.payload)

        return result
