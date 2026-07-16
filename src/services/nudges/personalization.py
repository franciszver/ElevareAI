"""
Nudge Personalization Service
Advanced personalization for nudges based on student data
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from src.models.goal import Goal
from src.models.practice import PracticeAssignment
from src.models.qa import QAInteraction
from src.models.session import Session as SessionModel
from src.models.subject import Subject
from src.models.user import User


class NudgePersonalization:
    """Service for personalizing nudges based on student data"""

    def __init__(self, db: DBSession):
        self.db = db

    def get_student_insights(self, student_id: str) -> Dict:
        """
        Get comprehensive student insights for personalization

        Returns:
            Dict with learning patterns, preferences, progress
        """
        try:
            from uuid import UUID as UUIDType

            student_uuid = (
                UUIDType(student_id) if isinstance(student_id, str) else student_id
            )
        except (ValueError, TypeError):
            student_uuid = student_id

        student = self.db.query(User).filter(User.id == student_uuid).first()
        if not student:
            return {}

        # Get recent activity
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        recent_sessions = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.student_id == student_uuid,
                SessionModel.session_date >= cutoff_date,
            )
            .all()
        )

        recent_practice = (
            self.db.query(PracticeAssignment)
            .filter(
                PracticeAssignment.student_id == student_uuid,
                PracticeAssignment.completed_at.isnot(None),
                PracticeAssignment.completed_at >= cutoff_date,
            )
            .all()
        )

        recent_qa = (
            self.db.query(QAInteraction)
            .filter(
                QAInteraction.student_id == student_uuid,
                QAInteraction.created_at >= cutoff_date,
            )
            .all()
        )

        # Calculate patterns
        preferred_subjects = self._get_preferred_subjects(
            student_uuid, recent_sessions, recent_practice
        )
        learning_pace = self._calculate_learning_pace(recent_sessions, recent_practice)
        engagement_level = self._calculate_engagement_level(
            recent_sessions, recent_practice, recent_qa
        )
        time_preferences = self._get_time_preferences(recent_sessions, recent_practice)

        # Gamification removed - no longer used

        return {
            "preferred_subjects": preferred_subjects,
            "learning_pace": learning_pace,  # slow, moderate, fast
            "engagement_level": engagement_level,  # low, medium, high
            "time_preferences": time_preferences,  # morning, afternoon, evening
            "recent_activity": {
                "sessions_30d": len(recent_sessions),
                "practice_30d": len(recent_practice),
                "qa_30d": len(recent_qa),
            },
        }

    def personalize_nudge_message(
        self,
        base_message: str,
        nudge_type: str,
        student_id: str,
        insights: Optional[Dict] = None,
    ) -> str:
        """
        Personalize nudge message based on student insights

        Args:
            base_message: Base nudge message
            nudge_type: Type of nudge
            student_id: Student ID
            insights: Optional pre-computed insights

        Returns:
            Personalized message
        """
        if not insights:
            insights = self.get_student_insights(student_id)

        # Convert student_id to UUID for query
        try:
            from uuid import UUID as UUIDType

            student_uuid = (
                UUIDType(student_id) if isinstance(student_id, str) else student_id
            )
        except (ValueError, TypeError):
            student_uuid = student_id

        student = self.db.query(User).filter(User.id == student_uuid).first()
        student_name = (
            student.profile.get("name") if student and student.profile else None
        )

        # Personalize based on type
        if nudge_type == "inactivity":
            return self._personalize_inactivity_message(
                base_message, insights, student_name
            )
        elif nudge_type == "goal_completion":
            return self._personalize_goal_completion_message(
                base_message, insights, student_name
            )
        elif nudge_type == "login":
            return self._personalize_login_message(base_message, insights, student_name)
        elif nudge_type == "cross_subject":
            return self._personalize_cross_subject_message(
                base_message, insights, student_name
            )

        return base_message

    def get_personalized_suggestions(
        self, student_id: str, nudge_type: str, insights: Optional[Dict] = None
    ) -> List[str]:
        """
        Get personalized suggestions based on student data

        Returns:
            List of suggestion strings
        """
        if not insights:
            insights = self.get_student_insights(student_id)

        suggestions = []

        # Subject-based suggestions
        preferred_subjects = insights.get("preferred_subjects", [])
        if preferred_subjects:
            top_subject = preferred_subjects[0] if preferred_subjects else None
            if top_subject:
                suggestions.append(f"Continue practicing {top_subject['name']}")

        # Gamification removed - level and streak suggestions no longer used

        # Engagement-based suggestions
        engagement = insights.get("engagement_level", "medium")
        if engagement == "low":
            suggestions.append("Start with a quick practice session")
        elif engagement == "high":
            suggestions.append("Try a new subject or topic")

        # Time-based suggestions
        time_pref = insights.get("time_preferences", {}).get("preferred_hour", None)
        if time_pref:
            if time_pref < 12:
                suggestions.append("Start your day with a study session")
            elif time_pref < 17:
                suggestions.append("Take a study break this afternoon")
            else:
                suggestions.append("End your day with some practice")

        return suggestions[:3]  # Limit to 3 suggestions

    def _personalize_inactivity_message(
        self, base_message: str, insights: Dict, student_name: Optional[str]
    ) -> str:
        """Personalize inactivity nudge message"""
        greeting = f"Hi {student_name}!" if student_name else "Hi!"

        recent_activity = insights.get("recent_activity", {})
        sessions_count = recent_activity.get("sessions_30d", 0)
        practice_count = recent_activity.get("practice_30d", 0)

        if sessions_count == 0 and practice_count == 0:
            message = f"{greeting} We'd love to help you get started! Try completing your first practice session."
        elif sessions_count < 3:
            message = f"{greeting} You've made a great start with {sessions_count} session(s)! Keep the momentum going."
        else:
            message = f"{greeting} You've been doing great with {sessions_count} sessions. Let's keep up the progress!"

        return message

    def _personalize_goal_completion_message(
        self, base_message: str, insights: Dict, student_name: Optional[str]
    ) -> str:
        """Personalize goal completion nudge message"""
        greeting = (
            f"Congratulations {student_name}!" if student_name else "Congratulations!"
        )

        # Gamification removed - use engagement level instead
        engagement = insights.get("engagement_level", "medium")
        if engagement == "low":
            message = f"{greeting} You're making great progress! Keep it up!"
        elif engagement == "medium":
            message = f"{greeting} You're doing amazing! Keep the momentum going!"
        else:
            message = f"{greeting} Outstanding work! Keep pushing forward!"

        return message

    def _personalize_login_message(
        self, base_message: str, insights: Dict, student_name: Optional[str]
    ) -> str:
        """Personalize login nudge message"""
        greeting = f"Welcome back, {student_name}!" if student_name else "Welcome back!"

        # Gamification removed - use recent activity instead
        recent_activity = insights.get("recent_activity", {})
        practice_count = recent_activity.get("practice_30d", 0)
        if practice_count > 0:
            message = f"{greeting} Ready to continue your learning journey?"
        else:
            message = f"{greeting} Let's get started with your first practice session!"

        return message

    def _personalize_cross_subject_message(
        self, base_message: str, insights: Dict, student_name: Optional[str]
    ) -> str:
        """Personalize cross-subject nudge message"""
        preferred_subjects = insights.get("preferred_subjects", [])
        if preferred_subjects and len(preferred_subjects) > 1:
            subject_names = [s["name"] for s in preferred_subjects[:2]]
            message = f"Based on your success with {subject_names[0]}, you might also enjoy {subject_names[1]}!"
        else:
            message = base_message

        return message

    def _get_preferred_subjects(
        self, student_id, sessions: List, practice: List
    ) -> List[Dict]:
        """Get student's preferred subjects based on activity"""
        subject_counts = {}

        for session in sessions:
            if hasattr(session, "subject_id") and session.subject_id:
                subject_id = str(session.subject_id)
                subject_counts[subject_id] = subject_counts.get(subject_id, 0) + 1

        for practice_item in practice:
            if hasattr(practice_item, "subject_id") and practice_item.subject_id:
                subject_id = str(practice_item.subject_id)
                subject_counts[subject_id] = subject_counts.get(subject_id, 0) + 1

        # Get subject names
        preferred = []
        for subject_id, count in sorted(
            subject_counts.items(), key=lambda x: x[1], reverse=True
        ):
            try:
                from uuid import UUID as UUIDType

                subject_uuid = (
                    UUIDType(subject_id) if isinstance(subject_id, str) else subject_id
                )
            except (ValueError, TypeError):
                subject_uuid = subject_id

            subject = self.db.query(Subject).filter(Subject.id == subject_uuid).first()
            if subject:
                preferred.append(
                    {"id": subject_id, "name": subject.name, "activity_count": count}
                )

        return preferred[:3]  # Top 3

    def _calculate_learning_pace(self, sessions: List, practice: List) -> str:
        """Calculate student's learning pace"""
        total_items = len(sessions) + len(practice)

        if total_items < 5:
            return "slow"
        elif total_items < 15:
            return "moderate"
        else:
            return "fast"

    def _calculate_engagement_level(
        self, sessions: List, practice: List, qa: List
    ) -> str:
        """Calculate student's engagement level"""
        total_activity = len(sessions) + len(practice) + len(qa)

        if total_activity < 5:
            return "low"
        elif total_activity < 15:
            return "medium"
        else:
            return "high"

    def _get_time_preferences(self, sessions: List, practice: List) -> Dict:
        """Get student's preferred study times"""
        hours = []

        for session in sessions:
            if hasattr(session, "session_date") and session.session_date:
                hours.append(session.session_date.hour)

        for practice_item in practice:
            if hasattr(practice_item, "completed_at") and practice_item.completed_at:
                hours.append(practice_item.completed_at.hour)

        if not hours:
            return {"preferred_hour": None, "pattern": "unknown"}

        # Find most common hour
        from collections import Counter

        hour_counts = Counter(hours)
        preferred_hour = hour_counts.most_common(1)[0][0]

        # Determine pattern
        if preferred_hour < 12:
            pattern = "morning"
        elif preferred_hour < 17:
            pattern = "afternoon"
        else:
            pattern = "evening"

        return {"preferred_hour": preferred_hour, "pattern": pattern}
