"""
Practice Models
"""

import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin


class PracticeBankItem(Base, TimestampMixin):
    __tablename__ = "practice_bank_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    explanation = Column(Text)

    subject_id = Column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True
    )
    difficulty_level = Column(Integer, nullable=False, index=True)
    goal_tags = Column(ARRAY(String))
    topic_tags = Column(ARRAY(String))

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True, index=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "difficulty_level >= 1 AND difficulty_level <= 10",
            name="check_difficulty_range",
        ),
    )

    # Relationships
    subject = relationship("Subject", backref="practice_bank_items")
    creator = relationship("User", backref="created_practice_items")

    def __repr__(self):
        return f"<PracticeBankItem(id={self.id}, difficulty={self.difficulty_level}, active={self.is_active})>"


class PracticeAssignment(Base):
    __tablename__ = "practice_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source = Column(String(20), nullable=False, index=True)  # bank, ai_generated
    bank_item_id = Column(
        UUID(as_uuid=True), ForeignKey("practice_bank_items.id"), nullable=True
    )

    # AI-generated items
    ai_question_text = Column(Text)
    ai_answer_text = Column(Text)
    ai_explanation = Column(Text)
    flagged = Column(Boolean, default=False, index=True)

    # Assignment metadata
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    difficulty_level = Column(Integer)
    goal_tags = Column(ARRAY(String))

    # Student performance
    student_rating_before = Column(Integer)
    student_rating_after = Column(Integer)
    performance_score = Column(Numeric(3, 2))
    completed = Column(Boolean, default=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Override tracking
    overridden = Column(Boolean, default=False)
    override_id = Column(UUID(as_uuid=True), nullable=True)

    assigned_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    student = relationship("User", backref="practice_assignments")
    bank_item = relationship("PracticeBankItem", backref="assignments")
    subject = relationship("Subject", backref="practice_assignments")

    def __repr__(self):
        return f"<PracticeAssignment(id={self.id}, source={self.source}, completed={self.completed})>"


class StudentRating(Base):
    __tablename__ = "student_ratings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = Column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True
    )

    rating = Column(Integer, default=1000, index=True)  # Elo rating
    last_updated = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    student = relationship("User", backref="ratings")
    subject = relationship("Subject", backref="student_ratings")

    __table_args__ = ({"extend_existing": True},)

    def __repr__(self):
        return f"<StudentRating(student_id={self.student_id}, subject_id={self.subject_id}, rating={self.rating})>"
