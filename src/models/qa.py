"""
Q&A Interaction Model
"""

import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base


class QAInteraction(Base):
    __tablename__ = "qa_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    confidence = Column(String(10), nullable=False, index=True)  # High, Medium, Low
    confidence_score = Column(Numeric(3, 2))  # 0.00 to 1.00

    # Context
    context_subjects = Column(ARRAY(String))
    clarification_requested = Column(Boolean, default=False)
    out_of_scope = Column(Boolean, default=False)

    # Escalation
    tutor_escalation_suggested = Column(Boolean, default=False)
    escalated_to_tutor_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    disclaimer_shown = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    student = relationship("User", foreign_keys=[student_id], backref="qa_interactions")
    escalated_tutor = relationship("User", foreign_keys=[escalated_to_tutor_id])
    goal = relationship("Goal", foreign_keys=[goal_id], backref="qa_interactions")

    def __repr__(self):
        return f"<QAInteraction(id={self.id}, confidence={self.confidence}, escalation={self.tutor_escalation_suggested})>"
