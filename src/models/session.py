"""
Session Model
"""

import uuid

from sqlalchemy import (
    ARRAY,
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


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    session_date = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    duration_minutes = Column(Integer)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)

    # Transcript
    transcript_text = Column(Text)
    transcript_storage_url = Column(String(500))
    transcript_available = Column(Boolean, default=True)

    # Metadata
    topics_covered = Column(ARRAY(String))
    notes = Column(Text)

    # Relationships
    student = relationship(
        "User", foreign_keys=[student_id], backref="sessions_as_student"
    )
    tutor = relationship("User", foreign_keys=[tutor_id], backref="sessions_as_tutor")
    subject = relationship("Subject", backref="sessions")

    def __repr__(self):
        return f"<Session(id={self.id}, student_id={self.student_id}, tutor_id={self.tutor_id}, date={self.session_date})>"
