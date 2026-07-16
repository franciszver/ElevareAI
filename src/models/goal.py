"""
Goal Model
"""

import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    goal_type = Column(String(50))  # SAT, AP, General
    title = Column(String(255), nullable=False)
    description = Column(Text)

    target_completion_date = Column(Date)
    status = Column(
        String(20), default="active", index=True
    )  # active, completed, paused, cancelled

    # Progress tracking
    completion_percentage = Column(Numeric(5, 2), default=0.00)
    current_streak = Column(Integer, default=0)
    xp_earned = Column(Integer, default=0)

    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], backref="goals")
    creator = relationship("User", foreign_keys=[created_by])
    subject = relationship("Subject", backref="goals")

    def __repr__(self):
        return f"<Goal(id={self.id}, title={self.title}, status={self.status}, completion={self.completion_percentage}%)>"
