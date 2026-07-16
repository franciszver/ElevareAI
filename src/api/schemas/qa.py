"""
Q&A API Schemas
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request schema for Q&A query"""

    student_id: str = Field(..., description="Student UUID")
    query: str = Field(..., min_length=1, max_length=2000, description="Student query")
    goal_id: Optional[str] = Field(
        None, description="Optional Goal UUID to associate this question with"
    )
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class QAResponse(BaseModel):
    """Response schema for Q&A"""

    interaction_id: str
    query: str
    answer: str
    confidence: str
    confidence_score: float
    disclaimer_shown: bool
    escalation: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]
