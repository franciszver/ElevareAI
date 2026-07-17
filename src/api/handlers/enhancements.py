"""
Enhancements Handler
Endpoints for enhanced features (email notifications, conversation history, etc.)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user, require_role
from src.config.database import get_db
from src.config.settings import settings
from src.models.user import User
from src.services.notifications.email import EmailService
from src.services.qa.conversation_history import ConversationHistory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enhancements", tags=["enhancements"])


@router.get("/qa/conversation-history/{student_id}")
async def get_conversation_history(
    student_id: str,
    limit: int = Query(10, le=50),
    hours: int = Query(24, le=168),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """
    Get conversation history for a student

    Returns recent Q&A interactions for context

    Security: Students can only access their own history. Tutors/admins can access any student's history.
    """
    from uuid import UUID

    # Get authenticated user from database
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify student_id exists
    target_student = db.query(User).filter(User.id == UUID(student_id)).first()
    if not target_student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Authorization check: Students can only access their own history
    # Tutors and admins can access any student's history
    user_role = db_user.role
    if user_role == "student":
        # Student can only access their own history
        if str(db_user.id) != student_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You can only view your own conversation history",
            )
    # Tutors and admins can access any student's history (for support purposes)

    conversation_history = ConversationHistory(db)

    history = conversation_history.get_recent_conversation(
        student_id=student_id, limit=limit, hours=hours
    )

    return {
        "success": True,
        "data": {
            "interactions": history,
            "count": len(history),
            "time_window_hours": hours,
        },
    }


@router.get("/qa/conversation-context/{student_id}")
async def get_conversation_context(
    student_id: str,
    current_query: str = Query(..., description="Current query to get context for"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """
    Get conversation context for a query

    Includes recent interactions and topics discussed
    """
    conversation_history = ConversationHistory(db)

    context = conversation_history.get_conversation_context(
        student_id=student_id, current_query=current_query
    )

    is_follow_up = conversation_history.is_follow_up_question(
        student_id=student_id, current_query=current_query
    )

    return {"success": True, "data": {**context, "is_follow_up": is_follow_up}}


@router.post("/email/send")
async def send_email(
    to_email: str = Body(..., embed=True),
    subject: str = Body(..., embed=True),
    body_html: Optional[str] = Body(None, embed=True),
    body_text: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Send email notification"""
    email_service = EmailService(db)
    result = email_service.send_email(
        to_email=to_email, subject=subject, body_html=body_html, body_text=body_text
    )
    return {"success": result.get("success"), "data": result}


@router.post("/email/weekly-progress")
async def send_weekly_progress_email(
    student_id: str = Body(..., embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Send weekly progress summary email to student"""
    try:
        from uuid import UUID as UUIDType

        student_uuid = (
            UUIDType(student_id) if isinstance(student_id, str) else student_id
        )
    except (ValueError, TypeError):
        student_uuid = student_id

    student = db.query(User).filter(User.id == student_uuid).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get progress data
    from src.services.analytics.aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(db)
    progress = aggregator.get_student_progress_summary(student_id)

    # Gamification removed

    progress_data = {
        "sessions": progress["sessions"]["recent_30_days"],
        "practice_completed": progress["practice"]["recent_30_days"],
        "goals_completed": progress["goals"]["completed"],
    }

    email_service = EmailService(db)
    student_name = (
        student.profile.get("name") if student.profile else student.email.split("@")[0]
    )

    result = email_service.send_weekly_progress_summary(
        to_email=student.email, student_name=student_name, progress_data=progress_data
    )

    return {"success": result.get("success"), "data": result}


@router.post("/email/batch")
async def send_batch_emails(
    emails: List[Dict] = Body(..., embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Send batch emails"""
    email_service = EmailService(db)
    result = email_service.send_batch_emails(emails)
    return {"success": result.get("success"), "data": result}
