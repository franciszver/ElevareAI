"""
Summary Model
"""

import uuid

from sqlalchemy import ARRAY, Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


class Summary(Base, TimestampMixin):
    __tablename__ = "summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tutor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    narrative = Column(Text, nullable=False)
    next_steps = Column(ARRAY(String), nullable=False)

    subjects_covered = Column(ARRAY(String))
    summary_type = Column(String(50))  # normal, brief, missing_transcript

    overridden = Column(Boolean, default=False)
    override_id = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    session = relationship("Session", backref="summaries")
    student = relationship(
        "User", foreign_keys=[student_id], backref="summaries_as_student"
    )
    tutor = relationship("User", foreign_keys=[tutor_id], backref="summaries_as_tutor")

    def __repr__(self):
        return f"<Summary(id={self.id}, session_id={self.session_id}, type={self.summary_type})>"
