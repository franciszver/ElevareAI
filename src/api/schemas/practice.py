"""
Practice API Schemas
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AssignPracticeRequest(BaseModel):
    """Request schema for assigning practice"""

    student_id: str = Field(..., description="Student UUID")
    subject: str = Field(..., min_length=1, description="Subject name")
    topic: Optional[str] = Field(None, description="Topic name")
    num_items: int = Field(5, ge=1, le=20, description="Number of practice items")
    goal_tags: Optional[List[str]] = Field(None, description="Goal tags for filtering")


class PracticeItemResponse(BaseModel):
    """Response schema for practice item"""

    item_id: str
    source: str
    question: str
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: int
    subject: str
    goal_tags: List[str]
    flagged: Optional[bool] = None
    requires_tutor_review: Optional[bool] = None


class AssignPracticeResponse(BaseModel):
    """Response schema for practice assignment"""

    assignment_id: str
    items: List[PracticeItemResponse]
    adaptive_metadata: Dict[str, Any]


class CompletePracticeRequest(BaseModel):
    """Request schema for completing practice"""

    assignment_id: str = Field(..., description="Assignment UUID")
    item_id: str = Field(..., description="Item UUID")
    student_answer: str = Field(..., description="Student's answer")
    correct: bool = Field(..., description="Whether answer is correct")
    time_taken_seconds: int = Field(..., ge=1, description="Time taken in seconds")
    hints_used: int = Field(0, ge=0, description="Number of hints used")


class CompletePracticeResponse(BaseModel):
    """Response schema for practice completion"""

    performance_score: float
    student_rating_before: int
    student_rating_after: int
    next_difficulty_suggestion: int
