"""
Dashboard Schemas
Request/response models for parent and admin dashboards
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StudentProgressSummary(BaseModel):
    """Student progress summary for parent dashboard"""

    student_id: str
    goals: Dict
    practice: Dict
    sessions: Dict
    qa: Dict
    last_activity: Optional[str] = None


class OverrideAnalytics(BaseModel):
    """Override analytics"""

    total_overrides: int
    by_type: Dict[str, int]
    by_subject: Dict[str, int]
    by_difficulty: Dict[int, int]
    period: Dict


class ConfidenceAnalytics(BaseModel):
    """Confidence distribution analytics"""

    total_queries: int
    confidence_distribution: Dict[str, float]
    confidence_counts: Dict[str, int]
    escalation_rate: float
    average_confidence_score: float
    period: Dict


class NudgeAnalytics(BaseModel):
    """Nudge engagement analytics"""

    total_nudges: int
    by_type: Dict
    engagement: Dict
    period: Dict


class PlatformOverview(BaseModel):
    """Platform overview statistics"""

    users: Dict
    activity: Dict
    recent_activity_7_days: Dict


class ExportRequest(BaseModel):
    """Request to export data"""

    format: str = Field(..., description="Export format: csv or json")
    data_type: str = Field(
        ..., description="Type of data to export: students, overrides, analytics"
    )
    filters: Optional[Dict] = Field(None, description="Optional filters for export")
