"""
Adaptive Practice Service
Elo-based difficulty adjustment system
"""

import math
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from src.config.settings import settings
from src.models.practice import PracticeAssignment, PracticeBankItem, StudentRating
from src.models.subject import Subject
from src.models.user import User


class AdaptivePracticeService:
    """Service for adaptive practice assignment using Elo rating system"""

    def __init__(self, db: DBSession):
        self.db = db

    def get_student_rating(self, student_id: str, subject_id: str) -> int:
        """Get or create student rating for a subject"""
        rating = (
            self.db.query(StudentRating)
            .filter(
                StudentRating.student_id == student_id,
                StudentRating.subject_id == subject_id,
            )
            .first()
        )

        if not rating:
            # Create default rating
            rating = StudentRating(
                student_id=student_id,
                subject_id=subject_id,
                rating=settings.elo_default_rating,
            )
            self.db.add(rating)
            self.db.commit()
            self.db.refresh(rating)

        return rating.rating

    def update_student_rating(
        self,
        student_id: str,
        subject_id: str,
        question_rating: int,
        performance_score: float,
    ) -> int:
        """
        Update student rating using Elo algorithm

        Args:
            student_id: Student UUID
            subject_id: Subject UUID
            question_rating: Elo rating of the question (difficulty * 100)
            performance_score: Student performance (0.0 to 1.0)

        Returns:
            New student rating
        """
        current_rating = self.get_student_rating(student_id, subject_id)

        # Calculate expected score (Elo formula)
        expected_score = 1.0 / (
            1.0 + math.pow(10.0, (question_rating - current_rating) / 400.0)
        )

        # Calculate new rating
        k_factor = settings.elo_k_factor
        new_rating = int(
            current_rating + k_factor * (performance_score - expected_score)
        )

        # Clamp to min/max
        new_rating = max(
            settings.elo_min_rating, min(settings.elo_max_rating, new_rating)
        )

        # Update database
        rating = (
            self.db.query(StudentRating)
            .filter(
                StudentRating.student_id == student_id,
                StudentRating.subject_id == subject_id,
            )
            .first()
        )

        if rating:
            rating.rating = new_rating
        else:
            rating = StudentRating(
                student_id=student_id, subject_id=subject_id, rating=new_rating
            )
            self.db.add(rating)

        self.db.commit()

        return new_rating

    def calculate_performance_score(
        self,
        correct: bool,
        time_taken_seconds: int,
        hints_used: int,
        optimal_time: int = 60,  # Expected time in seconds
    ) -> float:
        """
        Calculate performance score (0.0 to 1.0)

        Factors:
        - Accuracy (70%): Correct or incorrect
        - Speed (20%): Faster = better
        - Hints (10%): Fewer hints = better
        """
        accuracy = 1.0 if correct else 0.0

        # Time bonus (faster is better, but not too fast)
        if time_taken_seconds <= optimal_time:
            time_bonus = 1.0
        else:
            # Penalize for taking too long
            time_bonus = max(
                0.0, 1.0 - (time_taken_seconds - optimal_time) / (optimal_time * 2)
            )

        # Hint penalty
        hint_penalty = max(0.0, 1.0 - (hints_used * 0.1))

        performance = (accuracy * 0.7) + (time_bonus * 0.2) + (hint_penalty * 0.1)

        return round(performance, 2)

    def select_difficulty_range(self, student_rating: int) -> Tuple[int, int]:
        """
        Select difficulty range based on student rating

        Returns:
            Tuple of (min_difficulty, max_difficulty) on 1-10 scale
        """
        # Convert Elo rating (400-2000) to difficulty (1-10)
        # Rating 400 = difficulty 1, Rating 2000 = difficulty 10
        base_difficulty = (
            (student_rating - settings.elo_min_rating)
            / (settings.elo_max_rating - settings.elo_min_rating)
            * 9
        ) + 1

        base_difficulty = int(round(base_difficulty))

        # Provide range: ±1 difficulty
        min_difficulty = max(1, base_difficulty - 1)
        max_difficulty = min(10, base_difficulty + 1)

        return (min_difficulty, max_difficulty)

    def find_bank_items(
        self,
        subject_id: str,
        difficulty_min: int,
        difficulty_max: int,
        goal_tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[PracticeBankItem]:
        """Find practice bank items matching criteria"""
        query = self.db.query(PracticeBankItem).filter(
            PracticeBankItem.subject_id == subject_id,
            PracticeBankItem.difficulty_level >= difficulty_min,
            PracticeBankItem.difficulty_level <= difficulty_max,
            PracticeBankItem.is_active == True,
        )

        # Filter by goal tags if provided
        if goal_tags:
            # PostgreSQL array overlap operator
            for tag in goal_tags:
                query = query.filter(PracticeBankItem.goal_tags.contains([tag]))

        return query.limit(limit).all()
