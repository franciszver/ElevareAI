"""
Tutor-Student Assignment Model
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base


class TutorStudentAssignment(Base):
    __tablename__ = "tutor_student_assignments"

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
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)

    assigned_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status = Column(
        String(20), default="active", index=True
    )  # active, paused, completed

    notes = Column(Text)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    __table_args__ = (PrimaryKeyConstraint("tutor_id", "student_id", "subject_id"),)

    # Relationships
    tutor = relationship("User", foreign_keys=[tutor_id], backref="tutor_assignments")
    student = relationship(
        "User", foreign_keys=[student_id], backref="student_assignments"
    )
    subject = relationship("Subject", backref="tutor_student_assignments")

    def __repr__(self):
        return f"<TutorStudentAssignment(tutor_id={self.tutor_id}, student_id={self.student_id}, status={self.status})>"
