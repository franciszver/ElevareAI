"""
Analytics Aggregator
Aggregate and analyze data for dashboards and reports
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import and_, func, or_
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


class AnalyticsAggregator:
    """Aggregate analytics data for dashboards and reports"""

    def __init__(self, db: Session):
        self.db = db

    def get_student_progress_summary(self, student_id: str) -> Dict:
        """Get comprehensive progress summary for a student"""
        try:
            from uuid import UUID as UUIDType

            student_uuid = (
                UUIDType(student_id) if isinstance(student_id, str) else student_id
            )
        except (ValueError, TypeError):
            student_uuid = student_id

        # Get student (use test models if available)
        if USE_TEST_MODELS:
            student = self.db.query(TestUser).filter(TestUser.id == student_id).first()
            UserModel = TestUser
            GoalModel = TestGoal
            PracticeModel = TestPracticeAssignment
            SessionModelClass = TestSession
            QAModel = TestQAInteraction
        else:
            student = self.db.query(User).filter(User.id == student_uuid).first()
            if not student:
                student = self.db.query(User).filter(User.id == student_id).first()
            UserModel = User
            GoalModel = Goal
            PracticeModel = PracticeAssignment
            SessionModelClass = SessionModel
            QAModel = QAInteraction

        if not student:
            raise ValueError(f"Student {student_id} not found")

        # Use the actual student ID from the database for queries
        actual_student_id = student.id

        # Get goals
        goals = (
            self.db.query(GoalModel)
            .filter(GoalModel.student_id == actual_student_id)
            .all()
        )
        active_goals = [g for g in goals if g.status == "active"]
        completed_goals = [g for g in goals if g.status == "completed"]

        # Get practice stats
        practice_stats = (
            self.db.query(
                func.count(PracticeModel.id).label("total"),
                func.count(PracticeModel.id)
                .filter(PracticeModel.completed == True)
                .label("completed"),
                func.avg(PracticeModel.performance_score).label("avg_score"),
            )
            .filter(PracticeModel.student_id == actual_student_id)
            .first()
        )

        # Get session stats
        session_count = (
            self.db.query(func.count(SessionModelClass.id))
            .filter(SessionModelClass.student_id == actual_student_id)
            .scalar()
            or 0
        )

        # Get Q&A stats
        qa_count = (
            self.db.query(func.count(QAModel.id))
            .filter(QAModel.student_id == actual_student_id)
            .scalar()
            or 0
        )

        # Get recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        recent_practice = (
            self.db.query(func.count(PracticeModel.id))
            .filter(
                PracticeModel.student_id == actual_student_id,
                PracticeModel.completed == True,
                PracticeModel.completed_at >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        recent_sessions = (
            self.db.query(func.count(SessionModelClass.id))
            .filter(
                SessionModelClass.student_id == actual_student_id,
                SessionModelClass.session_date >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        return {
            "student_id": str(student_id),
            "goals": {
                "total": len(goals),
                "active": len(active_goals),
                "completed": len(completed_goals),
                "average_completion": float(
                    sum(g.completion_percentage for g in active_goals)
                    / len(active_goals)
                )
                if active_goals
                else 0.0,
            },
            "practice": {
                "total_assigned": practice_stats.total or 0,
                "completed": practice_stats.completed or 0,
                "completion_rate": (
                    practice_stats.completed / practice_stats.total * 100
                )
                if practice_stats.total
                else 0.0,
                "average_score": float(practice_stats.avg_score)
                if practice_stats.avg_score
                else 0.0,
                "recent_30_days": recent_practice,
            },
            "sessions": {"total": session_count, "recent_30_days": recent_sessions},
            "qa": {"total_queries": qa_count},
            "gamification": student.gamification or {},
        }

    def get_override_analytics(
        self,
        subject_id: Optional[str] = None,
        difficulty_level: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """Get override frequency analytics"""
        if USE_TEST_MODELS:
            OverrideModel = TestOverride
            SubjectModel = TestSubject
        else:
            OverrideModel = Override
            SubjectModel = Subject

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

        # Group by type
        by_type = {}
        for override in overrides:
            override_type = override.override_type
            if override_type not in by_type:
                by_type[override_type] = 0
            by_type[override_type] += 1

        # Group by subject
        by_subject = {}
        for override in overrides:
            if override.subject_id:
                if USE_TEST_MODELS:
                    subject = (
                        self.db.query(SubjectModel)
                        .filter(SubjectModel.id == override.subject_id)
                        .first()
                    )
                else:
                    try:
                        from uuid import UUID as UUIDType

                        subject_uuid = (
                            UUIDType(override.subject_id)
                            if isinstance(override.subject_id, str)
                            else override.subject_id
                        )
                        subject = (
                            self.db.query(SubjectModel)
                            .filter(SubjectModel.id == subject_uuid)
                            .first()
                        )
                    except (ValueError, TypeError):
                        subject = (
                            self.db.query(SubjectModel)
                            .filter(SubjectModel.id == override.subject_id)
                            .first()
                        )
                subject_name = subject.name if subject else "Unknown"
                if subject_name not in by_subject:
                    by_subject[subject_name] = 0
                by_subject[subject_name] += 1

        # Group by difficulty
        by_difficulty = {}
        for override in overrides:
            if override.difficulty_level:
                diff = override.difficulty_level
                if diff not in by_difficulty:
                    by_difficulty[diff] = 0
                by_difficulty[diff] += 1

        return {
            "total_overrides": len(overrides),
            "by_type": by_type,
            "by_subject": by_subject,
            "by_difficulty": by_difficulty,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def get_confidence_analytics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict:
        """Get confidence distribution analytics"""
        if USE_TEST_MODELS:
            QAModel = TestQAInteraction
        else:
            QAModel = QAInteraction

        query = self.db.query(QAModel)

        if start_date:
            query = query.filter(QAModel.created_at >= start_date)

        if end_date:
            query = query.filter(QAModel.created_at <= end_date)

        interactions = query.all()

        total = len(interactions)
        if total == 0:
            return {
                "total_queries": 0,
                "confidence_distribution": {"High": 0, "Medium": 0, "Low": 0},
                "escalation_rate": 0.0,
                "average_confidence_score": 0.0,
            }

        # Count by confidence
        confidence_counts = {"High": 0, "Medium": 0, "Low": 0}
        confidence_scores = []
        escalations = 0

        for interaction in interactions:
            confidence = interaction.confidence
            if confidence in confidence_counts:
                confidence_counts[confidence] += 1

            if interaction.confidence_score:
                confidence_scores.append(float(interaction.confidence_score))

            if interaction.tutor_escalation_suggested:
                escalations += 1

        # Calculate percentages
        confidence_distribution = {
            "High": round(confidence_counts["High"] / total * 100, 2),
            "Medium": round(confidence_counts["Medium"] / total * 100, 2),
            "Low": round(confidence_counts["Low"] / total * 100, 2),
        }

        return {
            "total_queries": total,
            "confidence_distribution": confidence_distribution,
            "confidence_counts": confidence_counts,
            "escalation_rate": round(escalations / total * 100, 2),
            "average_confidence_score": round(
                sum(confidence_scores) / len(confidence_scores), 2
            )
            if confidence_scores
            else 0.0,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def get_nudge_analytics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict:
        """Get nudge engagement analytics"""
        if USE_TEST_MODELS:
            NudgeModel = TestNudge
        else:
            NudgeModel = Nudge

        query = self.db.query(NudgeModel)

        if start_date:
            query = query.filter(NudgeModel.sent_at >= start_date)

        if end_date:
            query = query.filter(NudgeModel.sent_at <= end_date)

        nudges = query.all()

        total = len(nudges)
        if total == 0:
            return {
                "total_nudges": 0,
                "by_type": {},
                "engagement": {
                    "opened": 0,
                    "clicked": 0,
                    "opened_rate": 0.0,
                    "clicked_rate": 0.0,
                },
            }

        # Group by type
        by_type = {}
        opened = 0
        clicked = 0

        for nudge in nudges:
            nudge_type = nudge.type
            if nudge_type not in by_type:
                by_type[nudge_type] = {"sent": 0, "opened": 0, "clicked": 0}
            by_type[nudge_type]["sent"] += 1

            if nudge.opened_at:
                opened += 1
                by_type[nudge_type]["opened"] += 1

            if nudge.clicked_at:
                clicked += 1
                by_type[nudge_type]["clicked"] += 1

        return {
            "total_nudges": total,
            "by_type": by_type,
            "engagement": {
                "opened": opened,
                "clicked": clicked,
                "opened_rate": round(opened / total * 100, 2),
                "clicked_rate": round(clicked / total * 100, 2),
            },
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def get_platform_overview(self) -> Dict:
        """Get overall platform statistics"""
        if USE_TEST_MODELS:
            UserModel = TestUser
            GoalModel = TestGoal
            PracticeModel = TestPracticeAssignment
            QAModel = TestQAInteraction
            SessionModelClass = TestSession
        else:
            UserModel = User
            GoalModel = Goal
            PracticeModel = PracticeAssignment
            QAModel = QAInteraction
            SessionModelClass = SessionModel

        # User counts
        total_users = self.db.query(func.count(UserModel.id)).scalar() or 0
        students = (
            self.db.query(func.count(UserModel.id))
            .filter(UserModel.role == "student")
            .scalar()
            or 0
        )
        tutors = (
            self.db.query(func.count(UserModel.id))
            .filter(UserModel.role == "tutor")
            .scalar()
            or 0
        )

        # Activity counts
        total_sessions = self.db.query(func.count(SessionModelClass.id)).scalar() or 0
        total_practice = (
            self.db.query(func.count(PracticeModel.id))
            .filter(PracticeModel.completed == True)
            .scalar()
            or 0
        )
        total_qa = self.db.query(func.count(QAModel.id)).scalar() or 0
        total_goals = self.db.query(func.count(GoalModel.id)).scalar() or 0
        active_goals = (
            self.db.query(func.count(GoalModel.id))
            .filter(GoalModel.status == "active")
            .scalar()
            or 0
        )

        # Recent activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_sessions = (
            self.db.query(func.count(SessionModelClass.id))
            .filter(SessionModelClass.session_date >= seven_days_ago)
            .scalar()
            or 0
        )

        recent_practice = (
            self.db.query(func.count(PracticeModel.id))
            .filter(
                PracticeModel.completed == True,
                PracticeModel.completed_at >= seven_days_ago,
            )
            .scalar()
            or 0
        )

        return {
            "users": {"total": total_users, "students": students, "tutors": tutors},
            "activity": {
                "total_sessions": total_sessions,
                "total_practice_completed": total_practice,
                "total_qa_queries": total_qa,
                "total_goals": total_goals,
                "active_goals": active_goals,
            },
            "recent_activity_7_days": {
                "sessions": recent_sessions,
                "practice_completed": recent_practice,
            },
        }
