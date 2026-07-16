"""
Practice Item Generator
AI-powered practice question generation
"""

import json
import re
import uuid
from typing import Dict, List, Optional

from src.models.practice import PracticeBankItem
from src.services.ai.openai_client import openai_client
from src.services.ai.prompts import PromptTemplates
from src.services.practice.quality import PracticeQualityService


class PracticeGenerator:
    """Service for generating AI practice items"""

    def __init__(self):
        self.openai = openai_client
        self.quality_service = PracticeQualityService()

    def generate_practice_item(
        self,
        subject: str,
        topic: str,
        difficulty_level: int,
        goal_tags: Optional[List[str]] = None,
        student_history: Optional[List[Dict]] = None,
    ) -> Dict[str, any]:
        """
        Generate a practice item using AI with quality validation
        Uses SymPy for math problems, OpenAI for other subjects

        Args:
            subject: Subject name
            topic: Topic name
            difficulty_level: Difficulty level (1-10)
            goal_tags: Optional goal tags for alignment
            student_history: Optional student practice history for context

        Returns:
            dict with question_text, answer_text, explanation, quality_score
        """
        # Check if this is a math problem - use SymPy for better accuracy
        is_math = self._is_math_subject(subject, topic)

        if is_math:
            item = self._generate_math_item(subject, topic, difficulty_level)
        else:
            # Use quality service for context-aware generation (OpenAI)
            item = self.quality_service.generate_with_context(
                subject=subject,
                topic=topic,
                difficulty_level=difficulty_level,
                student_history=student_history,
                goal_tags=goal_tags,
            )

        # Validate quality
        validation = self.quality_service.validate_practice_item(item)
        item["quality_score"] = validation["quality_score"]
        item["quality_issues"] = validation["issues"]

        return item

    def _is_math_subject(self, subject: str, topic: str) -> bool:
        """Check if subject/topic is math-related"""
        math_keywords = [
            "math",
            "mathematics",
            "algebra",
            "geometry",
            "calculus",
            "trigonometry",
            "arithmetic",
            "equation",
            "solve",
            "linear",
            "quadratic",
            "polynomial",
            "expression",
            "simplify",
            "factor",
        ]
        combined = f"{subject} {topic}".lower()
        return any(keyword in combined for keyword in math_keywords)

    def _generate_math_item(
        self, subject: str, topic: str, difficulty_level: int
    ) -> Dict:
        """Generate math practice item using SymPy"""
        try:
            # Lazy import to avoid requiring SymPy if not installed
            if self._math_generator is None:
                from src.services.practice.math_generator import MathGenerator

                self._math_generator = MathGenerator()

            topic_lower = topic.lower()

            # Determine problem type from topic
            if "linear" in topic_lower or "equation" in topic_lower:
                if "quadratic" in topic_lower:
                    return self._math_generator.generate_quadratic_equation(
                        difficulty_level
                    )
                else:
                    return self._math_generator.generate_linear_equation(
                        difficulty_level
                    )
            elif "quadratic" in topic_lower:
                return self._math_generator.generate_quadratic_equation(
                    difficulty_level
                )
            elif "simplify" in topic_lower or "expression" in topic_lower:
                operation = "simplify"
                if "expand" in topic_lower:
                    operation = "expand"
                elif "factor" in topic_lower:
                    operation = "factor"
                return self._math_generator.generate_expression_simplification(
                    difficulty_level, operation
                )
            else:
                # Default to linear equations
                return self._math_generator.generate_linear_equation(difficulty_level)
        except ImportError:
            # SymPy not installed, fall back to OpenAI
            return self.quality_service.generate_with_context(
                subject=subject, topic=topic, difficulty_level=difficulty_level
            )
        except Exception as e:
            # Math generation failed, fall back to OpenAI
            return self.quality_service.generate_with_context(
                subject=subject, topic=topic, difficulty_level=difficulty_level
            )
