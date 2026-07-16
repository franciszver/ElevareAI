"""
Enhancement Tests
Tests for enhanced features (email, conversation history)
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from src.services.notifications.email import EmailService
from src.services.qa.conversation_history import ConversationHistory
from tests.test_models import TestQAInteraction, TestUser


def test_email_service(db_session: Session):
    """Test email service"""
    service = EmailService(db_session)

    result = service.send_email(
        to_email="test@example.com",
        subject="Test Email",
        body_html="<p>Test</p>",
        body_text="Test",
    )

    assert result["success"] is True
    assert "sent_at" in result


def test_message_notification_email(db_session: Session):
    """Test message notification email"""
    service = EmailService(db_session)

    result = service.send_message_notification(
        to_email="student@example.com",
        sender_name="Tutor Name",
        message_preview="This is a test message",
        thread_url="https://app.com/messages/123",
    )

    assert result["success"] is True


def test_nudge_notification_email(db_session: Session):
    """Test nudge notification email"""
    service = EmailService(db_session)

    result = service.send_nudge_notification(
        to_email="student@example.com",
        nudge_type="inactivity",
        message="Time to study!",
        suggestions=["Complete practice", "Review notes"],
    )

    assert result["success"] is True


def test_weekly_progress_email(db_session: Session):
    """Test weekly progress summary email"""
    service = EmailService(db_session)

    result = service.send_weekly_progress_summary(
        to_email="student@example.com",
        student_name="John",
        progress_data={
            "sessions": 5,
            "practice_completed": 20,
            "goals_completed": 2,
            "level": 5,
            "xp_earned": 500,
        },
    )

    assert result["success"] is True


def test_batch_emails(db_session: Session):
    """Test batch email sending"""
    service = EmailService(db_session)

    emails = [
        {
            "to_email": "user1@example.com",
            "subject": "Test 1",
            "body_html": "<p>Test 1</p>",
        },
        {
            "to_email": "user2@example.com",
            "subject": "Test 2",
            "body_html": "<p>Test 2</p>",
        },
    ]

    result = service.send_batch_emails(emails)

    assert result["success"] is True
    assert result["total"] == 2
    assert result["successful"] == 2


def test_get_recent_conversation(db_session: Session):
    """Test getting recent conversation history"""
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add(student)
    db_session.commit()

    # Create Q&A interactions
    qa1 = TestQAInteraction(
        id=str(uuid.uuid4()),
        student_id=student.id,
        query="What is algebra?",
        answer="Algebra is a branch of mathematics",
        confidence="High",
        created_at=datetime.utcnow() - timedelta(hours=2),
    )
    qa2 = TestQAInteraction(
        id=str(uuid.uuid4()),
        student_id=student.id,
        query="How do I solve equations?",
        answer="To solve equations, you need to isolate the variable",
        confidence="High",
        created_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add_all([qa1, qa2])
    db_session.commit()

    conversation_history = ConversationHistory(db_session)
    history = conversation_history.get_recent_conversation(
        student_id=str(student.id), limit=10, hours=24
    )

    assert len(history) >= 2
    assert history[0]["query"] == "How do I solve equations?"  # Most recent first


def test_get_conversation_context(db_session: Session):
    """Test getting conversation context"""
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add(student)
    db_session.commit()

    # Create Q&A interactions
    qa1 = TestQAInteraction(
        id=str(uuid.uuid4()),
        student_id=student.id,
        query="What is algebra?",
        answer="Algebra is a branch of mathematics",
        confidence="High",
    )
    db_session.add(qa1)
    db_session.commit()

    conversation_history = ConversationHistory(db_session)
    context = conversation_history.get_conversation_context(
        student_id=str(student.id), current_query="Can you explain more about that?"
    )

    assert "recent_interactions" in context
    assert "topics_discussed" in context
    assert context["interaction_count"] >= 1


def test_is_follow_up_question(db_session: Session):
    """Test follow-up question detection"""
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add(student)
    db_session.commit()

    # Create previous interaction
    qa1 = TestQAInteraction(
        id=str(uuid.uuid4()),
        student_id=student.id,
        query="What is algebra?",
        answer="Algebra is a branch of mathematics that uses symbols",
        confidence="High",
    )
    db_session.add(qa1)
    db_session.commit()

    conversation_history = ConversationHistory(db_session)

    # Test follow-up question
    is_follow_up = conversation_history.is_follow_up_question(
        student_id=str(student.id), current_query="Can you tell me more about that?"
    )

    assert is_follow_up is True

    # Test non-follow-up question
    is_follow_up2 = conversation_history.is_follow_up_question(
        student_id=str(student.id), current_query="What is chemistry?"
    )

    assert is_follow_up2 is False
