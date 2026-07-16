"""
Nudge Model
"""

import uuid

from sqlalchemy import ARRAY, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base


class Nudge(Base):
    __tablename__ = "nudges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type = Column(
        String(50), nullable=False, index=True
    )  # login, inactivity, cross_subject
    channel = Column(String(20), nullable=False)  # in_app, email, both

    message = Column(Text, nullable=False)
    personalized = Column(Boolean, default=True)

    # Engagement tracking
    sent_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    opened_at = Column(DateTime(timezone=True), nullable=True, index=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    trigger_reason = Column(Text)
    suggestions_made = Column(ARRAY(String))

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", backref="nudges")

    def __repr__(self):
        return f"<Nudge(id={self.id}, type={self.type}, channel={self.channel}, sent_at={self.sent_at})>"
