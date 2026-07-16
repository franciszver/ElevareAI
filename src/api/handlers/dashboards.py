"""
Dashboard Handler
Parent and admin dashboard endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user, require_role
from src.config.database import get_db
from src.models.goal import Goal
from src.models.session import Session as SessionModel
from src.models.summary import Summary
from src.models.user import User
from src.services.analytics.aggregator import AnalyticsAggregator
from src.services.analytics.exporter import DataExporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.get("/parent/student/{student_id}")
async def get_parent_dashboard(
    student_id: UUID,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["parent", "admin"])),
):
    """
    Get parent dashboard for a specific student

    Shows progress and recent activity
    """
    # Verify user is parent or admin
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify student exists
    student = db.query(User).filter(User.id == student_id).first()
    if not student or student.role != "student":
        raise HTTPException(status_code=404, detail="Student not found")

    # Get progress summary
    aggregator = AnalyticsAggregator(db)
    progress_summary = aggregator.get_student_progress_summary(str(student_id))

    # Get recent summaries (last 5)
    recent_summaries = (
        db.query(Summary)
        .filter(Summary.student_id == student_id)
        .order_by(Summary.created_at.desc())
        .limit(5)
        .all()
    )

    summaries_data = [
        {
            "summary_id": str(s.id),
            "session_id": str(s.session_id),
            "narrative": s.narrative[:200] + "..."
            if len(s.narrative) > 200
            else s.narrative,
            "subjects_covered": s.subjects_covered or [],
            "created_at": s.created_at.isoformat()
            if hasattr(s.created_at, "isoformat")
            else str(s.created_at),
        }
        for s in recent_summaries
    ]

    # Get active goals
    active_goals = (
        db.query(Goal)
        .filter(Goal.student_id == student_id, Goal.status == "active")
        .all()
    )

    goals_data = [
        {
            "goal_id": str(g.id),
            "title": g.title,
            "subject": g.subject.name if g.subject else "General",
            "completion_percentage": float(g.completion_percentage),
            "target_date": str(g.target_completion_date)
            if g.target_completion_date
            else None,
            "current_streak": g.current_streak,
            "xp_earned": g.xp_earned,
        }
        for g in active_goals
    ]

    return {
        "success": True,
        "data": {
            "student": {
                "student_id": str(student_id),
                "email": student.email,
                "name": student.profile.get("name") if student.profile else None,
            },
            "progress": progress_summary,
            "recent_summaries": summaries_data,
            "active_goals": goals_data,
        },
    }


@router.get("/parent/students")
async def get_parent_students(
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["parent", "admin"])),
):
    """
    Get list of students for parent

    For now, returns all students (in production, would filter by parent-student relationship)
    """
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all students (in production, filter by parent relationship)
    students = db.query(User).filter(User.role == "student").all()

    students_data = [
        {
            "student_id": str(s.id),
            "email": s.email,
            "name": s.profile.get("name") if s.profile else None,
            "last_activity": None,  # Gamification removed
        }
        for s in students
    ]

    return {
        "success": True,
        "data": {"students": students_data, "total": len(students_data)},
    }


@router.get("/admin/overview")
async def get_admin_overview(
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get admin platform overview

    Shows overall platform statistics
    """
    aggregator = AnalyticsAggregator(db)
    overview = aggregator.get_platform_overview()

    return {"success": True, "data": overview}


@router.get("/admin/overrides")
async def get_admin_override_analytics(
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
    Get override frequency analytics

    Shows override patterns by type, subject, and difficulty
    """
    aggregator = AnalyticsAggregator(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    analytics = aggregator.get_override_analytics(
        subject_id=subject_id,
        difficulty_level=difficulty_level,
        start_date=start,
        end_date=end,
    )

    return {"success": True, "data": analytics}


@router.get("/admin/confidence")
async def get_admin_confidence_analytics(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get confidence distribution analytics

    Shows Q&A confidence patterns and escalation rates
    """
    aggregator = AnalyticsAggregator(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    analytics = aggregator.get_confidence_analytics(start_date=start, end_date=end)

    return {"success": True, "data": analytics}


@router.get("/admin/nudges")
async def get_admin_nudge_analytics(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get nudge engagement analytics

    Shows nudge performance and engagement rates
    """
    aggregator = AnalyticsAggregator(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    analytics = aggregator.get_nudge_analytics(start_date=start, end_date=end)

    return {"success": True, "data": analytics}


@router.get("/admin/export")
async def export_data(
    format: str = Query(..., description="Export format: csv or json"),
    data_type: str = Query(..., description="Type: students, overrides, analytics"),
    subject_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Export data to CSV or JSON

    Supports exporting students, overrides, or analytics data
    """
    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")

    if data_type not in ["students", "overrides", "analytics"]:
        raise HTTPException(
            status_code=400,
            detail="Data type must be 'students', 'overrides', or 'analytics'",
        )

    aggregator = AnalyticsAggregator(db)
    exporter = DataExporter()

    if data_type == "students":
        # Get all students with progress data
        students = db.query(User).filter(User.role == "student").all()
        students_data = []

        for student in students:
            try:
                progress = aggregator.get_student_progress_summary(str(student.id))
                students_data.append(
                    {
                        "student_id": str(student.id),
                        "email": student.email,
                        "total_sessions": progress["sessions"]["total"],
                        "total_practice": progress["practice"]["completed"],
                        "total_qa": progress["qa"]["total_queries"],
                        "active_goals": progress["goals"]["active"],
                        "last_activity": None,  # Gamification removed
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get progress for student {student.id}: {str(e)}"
                )
                continue

        if format == "csv":
            content = exporter.export_students_to_csv(students_data)
            return Response(
                content=content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=students_{datetime.utcnow().strftime('%Y%m%d')}.csv"
                },
            )
        else:
            content = exporter.to_json(students_data)
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=students_{datetime.utcnow().strftime('%Y%m%d')}.json"
                },
            )

    elif data_type == "overrides":
        from src.models.override import Override
        from src.models.subject import Subject

        query = db.query(Override)

        if subject_id:
            try:
                from uuid import UUID as UUIDType

                subject_uuid = (
                    UUIDType(subject_id) if isinstance(subject_id, str) else subject_id
                )
                query = query.filter(Override.subject_id == subject_uuid)
            except (ValueError, TypeError):
                query = query.filter(Override.subject_id == subject_id)

        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(Override.created_at >= start)

        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(Override.created_at <= end)

        overrides = query.all()

        overrides_data = []
        for override in overrides:
            subject = (
                db.query(Subject).filter(Subject.id == override.subject_id).first()
                if override.subject_id
                else None
            )
            overrides_data.append(
                {
                    "override_id": str(override.id),
                    "tutor_id": str(override.tutor_id),
                    "student_id": str(override.student_id),
                    "override_type": override.override_type,
                    "subject": subject.name if subject else None,
                    "difficulty_level": override.difficulty_level,
                    "reason": override.reason,
                    "created_at": override.created_at.isoformat()
                    if hasattr(override.created_at, "isoformat")
                    else str(override.created_at),
                }
            )

        if format == "csv":
            content = exporter.export_overrides_to_csv(overrides_data)
            return Response(
                content=content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=overrides_{datetime.utcnow().strftime('%Y%m%d')}.csv"
                },
            )
        else:
            content = exporter.to_json(overrides_data)
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=overrides_{datetime.utcnow().strftime('%Y%m%d')}.json"
                },
            )

    else:  # analytics
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None

        analytics_data = {
            "platform_overview": aggregator.get_platform_overview(),
            "override_analytics": aggregator.get_override_analytics(
                start_date=start, end_date=end
            ),
            "confidence_analytics": aggregator.get_confidence_analytics(
                start_date=start, end_date=end
            ),
            "nudge_analytics": aggregator.get_nudge_analytics(
                start_date=start, end_date=end
            ),
            "exported_at": datetime.utcnow().isoformat(),
        }

        content = exporter.export_analytics_to_json(analytics_data)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=analytics_{datetime.utcnow().strftime('%Y%m%d')}.json"
            },
        )
