"""
Advanced Analytics Tests
Tests for advanced analytics functionality
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from src.services.analytics.ab_testing import ABTestingFramework
from src.services.analytics.advanced import AdvancedAnalytics
from tests.test_models import (
    TestGoal,
    TestNudge,
    TestOverride,
    TestPracticeAssignment,
    TestQAInteraction,
    TestSession,
    TestSubject,
    TestSummary,
    TestUser,
)


def test_override_patterns(db_session: Session):
    """Test override pattern analysis"""
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

    # Create multiple overrides
    override1 = TestOverride(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        override_type="practice",
        action="Modified",
        subject_id=subject.id,
        difficulty_level=5,
        reason="Too difficult",
    )
    override2 = TestOverride(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        override_type="summary",
        action="Modified",
        subject_id=subject.id,
        difficulty_level=5,
        reason="Incorrect information",
    )
    db_session.add_all([override1, override2])
    db_session.commit()

    analytics = AdvancedAnalytics(db_session)
    patterns = analytics.get_override_patterns()

    assert patterns["total_overrides"] == 2
    assert patterns["by_type"]["practice"] == 1
    assert patterns["by_type"]["summary"] == 1
    assert len(patterns["top_reasons"]) > 0


def test_confidence_telemetry(db_session: Session):
    """Test confidence telemetry analysis"""
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    tutor = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="tutor-sub",
        email="tutor@test.com",
        role="tutor",
    )
    db_session.add_all([student, tutor])
    db_session.commit()

    # Create Q&A interactions
    qa1 = TestQAInteraction(
        id=str(uuid.uuid4()),
        student_id=student.id,
        query="Test query 1",
        answer="Answer 1",
        confidence="High",
        confidence_score=0.9,
    )
    qa2 = TestQAInteraction(
        id=str(uuid.uuid4()),
        student_id=student.id,
        query="Test query 2",
        answer="Answer 2",
        confidence="Low",
        confidence_score=0.3,
    )
    db_session.add_all([qa1, qa2])
    db_session.commit()

    # Create override for one interaction
    override = TestOverride(
        id=str(uuid.uuid4()),
        tutor_id=tutor.id,
        student_id=student.id,
        override_type="qa_answer",
        action="Corrected answer",
        qa_interaction_id=qa1.id,
    )
    db_session.add(override)
    db_session.commit()

    analytics = AdvancedAnalytics(db_session)
    telemetry = analytics.get_confidence_telemetry()

    assert telemetry["total_interactions"] == 2
    assert telemetry["total_corrected"] == 1
    assert "confidence_accuracy" in telemetry
    assert telemetry["confidence_accuracy"]["high"]["corrected"] == 1


def test_retention_metrics(db_session: Session):
    """Test retention metrics calculation"""
    # Create cohort users
    student1 = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student1-sub",
        email="student1@test.com",
        role="student",
        created_at=datetime.utcnow() - timedelta(days=35),
    )
    student2 = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student2-sub",
        email="student2@test.com",
        role="student",
        created_at=datetime.utcnow() - timedelta(days=35),
    )
    db_session.add_all([student1, student2])
    db_session.commit()

    # Create recent activity for one student
    session = TestSession(
        id=str(uuid.uuid4()),
        student_id=student1.id,
        tutor_id=student1.id,
        session_date=datetime.utcnow() - timedelta(days=5),
    )
    db_session.add(session)
    db_session.commit()

    analytics = AdvancedAnalytics(db_session)
    cohort_start = datetime.utcnow() - timedelta(days=40)
    cohort_end = datetime.utcnow() - timedelta(days=30)

    retention = analytics.get_retention_metrics(
        cohort_start=cohort_start, cohort_end=cohort_end
    )

    assert retention["cohort_size"] == 2
    assert "retention_rates" in retention
    assert "engagement_metrics" in retention


def test_engagement_score(db_session: Session):
    """Test engagement score calculation"""
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    subject = TestSubject(id=str(uuid.uuid4()), name="Math", category="Math")
    db_session.add_all([student, subject])
    db_session.commit()

    # Create activity
    session = TestSession(
        id=str(uuid.uuid4()),
        student_id=student.id,
        tutor_id=student.id,
        session_date=datetime.utcnow() - timedelta(days=5),
    )
    practice = TestPracticeAssignment(
        id=str(uuid.uuid4()),
        student_id=student.id,
        source="bank",
        completed=True,
        completed_at=datetime.utcnow() - timedelta(days=3),
    )
    goal = TestGoal(
        id=str(uuid.uuid4()),
        student_id=student.id,
        created_by=student.id,
        goal_type="SAT",
        title="Test Goal",
        status="active",
    )
    db_session.add_all([session, practice, goal])
    db_session.commit()

    analytics = AdvancedAnalytics(db_session)
    score = analytics.get_engagement_score(str(student.id))

    assert score["user_id"] == str(student.id)
    assert score["engagement_score"] > 0
    assert "engagement_level" in score
    assert score["activity_30_days"]["sessions"] == 1


def test_ab_test_assignment(db_session: Session):
    """Test A/B test variant assignment"""
    framework = ABTestingFramework(db_session)

    user_id = str(uuid.uuid4())
    variants = ["control", "variant_a", "variant_b"]

    # Same user should get same variant
    variant1 = framework.assign_variant(user_id, "test1", variants)
    variant2 = framework.assign_variant(user_id, "test1", variants)

    assert variant1 == variant2
    assert variant1 in variants


def test_ab_test_results(db_session: Session):
    """Test A/B test results analysis"""
    student = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="student-sub",
        email="student@test.com",
        role="student",
    )
    db_session.add(student)
    db_session.commit()

    # Create nudges with different types (variants)
    nudge1 = TestNudge(
        id=str(uuid.uuid4()),
        user_id=student.id,
        type="inactivity",
        channel="in_app",
        message="Test",
        opened_at=datetime.utcnow(),
    )
    nudge2 = TestNudge(
        id=str(uuid.uuid4()),
        user_id=student.id,
        type="login",
        channel="email",
        message="Test",
        opened_at=datetime.utcnow(),
        clicked_at=datetime.utcnow(),
    )
    db_session.add_all([nudge1, nudge2])
    db_session.commit()

    framework = ABTestingFramework(db_session)
    results = framework.get_test_results("test", variant_field="type")

    assert "variants" in results
    assert "inactivity" in results["variants"] or "login" in results["variants"]


def test_statistical_significance(db_session: Session):
    """Test statistical significance calculation"""
    framework = ABTestingFramework(db_session)

    # Test with significant difference
    significance = framework.calculate_statistical_significance(
        variant_a_clicks=100,
        variant_a_sent=1000,
        variant_b_clicks=150,
        variant_b_sent=1000,
    )

    assert "significant" in significance
    assert "p_value" in significance
    assert "confidence_level" in significance
    assert "conversion_rates" in significance
