"""
Integration Models
Models for external integrations (LMS, Calendar, Webhooks)
"""

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin


class Integration(Base, TimestampMixin):
    """Integration configuration for external services"""

    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    integration_type = Column(
        String(50), nullable=False, index=True
    )  # lms, calendar, webhook
    provider = Column(
        String(50), nullable=False
    )  # canvas, blackboard, google_calendar, outlook, custom
    status = Column(String(20), default="active", index=True)  # active, inactive, error

    # Configuration stored as JSON
    config = Column(JSON, nullable=False)  # API keys, tokens, endpoints, etc.

    # Metadata
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)

    # Relationships
    user = relationship("User", backref="integrations")

    def __repr__(self):
        return f"<Integration(id={self.id}, type={self.integration_type}, provider={self.provider}, status={self.status})>"


class Webhook(Base, TimestampMixin):
    """Webhook configuration for external systems"""

    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Webhook details
    url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=True)  # For signature verification
    events = Column(JSON, nullable=False)  # List of events to subscribe to

    # Status
    status = Column(String(20), default="active", index=True)  # active, inactive, error
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)

    # Relationships
    user = relationship("User", backref="webhooks")
    webhook_events = relationship(
        "WebhookEvent", back_populates="webhook", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Webhook(id={self.id}, url={self.url[:50]}, status={self.status})>"


class WebhookEvent(Base):
    """Webhook event log"""

    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type = Column(String(50), nullable=False, index=True)
    payload = Column(JSON, nullable=False)

    # Delivery status
    status = Column(
        String(20), nullable=False, index=True
    )  # pending, sent, failed, retrying
    http_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)

    attempts = Column(Integer, default=0)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    webhook = relationship("Webhook", back_populates="webhook_events")

    def __repr__(self):
        return f"<WebhookEvent(id={self.id}, event_type={self.event_type}, status={self.status})>"
