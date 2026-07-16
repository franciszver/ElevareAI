"""
Advanced Analytics Schemas
Request/response models for advanced analytics endpoints
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class OverridePatternsResponse(BaseModel):
    """Override patterns analysis response"""

    total_overrides: int
    by_subject_difficulty: Dict[str, int]
    by_tutor: Dict[str, int]
    by_type: Dict[str, int]
    top_reasons: Dict[str, int]
    average_overrides_per_tutor: float
    period: Dict


class ConfidenceTelemetryResponse(BaseModel):
    """Confidence telemetry analysis response"""

    total_interactions: int
    total_corrected: int
    correction_rate: float
    confidence_accuracy: Dict
    confidence_score_analysis: Dict
    period: Dict


class RetentionMetricsResponse(BaseModel):
    """Retention metrics response"""

    cohort_size: int
    cohort_period: Dict
    retention_rates: Dict[str, float]
    engagement_metrics: Dict


class EngagementScoreResponse(BaseModel):
    """User engagement score response"""

    user_id: str
    engagement_score: float
    score_breakdown: Dict
    activity_30_days: Dict
    engagement_level: str


class ABTestRequest(BaseModel):
    """Request to create an A/B test"""

    test_name: str = Field(..., description="Unique test name")
    description: str = Field(..., description="Test description")
    variants: List[Dict] = Field(..., description="List of variant configurations")
    start_date: Optional[str] = Field(None, description="Test start date (ISO format)")
    end_date: Optional[str] = Field(None, description="Test end date (ISO format)")


class ABTestResultsResponse(BaseModel):
    """A/B test results response"""

    test_name: str
    period: Dict
    variants: Dict
    winner: Optional[str]
    total_sent: int
    total_opened: int
    total_clicked: int
