"""
Nudges Handler
POST /nudges/check - Check if nudge should be sent
POST /nudges/:nudge_id/engage - Track nudge engagement
"""

import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user_optional
from src.config.database import get_db
from src.models.nudge import Nudge
from src.models.user import User
from src.services.nudges.engine import NudgeEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nudges", tags=["nudges"])


class NudgeCheckRequest(BaseModel):
    student_id: str
    check_type: str  # "inactivity" | "goal_completion" | "login"


class NudgeEngageRequest(BaseModel):
    engagement_type: str  # "opened" | "clicked"


@router.post("/check")
async def check_nudge(
    request: NudgeCheckRequest,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Check if a student should receive a nudge

    Called by scheduled job or on login
    """
    engine = NudgeEngine(db)
    result = engine.should_send_nudge(request.student_id, request.check_type)

    if result["should_send"]:
        # Create nudge record
        nudge = Nudge(
            id=uuid.uuid4(),
            user_id=uuid.UUID(request.student_id),
            type=result["nudge"]["type"],
            channel=result["nudge"]["channel"],
            message=result["nudge"]["message"],
            personalized=result["nudge"]["personalized"],
            sent_at=datetime.now(timezone.utc),
            trigger_reason=result["nudge"].get("trigger_reason"),
            suggestions_made=result["nudge"].get("suggestions", []),
        )

        db.add(nudge)
        db.commit()
        db.refresh(nudge)

        # Send email if channel includes email
        if (
            "email" in result["nudge"]["channel"]
            or result["nudge"]["channel"] == "both"
        ):
            try:
                from src.services.notifications.email import EmailService

                email_service = EmailService(db)

                # Convert student_id to UUID for query
                try:
                    student_uuid = (
                        UUID(request.student_id)
                        if isinstance(request.student_id, str)
                        else request.student_id
                    )
                except (ValueError, TypeError):
                    student_uuid = request.student_id

                user = db.query(User).filter(User.id == student_uuid).first()
                if user:
                    email_service.send_nudge_notification(
                        to_email=user.email,
                        nudge_type=result["nudge"]["type"],
                        message=result["nudge"]["message"],
                        suggestions=result["nudge"].get("suggestions", []),
                    )
            except Exception as e:
                # Log error but don't fail the request
                logger.warning(f"Failed to send nudge email: {str(e)}")

        return {
            "success": True,
            "data": {
                "should_send": True,
                "nudge": {
                    "nudge_id": str(nudge.id),
                    "type": nudge.type,
                    "channel": nudge.channel,
                    "message": nudge.message,
                    "personalized": nudge.personalized,
                    "suggestions": nudge.suggestions_made or [],
                },
            },
        }
    else:
        return {
            "success": True,
            "data": {
                "should_send": False,
                "reason": result.get("reason", "unknown"),
                "next_available": result.get("next_available"),
            },
        }


@router.get("/users/{user_id}")
async def get_user_nudges(
    user_id: UUID,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get active nudges for a user

    Called by React frontend on login/dashboard load
    Returns nudges that haven't been dismissed and are still relevant
    """
    from datetime import timedelta

    # Get recent nudges (last 7 days) that haven't been opened yet
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

    nudges = (
        db.query(Nudge)
        .filter(
            Nudge.user_id == user_id,
            Nudge.sent_at >= cutoff_date,
            Nudge.opened_at.is_(None),  # Only show unopened nudges
        )
        .order_by(Nudge.sent_at.desc())
        .limit(5)
        .all()
    )

    # Always check if we should create a new nudge (especially for inactivity)
    # For inactivity nudges, create a new one if condition is met and no recent unopened nudge exists
    engine = NudgeEngine(db)

    # Check for inactivity nudge first (most important - should appear every login until resolved)
    try:
        inactivity_result = engine.should_send_nudge(str(user_id), "inactivity")
    except Exception as e:
        logger.error(f"Error checking inactivity nudge: {str(e)}", exc_info=True)
        # If checking fails, just return existing nudges
        inactivity_result = {"should_send": False, "reason": "check_failed"}
    if inactivity_result.get("should_send"):
        # Check if there's already an unopened inactivity nudge from today
        # Use timezone-aware comparison
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        recent_inactivity = (
            db.query(Nudge)
            .filter(
                Nudge.user_id == user_id,
                Nudge.type == "inactivity",
                Nudge.sent_at >= today_start,
                Nudge.sent_at < today_end,
                Nudge.opened_at.is_(None),
            )
            .first()
        )

        if not recent_inactivity:
            # Create the nudge directly instead of calling check_nudge to avoid recursion
            try:
                # Ensure suggestions is a list
                suggestions = inactivity_result["nudge"].get("suggestions")
                if suggestions is None:
                    suggestions = []
                elif not isinstance(suggestions, list):
                    suggestions = list(suggestions) if suggestions else []

                # Create nudge record
                nudge = Nudge(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    type=inactivity_result["nudge"]["type"],
                    channel=inactivity_result["nudge"]["channel"],
                    message=inactivity_result["nudge"]["message"],
                    personalized=inactivity_result["nudge"].get("personalized", True),
                    sent_at=datetime.now(timezone.utc),
                    trigger_reason=inactivity_result["nudge"].get("trigger_reason"),
                    suggestions_made=suggestions,
                )
                db.add(nudge)
                db.commit()
                db.refresh(nudge)

                # Refresh to get the newly created nudge
                nudges = (
                    db.query(Nudge)
                    .filter(
                        Nudge.user_id == user_id,
                        Nudge.sent_at >= cutoff_date,
                        Nudge.opened_at.is_(None),
                    )
                    .order_by(Nudge.sent_at.desc())
                    .limit(5)
                    .all()
                )
            except Exception as e:
                logger.error(
                    f"Failed to create inactivity nudge: {str(e)}", exc_info=True
                )
                db.rollback()
                # Return error details in response instead of raising
                import traceback

                error_details = traceback.format_exc()
                logger.error(f"Full traceback: {error_details}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create nudge: {str(e)}. Check logs for details.",
                )
    elif not nudges:
        # Only check for login nudge if no inactivity nudge and no unopened nudges
        login_result = engine.should_send_nudge(str(user_id), "login")
        if login_result.get("should_send"):
            try:
                # Ensure suggestions is a list
                suggestions = login_result["nudge"].get("suggestions")
                if suggestions is None:
                    suggestions = []
                elif not isinstance(suggestions, list):
                    suggestions = list(suggestions) if suggestions else []

                # Create nudge record directly
                nudge = Nudge(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    type=login_result["nudge"]["type"],
                    channel=login_result["nudge"]["channel"],
                    message=login_result["nudge"]["message"],
                    personalized=login_result["nudge"].get("personalized", True),
                    sent_at=datetime.now(timezone.utc),
                    trigger_reason=login_result["nudge"].get("trigger_reason"),
                    suggestions_made=suggestions,
                )
                db.add(nudge)
                db.commit()
                db.refresh(nudge)

                nudges = (
                    db.query(Nudge)
                    .filter(
                        Nudge.user_id == user_id,
                        Nudge.sent_at >= cutoff_date,
                        Nudge.opened_at.is_(None),
                    )
                    .order_by(Nudge.sent_at.desc())
                    .limit(5)
                    .all()
                )
            except Exception as e:
                logger.error(f"Failed to create login nudge: {str(e)}", exc_info=True)
                db.rollback()

    return {
        "success": True,
        "data": {
            "nudges": [
                {
                    "nudge_id": str(n.id),
                    "type": n.type,
                    "message": n.message,
                    "suggestions": n.suggestions_made or [],
                    "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                    "trigger_reason": n.trigger_reason,
                }
                for n in nudges
            ],
            "count": len(nudges),
        },
    }


@router.post("/{nudge_id}/engage")
async def track_nudge_engagement(
    nudge_id: UUID,
    request: NudgeEngageRequest,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Track nudge engagement (opened/clicked)

    Called by React frontend when user interacts with nudge
    """
    nudge = db.query(Nudge).filter(Nudge.id == nudge_id).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")

    if request.engagement_type == "opened" and not nudge.opened_at:
        nudge.opened_at = datetime.now(timezone.utc)
    elif request.engagement_type == "clicked" and not nudge.clicked_at:
        nudge.clicked_at = datetime.now(timezone.utc)
        # Also mark as opened if not already
        if not nudge.opened_at:
            nudge.opened_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "success": True,
        "data": {
            "nudge_id": str(nudge_id),
            "engagement_logged": True,
            "engagement_type": request.engagement_type,
        },
    }
