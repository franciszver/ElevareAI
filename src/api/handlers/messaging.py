"""
Messaging Handler
Message threads between tutors and students
"""

import logging
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user, require_role
from src.api.schemas.messaging import (
    CreateThreadRequest,
    MessageResponse,
    SendMessageRequest,
    ThreadListResponse,
    ThreadResponse,
)
from src.config.database import get_db
from src.models.messaging import Message, MessageThread
from src.models.practice import PracticeAssignment
from src.models.qa import QAInteraction
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messaging", tags=["messaging"])


@router.post("/threads")
async def create_thread(
    request: CreateThreadRequest,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["tutor", "admin"])),
):
    """
    Create a new message thread

    Tutors can create threads from flagged items or manually
    """
    # Verify tutor
    tutor = db.query(User).filter(User.id == request.tutor_id).first()
    if not tutor or tutor.role not in ["tutor", "admin"]:
        raise HTTPException(status_code=403, detail="Only tutors can create threads")

    # Verify student
    student = db.query(User).filter(User.id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Check if thread already exists for this context
    if request.triggered_by_type and request.triggered_by_id:
        existing = (
            db.query(MessageThread)
            .filter(
                MessageThread.tutor_id == uuid.UUID(request.tutor_id),
                MessageThread.student_id == uuid.UUID(request.student_id),
                MessageThread.triggered_by_type == request.triggered_by_type,
                MessageThread.triggered_by_id == uuid.UUID(request.triggered_by_id),
                MessageThread.status == "open",
            )
            .first()
        )

        if existing:
            # Return existing thread
            return {
                "success": True,
                "data": {
                    "thread_id": str(existing.id),
                    "message": "Thread already exists for this item",
                    "existing_thread": True,
                },
            }

    # Create thread
    thread = MessageThread(
        id=uuid.uuid4(),
        tutor_id=uuid.UUID(request.tutor_id),
        student_id=uuid.UUID(request.student_id),
        subject=request.subject,
        status="open",
        triggered_by_type=request.triggered_by_type,
        triggered_by_id=uuid.UUID(request.triggered_by_id)
        if request.triggered_by_id
        else None,
        message_count=0,
        unread_count_tutor=0,
        unread_count_student=0,
    )

    db.add(thread)
    db.flush()

    # Add initial message if provided
    if request.initial_message:
        message = Message(
            id=uuid.uuid4(),
            thread_id=thread.id,
            sender_id=uuid.UUID(request.tutor_id),
            content=request.initial_message,
            message_type="text",
        )
        db.add(message)
        thread.message_count = 1
        thread.last_message_at = datetime.utcnow()
        thread.unread_count_student = 1

    db.commit()
    db.refresh(thread)

    return {
        "success": True,
        "data": {
            "thread_id": str(thread.id),
            "tutor_id": request.tutor_id,
            "student_id": request.student_id,
            "subject": thread.subject,
            "status": thread.status,
            "created_at": thread.created_at.isoformat()
            if hasattr(thread.created_at, "isoformat")
            else str(thread.created_at),
        },
    }


@router.post("/threads/{thread_id}/messages")
async def send_message(
    thread_id: UUID,
    request: SendMessageRequest,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Send a message in a thread

    Both tutors and students can send messages
    """
    # Get thread
    thread = db.query(MessageThread).filter(MessageThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Verify user is part of this thread
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if str(db_user.id) not in [str(thread.tutor_id), str(thread.student_id)]:
        raise HTTPException(status_code=403, detail="You are not part of this thread")

    # Create message
    message = Message(
        id=uuid.uuid4(),
        thread_id=thread.id,
        sender_id=db_user.id,
        content=request.content,
        message_type=request.message_type,
    )

    db.add(message)

    # Update thread
    thread.message_count += 1
    thread.last_message_at = datetime.utcnow()

    # Update unread counts
    if str(db_user.id) == str(thread.tutor_id):
        thread.unread_count_student += 1
    else:
        thread.unread_count_tutor += 1

    db.commit()
    db.refresh(message)

    # Send email notification to recipient
    try:
        from src.services.notifications.email import EmailService

        email_service = EmailService(db)

        # Get recipient
        if str(db_user.id) == str(thread.tutor_id):
            recipient = db.query(User).filter(User.id == thread.student_id).first()
            sender_name = db_user.email  # In production, use user's name
        else:
            recipient = db.query(User).filter(User.id == thread.tutor_id).first()
            sender_name = db_user.email

        if recipient:
            email_service.send_message_notification(
                to_email=recipient.email,
                sender_name=sender_name,
                message_preview=request.content[:200],
                thread_url=f"/messages/{thread_id}",  # In production, use actual app URL
            )
    except Exception as e:
        logger.warning(f"Failed to send message email notification: {str(e)}")
        # Don't fail the request if email fails

    return {
        "success": True,
        "data": {
            "message_id": str(message.id),
            "thread_id": str(thread_id),
            "sender_id": str(db_user.id),
            "sender_role": db_user.role,
            "content": message.content,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat()
            if hasattr(message.created_at, "isoformat")
            else str(message.created_at),
        },
    }


@router.get("/threads")
async def list_threads(
    user_id: Optional[str] = Query(
        None, description="User ID (optional, defaults to current user)"
    ),
    role: Optional[str] = Query(None, description="Filter by role (tutor or student)"),
    status: Optional[str] = Query(
        None, description="Filter by status (open, closed, archived)"
    ),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List message threads for current user

    Tutors see threads they created
    Students see threads they're part of

    If user_id is provided, use that user (for frontend compatibility)
    Otherwise, use the authenticated user from JWT token
    """
    # Support user_id query parameter for frontend compatibility
    if user_id:
        try:
            db_user = db.query(User).filter(User.id == UUID(user_id)).first()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")
    else:
        # Use authenticated user from JWT token
        user_sub = current_user.get("sub")
        db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build query
    if db_user.role == "tutor":
        query = db.query(MessageThread).filter(MessageThread.tutor_id == db_user.id)
    else:
        query = db.query(MessageThread).filter(MessageThread.student_id == db_user.id)

    # Apply filters
    if status:
        query = query.filter(MessageThread.status == status)

    threads = query.order_by(
        MessageThread.last_message_at.desc().nullslast(),
        MessageThread.created_at.desc(),
    ).all()

    return {
        "success": True,
        "data": {
            "threads": [
                {
                    "thread_id": str(t.id),
                    "tutor_id": str(t.tutor_id),
                    "student_id": str(t.student_id),
                    "subject": t.subject,
                    "status": t.status,
                    "triggered_by_type": t.triggered_by_type,
                    "triggered_by_id": str(t.triggered_by_id)
                    if t.triggered_by_id
                    else None,
                    "message_count": t.message_count,
                    "unread_count": t.unread_count_tutor
                    if db_user.role == "tutor"
                    else t.unread_count_student,
                    "last_message_at": t.last_message_at.isoformat()
                    if t.last_message_at and hasattr(t.last_message_at, "isoformat")
                    else (str(t.last_message_at) if t.last_message_at else None),
                    "created_at": t.created_at.isoformat()
                    if hasattr(t.created_at, "isoformat")
                    else str(t.created_at),
                }
                for t in threads
            ],
            "total": len(threads),
        },
    }


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: UUID,
    include_messages: bool = Query(True, description="Include messages in response"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific thread with messages
    """
    thread = db.query(MessageThread).filter(MessageThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Verify user is part of this thread
    user_sub = current_user.get("sub")
    db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if str(db_user.id) not in [str(thread.tutor_id), str(thread.student_id)]:
        raise HTTPException(status_code=403, detail="You are not part of this thread")

    # Get messages if requested
    messages_data = []
    if include_messages:
        messages = (
            db.query(Message)
            .filter(Message.thread_id == thread_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        messages_data = [
            {
                "message_id": str(m.id),
                "sender_id": str(m.sender_id),
                "sender_role": m.sender.role if m.sender else "unknown",
                "content": m.content,
                "message_type": m.message_type,
                "created_at": m.created_at.isoformat()
                if hasattr(m.created_at, "isoformat")
                else str(m.created_at),
                "read_at": m.read_at.isoformat()
                if m.read_at and hasattr(m.read_at, "isoformat")
                else (str(m.read_at) if m.read_at else None),
            }
            for m in messages
        ]

        # Mark messages as read
        unread_messages = [m for m in messages if not m.read_at]
        if unread_messages:
            for msg in unread_messages:
                if str(msg.sender_id) != str(
                    db_user.id
                ):  # Don't mark own messages as read
                    msg.read_at = datetime.utcnow()
                    msg.read_by = db_user.id

            # Update thread unread counts
            if db_user.role == "tutor":
                thread.unread_count_tutor = 0
            else:
                thread.unread_count_student = 0

            db.commit()

    return {
        "success": True,
        "data": {
            "thread_id": str(thread.id),
            "tutor_id": str(thread.tutor_id),
            "student_id": str(thread.student_id),
            "subject": thread.subject,
            "status": thread.status,
            "triggered_by_type": thread.triggered_by_type,
            "triggered_by_id": str(thread.triggered_by_id)
            if thread.triggered_by_id
            else None,
            "message_count": thread.message_count,
            "unread_count": thread.unread_count_tutor
            if db_user.role == "tutor"
            else thread.unread_count_student,
            "last_message_at": thread.last_message_at.isoformat()
            if thread.last_message_at and hasattr(thread.last_message_at, "isoformat")
            else (str(thread.last_message_at) if thread.last_message_at else None),
            "created_at": thread.created_at.isoformat()
            if hasattr(thread.created_at, "isoformat")
            else str(thread.created_at),
            "messages": messages_data,
        },
    }


@router.post("/threads/{thread_id}/close")
async def close_thread(
    thread_id: UUID,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["tutor", "admin"])),
):
    """
    Close a message thread (tutor only)
    """
    thread = db.query(MessageThread).filter(MessageThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.status = "closed"
    db.commit()

    return {"success": True, "data": {"thread_id": str(thread_id), "status": "closed"}}


@router.post("/threads/from-flagged-item")
async def create_thread_from_flagged_item(
    tutor_id: str,
    student_id: str,
    item_type: str,  # "practice" | "qa"
    item_id: str,
    subject: Optional[str] = None,
    initial_message: Optional[str] = None,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["tutor", "admin"])),
):
    """
    Create a message thread from a flagged item

    Convenience endpoint for tutors to start a conversation about a flagged practice item or escalated Q&A
    """
    # Get the flagged item
    if item_type == "practice":
        item = (
            db.query(PracticeAssignment)
            .filter(PracticeAssignment.id == item_id)
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="Practice assignment not found")
        if not item.flagged:
            raise HTTPException(status_code=400, detail="Practice item is not flagged")

        default_subject = (
            f"Review: {item.subject.name if item.subject else 'Practice Item'}"
        )
        default_message = f"I'd like to discuss this practice item with you. Let me know if you have any questions!"
        triggered_type = "flagged_practice"

    elif item_type == "qa":
        item = db.query(QAInteraction).filter(QAInteraction.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Q&A interaction not found")
        if not item.tutor_escalation_suggested:
            raise HTTPException(
                status_code=400, detail="Q&A interaction is not escalated"
            )

        default_subject = f"Follow-up: Your question about {item.query[:50]}..."
        default_message = f"I saw your question and wanted to provide some additional guidance. Let's discuss this further!"
        triggered_type = "qa_escalation"

    else:
        raise HTTPException(
            status_code=400, detail="Invalid item_type. Must be 'practice' or 'qa'"
        )

    # Create thread request
    thread_request = CreateThreadRequest(
        tutor_id=tutor_id,
        student_id=student_id,
        subject=subject or default_subject,
        triggered_by_type=triggered_type,
        triggered_by_id=item_id,
        initial_message=initial_message or default_message,
    )

    # Use the create_thread logic
    return await create_thread(thread_request, db, current_user)
