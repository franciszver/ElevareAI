"""
Goal Progress Service
Automatically updates goal completion_percentage based on student activity
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from src.models.goal import Goal
from src.models.practice import PracticeAssignment, StudentRating
from src.models.session import Session as SessionModel

logger = logging.getLogger(__name__)


class GoalProgressService:
    """Service for updating goal progress based on student activity"""

    def __init__(self, db: DBSession):
        self.db = db

    def update_goal_progress_from_practice(
        self,
        student_id: str,
        goal_tags: Optional[List[str]] = None,
        subject_id: Optional[str] = None,
    ) -> None:
        """
        Update goal progress when a practice item is completed

        Args:
            student_id: Student UUID
            goal_tags: List of goal IDs that this practice item is linked to
            subject_id: Subject ID (used as fallback to find goals by subject)
        """
        if not goal_tags and not subject_id:
            return

        # Find goals linked to this practice item
        goals_to_update = []

        if goal_tags:
            # Find goals by their IDs in goal_tags
            for goal_id in goal_tags:
                try:
                    # Try to convert to UUID if it's a string
                    goal_uuid = UUID(goal_id) if isinstance(goal_id, str) else goal_id
                    goal = (
                        self.db.query(Goal)
                        .filter(
                            Goal.id == goal_uuid,
                            Goal.student_id == UUID(student_id)
                            if isinstance(student_id, str)
                            else student_id,
                            Goal.status == "active",
                        )
                        .first()
                    )
                    if goal and goal not in goals_to_update:
                        goals_to_update.append(goal)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid goal_id in goal_tags: {goal_id}, {e}")

        # Fallback: if no goal_tags but subject_id provided, find goals by subject
        if not goals_to_update and subject_id:
            try:
                student_uuid = (
                    UUID(student_id) if isinstance(student_id, str) else student_id
                )
                subject_uuid = (
                    UUID(subject_id) if isinstance(subject_id, str) else subject_id
                )
                goals_by_subject = (
                    self.db.query(Goal)
                    .filter(
                        Goal.student_id == student_uuid,
                        Goal.subject_id == subject_uuid,
                        Goal.status == "active",
                    )
                    .all()
                )
                for goal in goals_by_subject:
                    if goal not in goals_to_update:
                        goals_to_update.append(goal)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Invalid UUID in update_goal_progress_from_practice: {e}"
                )

        # Update each goal's progress
        for goal in goals_to_update:
            self._calculate_and_update_goal_progress(goal)

    def update_goal_progress_from_session(
        self, student_id: str, subject_id: Optional[str] = None
    ) -> None:
        """
        Update goal progress when a tutoring session is completed

        Args:
            student_id: Student UUID
            subject_id: Subject ID of the session
        """
        if not subject_id:
            return

        # Find active goals for this subject
        goals = (
            self.db.query(Goal)
            .filter(
                Goal.student_id == student_id,
                Goal.subject_id == subject_id,
                Goal.status == "active",
            )
            .all()
        )

        for goal in goals:
            self._calculate_and_update_goal_progress(goal)

    def _calculate_and_update_goal_progress(self, goal: Goal) -> None:
        """
        Calculate and update a goal's completion_percentage

        Progress is calculated based on:
        1. Practice items completed (60% weight)
        2. Elo rating improvement (30% weight)
        3. Sessions completed (10% weight)
        """
        try:
            # Get practice completion stats for this goal
            practice_stats = self._get_practice_stats(goal)

            # Get Elo rating progress
            elo_progress = self._get_elo_progress(goal)

            # Get session progress
            session_progress = self._get_session_progress(goal)

            # Calculate weighted progress
            # Practice: 60%, Elo: 30%, Sessions: 10%
            total_progress = (
                practice_stats * 0.60 + elo_progress * 0.30 + session_progress * 0.10
            )

            # Clamp to 0-100
            total_progress = max(0.0, min(100.0, total_progress))

            # Update goal
            old_completion = float(goal.completion_percentage)
            goal.completion_percentage = total_progress

            # Auto-complete goal if progress reaches 100%
            if total_progress >= 100.0 and goal.status == "active":
                goal.status = "completed"
                goal.completed_at = datetime.now(timezone.utc)
                logger.info(f"Goal {goal.id} auto-completed at 100% progress")

            self.db.commit()

            logger.debug(
                f"Updated goal {goal.id} progress: {old_completion:.1f}% -> {total_progress:.1f}%"
            )

        except Exception as e:
            logger.error(
                f"Error updating goal progress for goal {goal.id}: {e}", exc_info=True
            )
            self.db.rollback()

    def _get_practice_stats(self, goal: Goal) -> float:
        """
        Calculate practice completion percentage (0-100)

        Based on:
        - Number of completed practice items linked to this goal
        - Target: Assume 50 completed items = 100% (configurable)
        """
        from sqlalchemy.dialects.postgresql import array

        # Get practice items linked to this goal
        goal_id_str = str(goal.id)

        # Query for practice items with this goal in goal_tags
        # PostgreSQL array contains operator
        practice_query = self.db.query(PracticeAssignment).filter(
            PracticeAssignment.student_id == goal.student_id,
            PracticeAssignment.completed == True,
        )

        # Try to find items with this goal_id in goal_tags array
        # PostgreSQL: use array overlap operator (&&) or contains operator
        try:
            # Method 1: Check if goal_id is in the goal_tags array
            practice_items = practice_query.filter(
                PracticeAssignment.goal_tags.contains([goal_id_str])
            ).all()
        except Exception:
            # Fallback: If array operations don't work, try string matching
            # This is less efficient but more compatible
            all_items = practice_query.all()
            practice_items = [
                item
                for item in all_items
                if item.goal_tags and goal_id_str in item.goal_tags
            ]

        # If no items found by goal_tags, try by subject_id
        if not practice_items and goal.subject_id:
            practice_items = practice_query.filter(
                PracticeAssignment.subject_id == goal.subject_id
            ).all()

        completed_count = len(practice_items)

        # Target: 50 completed items = 100% progress
        # This can be adjusted based on goal_type or other factors
        target_items = 50
        if goal.goal_type and goal.goal_type.upper() == "SAT":
            target_items = 100  # SAT goals require more practice
        elif goal.goal_type and goal.goal_type.upper() == "AP":
            target_items = 75  # AP goals require moderate practice

        progress = min(100.0, (completed_count / target_items) * 100.0)

        return progress

    def _get_elo_progress(self, goal: Goal) -> float:
        """
        Calculate progress based on Elo rating improvement (0-100)

        Based on:
        - Current Elo rating vs starting rating (1000)
        - Target: 1500+ rating = 100% progress
        """
        if not goal.subject_id:
            return 0.0

        # Get current Elo rating for this subject
        rating = (
            self.db.query(StudentRating)
            .filter(
                StudentRating.student_id == goal.student_id,
                StudentRating.subject_id == goal.subject_id,
            )
            .first()
        )

        if not rating:
            return 0.0

        current_rating = rating.rating
        starting_rating = 1000  # Default Elo rating

        # Calculate improvement
        improvement = current_rating - starting_rating

        # Target: 500 point improvement (from 1000 to 1500) = 100% progress
        target_improvement = 500

        # Progress based on improvement
        if improvement <= 0:
            progress = 0.0
        else:
            progress = min(100.0, (improvement / target_improvement) * 100.0)

        return progress

    def _get_session_progress(self, goal: Goal) -> float:
        """
        Calculate progress based on sessions completed (0-100)

        Based on:
        - Number of sessions for this subject
        - Target: 10 sessions = 100% progress
        """
        if not goal.subject_id:
            return 0.0

        session_count = (
            self.db.query(func.count(SessionModel.id))
            .filter(
                SessionModel.student_id == goal.student_id,
                SessionModel.subject_id == goal.subject_id,
            )
            .scalar()
            or 0
        )

        # Target: 10 sessions = 100% progress
        target_sessions = 10

        progress = min(100.0, (session_count / target_sessions) * 100.0)

        return progress
