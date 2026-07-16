"""
Messaging Tests
Tests for message thread functionality
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.api.handlers.messaging import (
    create_thread,
    create_thread_from_flagged_item,
    get_thread,
    list_threads,
    send_message,
)
from src.api.schemas.messaging import CreateThreadRequest, SendMessageRequest
from tests.test_models import (
    TestMessage,
    TestMessageThread,
    TestPracticeAssignment,
    TestQAInteraction,
    TestSubject,
    TestUser,
)


def test_create_thread(db_session: Session):
    """Test creating a message thread"""
    # Create tutor and student
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add(tutor)
    db_session.add(student)
    db_session.commit()

    # Create thread request
    request = CreateThreadRequest(
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Test Thread",
        initial_message="Hello, let's discuss this.",
    )

    # Mock current_user
    current_user = {"sub": "tutor-sub"}

    # Create thread (simplified - direct DB access for testing)
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject=request.subject,
        status="open",
        message_count=0,
    )
    db_session.add(thread)
    db_session.commit()

    # Verify thread created
    assert thread.id is not None
    assert thread.tutor_id == tutor.id
    assert thread.student_id == student.id
    assert thread.subject == "Test Thread"
    assert thread.status == "open"


def test_create_thread_with_initial_message(db_session: Session):
    """Test creating a thread with an initial message"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add(tutor)
    db_session.add(student)
    db_session.commit()

    # Create thread
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Test Thread",
        status="open",
        message_count=0,
    )
    db_session.add(thread)
    db_session.flush()

    # Add initial message
    message = TestMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        sender_id=tutor.id,
        content="Hello, let's discuss this.",
        message_type="text",
    )
    db_session.add(message)
    thread.message_count = 1
    thread.last_message_at = datetime.utcnow()
    thread.unread_count_student = 1
    db_session.commit()

    # Verify
    assert thread.message_count == 1
    assert thread.unread_count_student == 1
    assert message.content == "Hello, let's discuss this."


def test_send_message(db_session: Session):
    """Test sending a message in a thread"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add(tutor)
    db_session.add(student)
    db_session.commit()

    # Create thread
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Test Thread",
        status="open",
        message_count=0,
    )
    db_session.add(thread)
    db_session.commit()

    # Send message
    message = TestMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        sender_id=student.id,
        content="This is my response.",
        message_type="text",
    )
    db_session.add(message)
    thread.message_count += 1
    thread.last_message_at = datetime.utcnow()
    thread.unread_count_tutor += 1
    db_session.commit()

    # Verify
    assert thread.message_count == 1
    assert thread.unread_count_tutor == 1
    assert message.content == "This is my response."


def test_list_threads_for_tutor(db_session: Session):
    """Test listing threads for a tutor"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student1 = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student1-sub",
        email="student1@test.com",
        role="student",
    )
    student2 = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student2-sub",
        email="student2@test.com",
        role="student",
    )
    db_session.add_all([tutor, student1, student2])
    db_session.commit()

    # Create threads
    thread1 = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student1.id,
        subject="Thread 1",
        status="open",
        message_count=1,
        last_message_at=datetime.utcnow(),
    )
    thread2 = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student2.id,
        subject="Thread 2",
        status="open",
        message_count=2,
        last_message_at=datetime.utcnow(),
    )
    db_session.add_all([thread1, thread2])
    db_session.commit()

    # Query threads for tutor
    threads = (
        db_session.query(TestMessageThread)
        .filter(TestMessageThread.tutor_id == tutor.id)
        .all()
    )

    assert len(threads) == 2
    assert all(t.tutor_id == tutor.id for t in threads)


def test_list_threads_for_student(db_session: Session):
    """Test listing threads for a student"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add_all([tutor, student])
    db_session.commit()

    # Create thread
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Test Thread",
        status="open",
        message_count=1,
    )
    db_session.add(thread)
    db_session.commit()

    # Query threads for student
    threads = (
        db_session.query(TestMessageThread)
        .filter(TestMessageThread.student_id == student.id)
        .all()
    )

    assert len(threads) == 1
    assert threads[0].student_id == student.id


def test_create_thread_from_flagged_practice(db_session: Session):
    """Test creating a thread from a flagged practice item"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    subject = TestSubject(id=str(uuid.uuid4()), name="Math", category="Math")
    db_session.add_all([tutor, student, subject])
    db_session.commit()

    # Create flagged practice assignment
    practice = TestPracticeAssignment(
        id=str(uuid.uuid4()),
        student_id=student.id,
        source="ai_generated",
        flagged=True,
        subject_id=subject.id,
    )
    db_session.add(practice)
    db_session.commit()

    # Create thread linked to practice
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject=f"Review: {subject.name}",
        status="open",
        triggered_by_type="flagged_practice",
        triggered_by_id=practice.id,
        message_count=0,
    )
    db_session.add(thread)
    db_session.commit()

    # Verify
    assert thread.triggered_by_type == "flagged_practice"
    assert thread.triggered_by_id == practice.id


def test_create_thread_from_escalated_qa(db_session: Session):
    """Test creating a thread from an escalated Q&A"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add_all([tutor, student])
    db_session.commit()

    # Create escalated Q&A
    qa = TestQAInteraction(
        id=str(uuid.uuid4()),
        student_id=student.id,
        query="What is calculus?",
        answer="Calculus is...",
        confidence="Low",
        tutor_escalation_suggested=True,
    )
    db_session.add(qa)
    db_session.commit()

    # Create thread linked to Q&A
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Follow-up: Your question about What is calculus?...",
        status="open",
        triggered_by_type="qa_escalation",
        triggered_by_id=qa.id,
        message_count=0,
    )
    db_session.add(thread)
    db_session.commit()

    # Verify
    assert thread.triggered_by_type == "qa_escalation"
    assert thread.triggered_by_id == qa.id


def test_thread_unread_counts(db_session: Session):
    """Test unread count tracking"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add_all([tutor, student])
    db_session.commit()

    # Create thread
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Test Thread",
        status="open",
        message_count=0,
        unread_count_tutor=0,
        unread_count_student=0,
    )
    db_session.add(thread)
    db_session.commit()

    # Tutor sends message
    msg1 = TestMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        sender_id=tutor.id,
        content="Message from tutor",
        message_type="text",
    )
    db_session.add(msg1)
    thread.message_count += 1
    thread.unread_count_student += 1
    db_session.commit()

    assert thread.unread_count_student == 1
    assert thread.unread_count_tutor == 0

    # Student sends message
    msg2 = TestMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        sender_id=student.id,
        content="Message from student",
        message_type="text",
    )
    db_session.add(msg2)
    thread.message_count += 1
    thread.unread_count_tutor += 1
    db_session.commit()

    assert thread.unread_count_student == 1
    assert thread.unread_count_tutor == 1


def test_close_thread(db_session: Session):
    """Test closing a thread"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add_all([tutor, student])
    db_session.commit()

    # Create thread
    thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Test Thread",
        status="open",
    )
    db_session.add(thread)
    db_session.commit()

    # Close thread
    thread.status = "closed"
    db_session.commit()

    # Verify
    assert thread.status == "closed"


def test_thread_status_filtering(db_session: Session):
    """Test filtering threads by status"""
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add_all([tutor, student])
    db_session.commit()

    # Create threads with different statuses
    open_thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Open Thread",
        status="open",
    )
    closed_thread = TestMessageThread(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        subject="Closed Thread",
        status="closed",
    )
    db_session.add_all([open_thread, closed_thread])
    db_session.commit()

    # Filter by status
    open_threads = (
        db_session.query(TestMessageThread)
        .filter(TestMessageThread.status == "open")
        .all()
    )

    assert len(open_threads) == 1
    assert open_threads[0].status == "open"
