"""
Advanced Analytics Handler
Endpoints for advanced analytics features
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import require_role
from src.config.database import get_db
from src.services.analytics.ab_testing import ABTestingFramework
from src.services.analytics.advanced import AdvancedAnalytics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics/advanced", tags=["advanced-analytics"])


@router.get("/override-patterns")
async def get_override_patterns(
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    difficulty_level: Optional[int] = Query(
        None, description="Filter by difficulty level"
    ),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get override pattern analysis

    Identifies trends in tutor overrides by subject, difficulty, and type
    """
    analytics = AdvancedAnalytics(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    patterns = analytics.get_override_patterns(
        subject_id=subject_id,
        difficulty_level=difficulty_level,
        start_date=start,
        end_date=end,
    )

    return {"success": True, "data": patterns}


@router.get("/confidence-telemetry")
async def get_confidence_telemetry(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get confidence telemetry analysis

    Compares AI confidence scores with tutor corrections to measure accuracy
    """
    analytics = AdvancedAnalytics(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    telemetry = analytics.get_confidence_telemetry(start_date=start, end_date=end)

    return {"success": True, "data": telemetry}


@router.get("/retention")
async def get_retention_metrics(
    cohort_start: Optional[str] = Query(
        None, description="Cohort start date (ISO format)"
    ),
    cohort_end: Optional[str] = Query(None, description="Cohort end date (ISO format)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get user retention metrics

    Calculates retention rates at different intervals (7, 14, 30, 60, 90 days)
    """
    analytics = AdvancedAnalytics(db)

    start = datetime.fromisoformat(cohort_start) if cohort_start else None
    end = datetime.fromisoformat(cohort_end) if cohort_end else None

    retention = analytics.get_retention_metrics(cohort_start=start, cohort_end=end)

    return {"success": True, "data": retention}


@router.get("/engagement/{user_id}")
async def get_engagement_score(
    user_id: str,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin", "tutor", "parent"])),
):
    """
    Get engagement score for a user

    Calculates engagement based on sessions, practice, Q&A, and goals
    """
    analytics = AdvancedAnalytics(db)

    try:
        score = analytics.get_engagement_score(user_id)
        return {"success": True, "data": score}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/ab-tests/{test_name}/results")
async def get_ab_test_results(
    test_name: str,
    variant_field: str = Query(
        "type", description="Field to use as variant (type, channel)"
    ),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get A/B test results

    Analyzes performance of different test variants
    """
    framework = ABTestingFramework(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    results = framework.get_test_results(
        test_name=test_name, variant_field=variant_field, start_date=start, end_date=end
    )

    return {"success": True, "data": results}


@router.post("/ab-tests")
async def create_ab_test(
    test_name: str,
    description: str,
    variants: list,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Create a new A/B test configuration
    """
    framework = ABTestingFramework(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    test_config = framework.create_test(
        test_name=test_name,
        description=description,
        variants=variants,
        start_date=start,
        end_date=end,
    )

    return {"success": True, "data": test_config}


@router.get("/ab-tests/statistical-significance")
async def calculate_statistical_significance(
    variant_a_clicks: int = Query(..., description="Variant A clicks"),
    variant_a_sent: int = Query(..., description="Variant A sent"),
    variant_b_clicks: int = Query(..., description="Variant B clicks"),
    variant_b_sent: int = Query(..., description="Variant B sent"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Calculate statistical significance between two variants

    Uses chi-square test to determine if results are statistically significant
    """
    framework = ABTestingFramework(db)

    significance = framework.calculate_statistical_significance(
        variant_a_clicks=variant_a_clicks,
        variant_a_sent=variant_a_sent,
        variant_b_clicks=variant_b_clicks,
        variant_b_sent=variant_b_sent,
    )

    return {"success": True, "data": significance}
