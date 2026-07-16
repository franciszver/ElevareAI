"""
Advanced Analytics Service
Deep analytics including override patterns, confidence telemetry, retention, and A/B testing
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

# Import models - will use test models if available
try:
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

    USE_TEST_MODELS = True
except ImportError:
    USE_TEST_MODELS = False
    from src.models.goal import Goal
    from src.models.nudge import Nudge
    from src.models.override import Override
    from src.models.practice import PracticeAssignment
    from src.models.qa import QAInteraction
    from src.models.session import Session as SessionModel
    from src.models.subject import Subject
    from src.models.summary import Summary
    from src.models.user import User

logger = logging.getLogger(__name__)


class AdvancedAnalytics:
    """Advanced analytics for deep insights"""

    def __init__(self, db: Session):
        self.db = db

    def get_override_patterns(
        self,
        subject_id: Optional[str] = None,
        difficulty_level: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Analyze override patterns to identify trends

        Returns:
        - Override frequency by subject/difficulty
        - Most common override types
        - Override impact on student performance
        - Tutor override patterns
        """
        if USE_TEST_MODELS:
            OverrideModel = TestOverride
            SubjectModel = TestSubject
            PracticeModel = TestPracticeAssignment
        else:
            OverrideModel = Override
            SubjectModel = Subject
            PracticeModel = PracticeAssignment

        query = self.db.query(OverrideModel)

        # Apply filters
        if subject_id:
            if USE_TEST_MODELS:
                query = query.filter(OverrideModel.subject_id == subject_id)
            else:
                try:
                    from uuid import UUID as UUIDType

                    subject_uuid = (
                        UUIDType(subject_id)
                        if isinstance(subject_id, str)
                        else subject_id
                    )
                    query = query.filter(OverrideModel.subject_id == subject_uuid)
                except (ValueError, TypeError):
                    query = query.filter(OverrideModel.subject_id == subject_id)

        if difficulty_level:
            query = query.filter(OverrideModel.difficulty_level == difficulty_level)

        if start_date:
            query = query.filter(OverrideModel.created_at >= start_date)

        if end_date:
            query = query.filter(OverrideModel.created_at <= end_date)

        overrides = query.all()

        # Analyze patterns
        by_subject_difficulty = {}
        by_tutor = {}
        by_type = {}
        override_reasons = {}

        for override in overrides:
            # Subject + Difficulty combination
            if override.subject_id and override.difficulty_level:
                subject = (
                    self.db.query(SubjectModel)
                    .filter(SubjectModel.id == override.subject_id)
                    .first()
                )
                subject_name = subject.name if subject else "Unknown"
                key = f"{subject_name}_diff_{override.difficulty_level}"
                if key not in by_subject_difficulty:
                    by_subject_difficulty[key] = 0
                by_subject_difficulty[key] += 1

            # By tutor
            tutor_id = str(override.tutor_id)
            if tutor_id not in by_tutor:
                by_tutor[tutor_id] = 0
            by_tutor[tutor_id] += 1

            # By type
            override_type = override.override_type
            if override_type not in by_type:
                by_type[override_type] = 0
            by_type[override_type] += 1

            # Reasons
            if override.reason:
                reason_key = override.reason[:50]  # First 50 chars
                if reason_key not in override_reasons:
                    override_reasons[reason_key] = 0
                override_reasons[reason_key] += 1

        # Get top patterns
        top_subject_difficulty = sorted(
            by_subject_difficulty.items(), key=lambda x: x[1], reverse=True
        )[:10]

        top_tutors = sorted(by_tutor.items(), key=lambda x: x[1], reverse=True)[:10]

        top_reasons = sorted(
            override_reasons.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "total_overrides": len(overrides),
            "by_subject_difficulty": dict(top_subject_difficulty),
            "by_tutor": {k: v for k, v in top_tutors},
            "by_type": by_type,
            "top_reasons": dict(top_reasons),
            "average_overrides_per_tutor": len(overrides) / len(by_tutor)
            if by_tutor
            else 0,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def get_confidence_telemetry(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Analyze confidence scores vs tutor corrections

        Compares AI confidence with actual tutor overrides to measure accuracy
        """
        if USE_TEST_MODELS:
            QAModel = TestQAInteraction
            OverrideModel = TestOverride
        else:
            QAModel = QAInteraction
            OverrideModel = Override

        # Get all Q&A interactions in period
        qa_query = self.db.query(QAModel)
        if start_date:
            qa_query = qa_query.filter(QAModel.created_at >= start_date)
        if end_date:
            qa_query = qa_query.filter(QAModel.created_at <= end_date)

        interactions = qa_query.all()

        # Get overrides for these interactions
        override_query = self.db.query(OverrideModel).filter(
            OverrideModel.qa_interaction_id.isnot(None)
        )
        if start_date:
            override_query = override_query.filter(
                OverrideModel.created_at >= start_date
            )
        if end_date:
            override_query = override_query.filter(OverrideModel.created_at <= end_date)

        overrides = override_query.all()

        # Create override lookup
        override_by_qa = {str(o.qa_interaction_id): o for o in overrides}

        # Analyze confidence vs corrections
        high_confidence_corrected = 0
        medium_confidence_corrected = 0
        low_confidence_corrected = 0
        high_confidence_total = 0
        medium_confidence_total = 0
        low_confidence_total = 0

        confidence_scores_corrected = []
        confidence_scores_not_corrected = []

        for interaction in interactions:
            interaction_id = str(interaction.id)
            was_corrected = interaction_id in override_by_qa

            confidence = interaction.confidence
            confidence_score = (
                float(interaction.confidence_score)
                if interaction.confidence_score
                else 0.0
            )

            if confidence == "High":
                high_confidence_total += 1
                if was_corrected:
                    high_confidence_corrected += 1
                    confidence_scores_corrected.append(confidence_score)
                else:
                    confidence_scores_not_corrected.append(confidence_score)
            elif confidence == "Medium":
                medium_confidence_total += 1
                if was_corrected:
                    medium_confidence_corrected += 1
                    confidence_scores_corrected.append(confidence_score)
                else:
                    confidence_scores_not_corrected.append(confidence_score)
            elif confidence == "Low":
                low_confidence_total += 1
                if was_corrected:
                    low_confidence_corrected += 1
                    confidence_scores_corrected.append(confidence_score)
                else:
                    confidence_scores_not_corrected.append(confidence_score)

        # Calculate accuracy metrics
        high_accuracy = (
            (1 - (high_confidence_corrected / high_confidence_total)) * 100
            if high_confidence_total > 0
            else 0
        )
        medium_accuracy = (
            (1 - (medium_confidence_corrected / medium_confidence_total)) * 100
            if medium_confidence_total > 0
            else 0
        )
        low_accuracy = (
            (1 - (low_confidence_corrected / low_confidence_total)) * 100
            if low_confidence_total > 0
            else 0
        )

        avg_confidence_corrected = (
            sum(confidence_scores_corrected) / len(confidence_scores_corrected)
            if confidence_scores_corrected
            else 0
        )
        avg_confidence_not_corrected = (
            sum(confidence_scores_not_corrected) / len(confidence_scores_not_corrected)
            if confidence_scores_not_corrected
            else 0
        )

        return {
            "total_interactions": len(interactions),
            "total_corrected": len(overrides),
            "correction_rate": (len(overrides) / len(interactions) * 100)
            if interactions
            else 0,
            "confidence_accuracy": {
                "high": {
                    "total": high_confidence_total,
                    "corrected": high_confidence_corrected,
                    "accuracy_percentage": round(high_accuracy, 2),
                },
                "medium": {
                    "total": medium_confidence_total,
                    "corrected": medium_confidence_corrected,
                    "accuracy_percentage": round(medium_accuracy, 2),
                },
                "low": {
                    "total": low_confidence_total,
                    "corrected": low_confidence_corrected,
                    "accuracy_percentage": round(low_accuracy, 2),
                },
            },
            "confidence_score_analysis": {
                "average_corrected": round(avg_confidence_corrected, 3),
                "average_not_corrected": round(avg_confidence_not_corrected, 3),
                "difference": round(
                    avg_confidence_corrected - avg_confidence_not_corrected, 3
                ),
            },
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def get_retention_metrics(
        self,
        cohort_start: Optional[datetime] = None,
        cohort_end: Optional[datetime] = None,
    ) -> Dict:
        """
        Calculate user retention and engagement metrics

        Tracks user retention over time and engagement patterns
        """
        if USE_TEST_MODELS:
            UserModel = TestUser
            SessionModel = TestSession
            PracticeModel = TestPracticeAssignment
            QAModel = TestQAInteraction
        else:
            UserModel = User
            SessionModel = SessionModel
            PracticeModel = PracticeAssignment
            QAModel = QAInteraction

        # Get cohort (users who joined in period)
        if cohort_start and cohort_end:
            cohort_query = self.db.query(UserModel).filter(
                UserModel.created_at >= cohort_start,
                UserModel.created_at <= cohort_end,
                UserModel.role == "student",
            )
        else:
            # Default to last 30 days
            cohort_start = datetime.utcnow() - timedelta(days=30)
            cohort_end = datetime.utcnow()
            cohort_query = self.db.query(UserModel).filter(
                UserModel.created_at >= cohort_start, UserModel.role == "student"
            )

        cohort_users = cohort_query.all()
        cohort_size = len(cohort_users)

        if cohort_size == 0:
            return {"cohort_size": 0, "retention_rates": {}, "engagement_metrics": {}}

        # Calculate retention at different intervals
        now = datetime.utcnow()
        retention_intervals = [7, 14, 30, 60, 90]  # days

        retention_rates = {}
        for days in retention_intervals:
            cutoff_date = now - timedelta(days=days)
            active_users = 0

            for user in cohort_users:
                user_id = user.id

                # Check if user was active (session, practice, or Q&A) after cutoff
                has_session = (
                    self.db.query(func.count(SessionModel.id))
                    .filter(
                        SessionModel.student_id == user_id,
                        SessionModel.session_date >= cutoff_date,
                    )
                    .scalar()
                    > 0
                )

                has_practice = (
                    self.db.query(func.count(PracticeModel.id))
                    .filter(
                        PracticeModel.student_id == user_id,
                        PracticeModel.completed == True,
                        PracticeModel.completed_at >= cutoff_date,
                    )
                    .scalar()
                    > 0
                )

                has_qa = (
                    self.db.query(func.count(QAModel.id))
                    .filter(
                        QAModel.student_id == user_id, QAModel.created_at >= cutoff_date
                    )
                    .scalar()
                    > 0
                )

                if has_session or has_practice or has_qa:
                    active_users += 1

            retention_rate = (
                (active_users / cohort_size) * 100 if cohort_size > 0 else 0
            )
            retention_rates[f"{days}_days"] = round(retention_rate, 2)

        # Engagement metrics
        total_sessions = 0
        total_practice = 0
        total_qa = 0

        for user in cohort_users:
            user_id = user.id
            total_sessions += (
                self.db.query(func.count(SessionModel.id))
                .filter(SessionModel.student_id == user_id)
                .scalar()
                or 0
            )

            total_practice += (
                self.db.query(func.count(PracticeModel.id))
                .filter(
                    PracticeModel.student_id == user_id, PracticeModel.completed == True
                )
                .scalar()
                or 0
            )

            total_qa += (
                self.db.query(func.count(QAModel.id))
                .filter(QAModel.student_id == user_id)
                .scalar()
                or 0
            )

        return {
            "cohort_size": cohort_size,
            "cohort_period": {
                "start": cohort_start.isoformat(),
                "end": cohort_end.isoformat(),
            },
            "retention_rates": retention_rates,
            "engagement_metrics": {
                "average_sessions_per_user": round(total_sessions / cohort_size, 2)
                if cohort_size > 0
                else 0,
                "average_practice_per_user": round(total_practice / cohort_size, 2)
                if cohort_size > 0
                else 0,
                "average_qa_per_user": round(total_qa / cohort_size, 2)
                if cohort_size > 0
                else 0,
                "total_sessions": total_sessions,
                "total_practice": total_practice,
                "total_qa": total_qa,
            },
        }

    def get_engagement_score(self, user_id: str) -> Dict:
        """
        Calculate engagement score for a user

        Combines multiple factors: sessions, practice, Q&A, goals
        """
        if USE_TEST_MODELS:
            UserModel = TestUser
            SessionModel = TestSession
            PracticeModel = TestPracticeAssignment
            QAModel = TestQAInteraction
            GoalModel = TestGoal
        else:
            UserModel = User
            SessionModel = SessionModel
            PracticeModel = PracticeAssignment
            QAModel = QAInteraction
            GoalModel = Goal

        try:
            from uuid import UUID as UUIDType

            user_uuid = UUIDType(user_id) if isinstance(user_id, str) else user_id
        except (ValueError, TypeError):
            user_uuid = user_id

        # Get user
        if USE_TEST_MODELS:
            user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        else:
            user = self.db.query(UserModel).filter(UserModel.id == user_uuid).first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        user_id_actual = user.id

        # Get activity in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        sessions_count = (
            self.db.query(func.count(SessionModel.id))
            .filter(
                SessionModel.student_id == user_id_actual,
                SessionModel.session_date >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        practice_count = (
            self.db.query(func.count(PracticeModel.id))
            .filter(
                PracticeModel.student_id == user_id_actual,
                PracticeModel.completed == True,
                PracticeModel.completed_at >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        qa_count = (
            self.db.query(func.count(QAModel.id))
            .filter(
                QAModel.student_id == user_id_actual,
                QAModel.created_at >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        active_goals = (
            self.db.query(func.count(GoalModel.id))
            .filter(
                GoalModel.student_id == user_id_actual, GoalModel.status == "active"
            )
            .scalar()
            or 0
        )

        # Calculate engagement score (0-100)
        # Weighted: sessions (40%), practice (30%), Q&A (20%), goals (10%)
        session_score = min(sessions_count * 10, 40)  # Max 40 points
        practice_score = min(practice_count * 2, 30)  # Max 30 points
        qa_score = min(qa_count * 2, 20)  # Max 20 points
        goal_score = min(active_goals * 2, 10)  # Max 10 points

        engagement_score = session_score + practice_score + qa_score + goal_score

        return {
            "user_id": str(user_id),
            "engagement_score": round(engagement_score, 2),
            "score_breakdown": {
                "sessions": round(session_score, 2),
                "practice": round(practice_score, 2),
                "qa": round(qa_score, 2),
                "goals": round(goal_score, 2),
            },
            "activity_30_days": {
                "sessions": sessions_count,
                "practice_completed": practice_count,
                "qa_queries": qa_count,
                "active_goals": active_goals,
            },
            "engagement_level": (
                "high"
                if engagement_score >= 70
                else "medium"
                if engagement_score >= 40
                else "low"
            ),
        }
