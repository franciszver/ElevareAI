"""
Summary API Schemas
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class CreateSummaryRequest(BaseModel):
    """Request schema for creating a summary"""

    session_id: str = Field(..., description="Session UUID")
    student_id: str = Field(..., description="Student UUID")
    tutor_id: str = Field(..., description="Tutor UUID")
    transcript: Optional[str] = Field(None, description="Session transcript text")
    session_duration_minutes: int = Field(
        ..., ge=1, le=480, description="Session duration in minutes"
    )
    subject: str = Field(..., min_length=1, max_length=100, description="Subject name")
    topics_covered: List[str] = Field(
        default_factory=list, description="List of topics covered"
    )

    @validator("session_id", "student_id", "tutor_id")
    def validate_uuid(cls, v):
        """Validate UUID format"""
        import uuid

        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")


class SummaryResponse(BaseModel):
    """Response schema for summary"""

    summary_id: str
    session_id: str
    narrative: str
    next_steps: List[str]
    subjects_covered: List[str]
    summary_type: str
    created_at: str

    class Config:
        from_attributes = True


class SummaryListResponse(BaseModel):
    """Response schema for summary list"""

    summaries: List[SummaryResponse]
    pagination: dict
