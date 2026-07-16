"""
Integration Handler
Endpoints for external integrations
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user, require_role
from src.config.database import get_db
from src.models.integration import Integration, Webhook
from src.models.user import User
from src.services.integrations.calendar import CalendarService
from src.services.integrations.lms import LMSService
from src.services.integrations.notifications import NotificationService
from src.services.integrations.webhooks import WebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# LMS Integration Endpoints
@router.post("/lms/canvas/sync")
async def sync_canvas_assignments(
    api_token: str = Body(..., embed=True),
    canvas_url: str = Body(..., embed=True),
    course_id: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """Sync assignments from Canvas LMS"""
    service = LMSService(db)
    result = service.sync_canvas_assignments(
        api_token=api_token, canvas_url=canvas_url, course_id=course_id
    )
    return {"success": result.get("success"), "data": result}


@router.post("/lms/blackboard/sync")
async def sync_blackboard_assignments(
    api_key: str = Body(..., embed=True),
    api_secret: str = Body(..., embed=True),
    blackboard_url: str = Body(..., embed=True),
    course_id: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """Sync assignments from Blackboard LMS"""
    service = LMSService(db)
    result = service.sync_blackboard_assignments(
        api_key=api_key,
        api_secret=api_secret,
        blackboard_url=blackboard_url,
        course_id=course_id,
    )
    if not result.get("success", False):
        # Do not expose internal error details to the client; log is already server side
        raise HTTPException(
            status_code=500, detail="An error occurred syncing with Blackboard LMS."
        )
    return {"success": True, "data": result}


@router.post("/lms/submit-grade")
async def submit_grade_to_lms(
    provider: str = Body(..., embed=True),
    config: Dict = Body(..., embed=True),
    student_id: str = Body(..., embed=True),
    assignment_id: str = Body(..., embed=True),
    grade: float = Body(..., embed=True),
    feedback: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["tutor", "admin"])),
):
    """Submit grade back to LMS (grade passback)"""
    service = LMSService(db)
    result = service.submit_grade(
        provider=provider,
        config=config,
        student_id=student_id,
        assignment_id=assignment_id,
        grade=grade,
        feedback=feedback,
    )
    return {"success": result.get("success"), "data": result}


# Calendar Integration Endpoints
@router.post("/calendar/google/sync")
async def sync_google_calendar(
    access_token: str = Body(..., embed=True),
    calendar_id: str = Body("primary", embed=True),
    start_date: Optional[str] = Body(None, embed=True),
    end_date: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """Sync events from Google Calendar"""
    service = CalendarService(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    result = service.sync_google_calendar(
        access_token=access_token,
        calendar_id=calendar_id,
        start_date=start,
        end_date=end,
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": "An internal error occurred while syncing Google calendar.",
            "data": None,
        }
    return {"success": True, "data": result}


@router.post("/calendar/google/create-event")
async def create_google_calendar_event(
    access_token: str = Body(..., embed=True),
    calendar_id: str = Body(..., embed=True),
    summary: str = Body(..., embed=True),
    start_time: str = Body(..., embed=True),
    end_time: str = Body(..., embed=True),
    description: Optional[str] = Body(None, embed=True),
    location: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """Create event in Google Calendar"""
    service = CalendarService(db)

    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    result = service.create_google_calendar_event(
        access_token=access_token,
        calendar_id=calendar_id,
        summary=summary,
        start_time=start,
        end_time=end,
        description=description,
        location=location,
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": "An internal error occurred while creating Google calendar event.",
            "data": None,
        }
    return {"success": True, "data": result}


@router.post("/calendar/outlook/sync")
async def sync_outlook_calendar(
    access_token: str = Body(..., embed=True),
    start_date: Optional[str] = Body(None, embed=True),
    end_date: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """Sync events from Outlook Calendar"""
    service = CalendarService(db)

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    result = service.sync_outlook_calendar(
        access_token=access_token, start_date=start, end_date=end
    )
    if not result.get("success"):
        # Log the error already done in service; suppress details to client
        return {
            "success": False,
            "error": "An internal error occurred while syncing Outlook calendar.",
            "data": None,
        }
    return {"success": True, "data": result}


@router.post("/calendar/outlook/create-event")
async def create_outlook_calendar_event(
    access_token: str = Body(..., embed=True),
    subject: str = Body(..., embed=True),
    start_time: str = Body(..., embed=True),
    end_time: str = Body(..., embed=True),
    body: Optional[str] = Body(None, embed=True),
    location: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["student", "tutor", "admin"])),
):
    """Create event in Outlook Calendar"""
    service = CalendarService(db)

    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    result = service.create_outlook_calendar_event(
        access_token=access_token,
        subject=subject,
        start_time=start,
        end_time=end,
        body=body,
        location=location,
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": "An internal error occurred while creating Outlook calendar event.",
            "data": None,
        }
    # Only expose relevant, non-sensitive event fields
    event = result.get("event", {})
    sanitized_event = {
        "id": event.get("id"),
        "subject": event.get("subject"),
        "start": event.get("start"),
        "end": event.get("end"),
        "location": event.get("location", {}).get("displayName")
        if event.get("location")
        else None,
        "created_at": result.get("created_at"),
    }
    return {"success": True, "data": sanitized_event}


# Notification Endpoints
@router.post("/notifications/push")
async def send_push_notification(
    user_id: str = Body(..., embed=True),
    title: str = Body(..., embed=True),
    body: str = Body(..., embed=True),
    data: Optional[Dict] = Body(None, embed=True),
    platform: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Send push notification to user"""
    service = NotificationService(db)
    result = service.send_push_notification(
        user_id=user_id, title=title, body=body, data=data, platform=platform
    )
    return {"success": result.get("success"), "data": result}


@router.post("/notifications/register-device")
async def register_device_token(
    device_token: str = Body(..., embed=True),
    platform: str = Body(..., embed=True),
    device_info: Optional[Dict] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Register device token for push notifications"""
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    service = NotificationService(db)
    result = service.register_device_token(
        user_id=str(db_user.id),
        device_token=device_token,
        platform=platform,
        device_info=device_info,
    )
    return {"success": result.get("success"), "data": result}


@router.post("/notifications/unregister-device")
async def unregister_device_token(
    device_token: str = Body(..., embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Unregister device token"""
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    service = NotificationService(db)
    result = service.unregister_device_token(
        user_id=str(db_user.id), device_token=device_token
    )
    return {"success": result.get("success"), "data": result}


# Webhook Endpoints
@router.post("/webhooks")
async def create_webhook(
    url: str = Body(..., embed=True),
    events: List[str] = Body(..., embed=True),
    secret: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Create a new webhook"""
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    service = WebhookService(db)
    result = service.create_webhook(
        user_id=str(db_user.id) if db_user else None,
        url=url,
        events=events,
        secret=secret,
    )
    return result


@router.get("/webhooks")
async def list_webhooks(
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """List all webhooks"""
    webhooks = db.query(Webhook).all()

    return {
        "success": True,
        "data": [
            {
                "id": str(w.id),
                "url": w.url,
                "events": w.events,
                "status": w.status,
                "last_triggered_at": w.last_triggered_at.isoformat()
                if w.last_triggered_at
                else None,
                "success_count": w.success_count,
                "error_count": w.error_count,
                "created_at": w.created_at.isoformat()
                if hasattr(w.created_at, "isoformat")
                else str(w.created_at),
            }
            for w in webhooks
        ],
    }


@router.post("/webhooks/trigger")
async def trigger_webhook(
    event_type: str = Body(..., embed=True),
    payload: Dict = Body(..., embed=True),
    webhook_id: Optional[str] = Body(None, embed=True),
    user_id: Optional[str] = Body(None, embed=True),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Trigger webhook for an event"""
    service = WebhookService(db)
    result = service.trigger_webhook(
        event_type=event_type, payload=payload, webhook_id=webhook_id, user_id=user_id
    )
    return result


@router.get("/webhooks/{webhook_id}/events")
async def get_webhook_events(
    webhook_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Get webhook event history"""
    service = WebhookService(db)
    result = service.get_webhook_events(
        webhook_id=webhook_id, status=status, limit=limit
    )
    return result


@router.post("/webhooks/events/{event_id}/retry")
async def retry_webhook_event(
    event_id: str,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["admin"])),
):
    """Retry a failed webhook event"""
    service = WebhookService(db)
    result = service.retry_failed_webhook(event_id)
    if not result.get("success", False) and "error" in result:
        logger.error("Webhook event retry failed: %s", result["error"])
        # Replace error details with a generic message
        result = dict(result)  # copy or ensure we do not mutate underlying service data
        result[
            "error"
        ] = "An internal error occurred. Please contact support or try again later."
    return result
