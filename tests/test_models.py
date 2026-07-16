"""
Test-specific models for SQLite compatibility
Uses JSON instead of ARRAY for SQLite testing
"""

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


# Separate Base for test models to avoid table name conflicts
class TestBase(DeclarativeBase):
    pass


class TimestampMixin:
    """Timestamp mixin for test models"""

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Test models that use JSON instead of ARRAY for SQLite compatibility
class TestSubject(TestBase):
    """Test version of Subject model with JSON instead of ARRAY"""

    __tablename__ = "subjects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    category = Column(String(50), index=True)
    description = Column(Text)
    related_subjects = Column(JSON)  # JSON array instead of ARRAY
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TestSession(TestBase, TimestampMixin):
    """Test version of Session model with JSON instead of ARRAY"""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tutor_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_date = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    duration_minutes = Column(Integer)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True)
    transcript_text = Column(Text)
    transcript_storage_url = Column(String(500))
    transcript_available = Column(Boolean, default=True)
    topics_covered = Column(JSON)  # JSON array instead of ARRAY
    notes = Column(Text)

    student = relationship(
        "TestUser", foreign_keys=[student_id], backref="sessions_as_student"
    )
    tutor = relationship(
        "TestUser", foreign_keys=[tutor_id], backref="sessions_as_tutor"
    )
    subject = relationship("TestSubject", backref="sessions")


class TestSummary(TestBase, TimestampMixin):
    """Test version of Summary model with JSON instead of ARRAY"""

    __tablename__ = "summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tutor_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    narrative = Column(Text, nullable=False)
    next_steps = Column(JSON, nullable=False)  # JSON array instead of ARRAY
    subjects_covered = Column(JSON)  # JSON array instead of ARRAY
    summary_type = Column(String(50))
    overridden = Column(Boolean, default=False)
    override_id = Column(String(36), nullable=True)

    session = relationship("TestSession", backref="summaries")
    student = relationship(
        "TestUser", foreign_keys=[student_id], backref="summaries_as_student"
    )
    tutor = relationship(
        "TestUser", foreign_keys=[tutor_id], backref="summaries_as_tutor"
    )


class TestQAInteraction(TestBase):
    """Test version of QAInteraction model with JSON instead of ARRAY"""

    __tablename__ = "qa_interactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    confidence = Column(String(10), nullable=False, index=True)
    confidence_score = Column(Numeric(3, 2))
    context_subjects = Column(JSON)  # JSON array instead of ARRAY
    clarification_requested = Column(Boolean, default=False)
    out_of_scope = Column(Boolean, default=False)
    tutor_escalation_suggested = Column(Boolean, default=False)
    escalated_to_tutor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    disclaimer_shown = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student = relationship(
        "TestUser", foreign_keys=[student_id], backref="qa_interactions"
    )
    escalated_tutor = relationship("TestUser", foreign_keys=[escalated_to_tutor_id])


class TestPracticeBankItem(TestBase, TimestampMixin):
    """Test version of PracticeBankItem model with JSON instead of ARRAY"""

    __tablename__ = "practice_bank_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    explanation = Column(Text)
    subject_id = Column(
        String(36), ForeignKey("subjects.id"), nullable=False, index=True
    )
    difficulty_level = Column(Integer, nullable=False, index=True)
    goal_tags = Column(JSON)  # JSON array instead of ARRAY
    topic_tags = Column(JSON)  # JSON array instead of ARRAY
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True, index=True)

    subject = relationship("TestSubject", backref="practice_bank_items")
    creator = relationship("TestUser", backref="created_practice_items")


class TestUser(TestBase, TimestampMixin):
    """Test version of User model"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cognito_sub = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(20), nullable=False)
    profile = Column(JSON, default={})
    gamification = Column(JSON, default={})
    analytics = Column(JSON, default={})
    disclaimer_shown = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TestGoal(TestBase, TimestampMixin):
    """Test version of Goal model"""

    __tablename__ = "goals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    subject_id = Column(
        String(36), ForeignKey("subjects.id"), nullable=True, index=True
    )
    goal_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), nullable=False, index=True)
    completion_percentage = Column(Integer, default=0)
    target_completion_date = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    current_streak = Column(Integer, default=0)
    xp_earned = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student = relationship("TestUser", foreign_keys=[student_id], backref="goals")
    subject = relationship("TestSubject", backref="goals")


class TestStudentRating(TestBase):
    """Test version of StudentRating model"""

    __tablename__ = "student_ratings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = Column(
        String(36),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating = Column(Integer, nullable=False, default=1000)
    last_updated = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student = relationship("TestUser", backref="student_ratings")
    subject = relationship("TestSubject", backref="student_ratings")


class TestPracticeAssignment(TestBase):
    """Test version of PracticeAssignment model"""

    __tablename__ = "practice_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String(20), nullable=False, index=True)
    bank_item_id = Column(
        String(36), ForeignKey("practice_bank_items.id"), nullable=True
    )
    ai_question_text = Column(Text)
    ai_answer_text = Column(Text)
    ai_explanation = Column(Text)
    flagged = Column(Boolean, default=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True)
    difficulty_level = Column(Integer)
    goal_tags = Column(JSON)
    student_rating_before = Column(Integer)
    student_rating_after = Column(Integer)
    performance_score = Column(Numeric(3, 2))
    completed = Column(Boolean, default=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    overridden = Column(Boolean, default=False)
    override_id = Column(String(36), nullable=True)
    assigned_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student = relationship("TestUser", backref="practice_assignments")
    bank_item = relationship("TestPracticeBankItem", backref="assignments")
    subject = relationship("TestSubject", backref="practice_assignments")


class TestMessageThread(TestBase):
    """Test version of MessageThread model"""

    __tablename__ = "message_threads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tutor_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject = Column(String(200), nullable=False)
    status = Column(String(20), default="open", index=True)
    triggered_by_type = Column(String(50))
    triggered_by_id = Column(String(36), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True, index=True)
    message_count = Column(Integer, default=0)
    unread_count_tutor = Column(Integer, default=0)
    unread_count_student = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tutor = relationship(
        "TestUser", foreign_keys=[tutor_id], backref="message_threads_as_tutor"
    )
    student = relationship(
        "TestUser", foreign_keys=[student_id], backref="message_threads_as_student"
    )
    messages = relationship(
        "TestMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="TestMessage.created_at",
    )


class TestMessage(TestBase):
    """Test version of Message model"""

    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(
        String(36),
        ForeignKey("message_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")
    read_at = Column(DateTime(timezone=True), nullable=True)
    read_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    thread = relationship("TestMessageThread", back_populates="messages")
    sender = relationship("TestUser", foreign_keys=[sender_id], backref="sent_messages")
    reader = relationship("TestUser", foreign_keys=[read_by])


class TestOverride(TestBase):
    """Test version of Override model"""

    __tablename__ = "overrides"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tutor_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    override_type = Column(String(50), nullable=False, index=True)
    action = Column(Text, nullable=False)
    summary_id = Column(String(36), ForeignKey("summaries.id"), nullable=True)
    practice_assignment_id = Column(
        String(36), ForeignKey("practice_assignments.id"), nullable=True
    )
    qa_interaction_id = Column(
        String(36), ForeignKey("qa_interactions.id"), nullable=True
    )
    original_content = Column(JSON)
    new_content = Column(JSON)
    reason = Column(Text)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True)
    difficulty_level = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    tutor = relationship(
        "TestUser", foreign_keys=[tutor_id], backref="overrides_as_tutor"
    )
    student = relationship(
        "TestUser", foreign_keys=[student_id], backref="overrides_as_student"
    )
    subject = relationship("TestSubject", backref="overrides")


class TestNudge(TestBase):
    """Test version of Nudge model"""

    __tablename__ = "nudges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(50), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    personalized = Column(Boolean, default=True)
    sent_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    opened_at = Column(DateTime(timezone=True), nullable=True, index=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    trigger_reason = Column(Text)
    suggestions_made = Column(JSON)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("TestUser", backref="nudges")


class TestIntegration(TestBase, TimestampMixin):
    """Test version of Integration model"""

    __tablename__ = "integrations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    integration_type = Column(String(50), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    status = Column(String(20), default="active", index=True)
    config = Column(JSON, nullable=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("TestUser", backref="integrations")


class TestWebhook(TestBase, TimestampMixin):
    """Test version of Webhook model"""

    __tablename__ = "webhooks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=True)
    events = Column(JSON, nullable=False)
    status = Column(String(20), default="active", index=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("TestUser", backref="webhooks")
    webhook_events = relationship(
        "TestWebhookEvent", back_populates="webhook", cascade="all, delete-orphan"
    )


class TestWebhookEvent(TestBase):
    """Test version of WebhookEvent model"""

    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_id = Column(
        String(36),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(50), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, index=True)
    http_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    webhook = relationship("TestWebhook", back_populates="webhook_events")
