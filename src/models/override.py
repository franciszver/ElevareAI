"""
Override Model
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base


class Override(Base):
    __tablename__ = "overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tutor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    override_type = Column(
        String(50), nullable=False, index=True
    )  # summary, practice, qa_answer
    action = Column(Text, nullable=False)

    # References to overridden content
    summary_id = Column(UUID(as_uuid=True), ForeignKey("summaries.id"), nullable=True)
    practice_assignment_id = Column(
        UUID(as_uuid=True), ForeignKey("practice_assignments.id"), nullable=True
    )
    qa_interaction_id = Column(
        UUID(as_uuid=True), ForeignKey("qa_interactions.id"), nullable=True
    )

    # Override details
    original_content = Column(JSONB)
    new_content = Column(JSONB)
    reason = Column(Text)

    # Analytics
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    difficulty_level = Column(Integer)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    tutor = relationship("User", foreign_keys=[tutor_id], backref="overrides_as_tutor")
    student = relationship(
        "User", foreign_keys=[student_id], backref="overrides_as_student"
    )
    summary = relationship("Summary", backref="overrides")
    practice_assignment = relationship("PracticeAssignment", backref="overrides")
    qa_interaction = relationship("QAInteraction", backref="overrides")
    subject = relationship("Subject", backref="overrides")

    def __repr__(self):
        return f"<Override(id={self.id}, type={self.override_type}, tutor_id={self.tutor_id})>"
