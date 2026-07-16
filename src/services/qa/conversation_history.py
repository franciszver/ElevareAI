"""
Conversation History Service
Manage and retrieve Q&A conversation history for context
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

# Import models - will use test models if available
try:
    from tests.test_models import TestQAInteraction

    USE_TEST_MODELS = True
except ImportError:
    USE_TEST_MODELS = False
    from src.models.qa import QAInteraction

logger = logging.getLogger(__name__)


class ConversationHistory:
    """Service for managing Q&A conversation history"""

    def __init__(self, db: Session):
        self.db = db

    def get_recent_conversation(
        self, student_id: str, limit: int = 10, hours: int = 24
    ) -> List[Dict]:
        """
        Get recent conversation history for context

        Args:
            student_id: Student ID
            limit: Maximum number of interactions to return
            hours: Time window in hours

        Returns:
            List of recent Q&A interactions
        """
        if USE_TEST_MODELS:
            QAModel = TestQAInteraction
        else:
            QAModel = QAInteraction

        try:
            from uuid import UUID as UUIDType

            student_uuid = (
                UUIDType(student_id) if isinstance(student_id, str) else student_id
            )
        except (ValueError, TypeError):
            student_uuid = student_id

        # Get interactions from last N hours
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        if USE_TEST_MODELS:
            interactions = (
                self.db.query(QAModel)
                .filter(
                    QAModel.student_id == student_id, QAModel.created_at >= cutoff_time
                )
                .order_by(desc(QAModel.created_at))
                .limit(limit)
                .all()
            )
        else:
            interactions = (
                self.db.query(QAModel)
                .filter(
                    QAModel.student_id == student_uuid,
                    QAModel.created_at >= cutoff_time,
                )
                .order_by(desc(QAModel.created_at))
                .limit(limit)
                .all()
            )

        return [
            {
                "id": str(i.id),
                "query": i.query,
                "answer": i.answer,
                "confidence": i.confidence,
                "created_at": i.created_at.isoformat()
                if hasattr(i.created_at, "isoformat")
                else str(i.created_at),
            }
            for i in interactions
        ]

    def get_conversation_context(
        self, student_id: str, current_query: str, limit: int = 5
    ) -> Dict:
        """
        Get conversation context for current query

        Includes recent queries and answers for better context understanding

        Args:
            student_id: Student ID
            current_query: Current query being asked
            limit: Number of recent interactions to include

        Returns:
            Context dictionary with conversation history
        """
        recent = self.get_recent_conversation(student_id, limit=limit)

        # Extract topics/subjects from recent queries
        topics = set()
        for interaction in recent:
            # Simple topic extraction (in production, use NLP)
            query_lower = interaction["query"].lower()
            if "math" in query_lower or "algebra" in query_lower:
                topics.add("math")
            if "science" in query_lower or "chemistry" in query_lower:
                topics.add("science")
            if "english" in query_lower or "essay" in query_lower:
                topics.add("english")

        return {
            "recent_interactions": recent,
            "topics_discussed": list(topics),
            "interaction_count": len(recent),
            "context_window_hours": 24,
        }

    def is_follow_up_question(self, student_id: str, current_query: str) -> bool:
        """
        Determine if current query is a follow-up to previous conversation

        Args:
            student_id: Student ID
            current_query: Current query

        Returns:
            True if likely a follow-up question
        """
        recent = self.get_recent_conversation(student_id, limit=3)

        if not recent:
            return False

        # Check for follow-up indicators
        follow_up_indicators = [
            "what about",
            "how about",
            "and",
            "also",
            "what if",
            "can you explain",
            "tell me more",
            "what does that mean",
        ]

        query_lower = current_query.lower()
        has_follow_up_word = any(
            indicator in query_lower for indicator in follow_up_indicators
        )

        # Check if query references previous topic
        last_query = recent[0]["query"].lower()
        last_answer = recent[0]["answer"].lower()

        # Simple keyword matching (in production, use NLP)
        shared_keywords = set(query_lower.split()) & set(last_query.split())
        shared_keywords = shared_keywords & set(last_answer.split())

        return has_follow_up_word or len(shared_keywords) > 2
