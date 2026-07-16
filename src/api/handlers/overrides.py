"""
Tutor Overrides Handler
POST /overrides - Create tutor override
GET /overrides/:student_id - Get all overrides for student
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user, require_role
from src.config.database import get_db
from src.models.override import Override
from src.models.practice import PracticeAssignment
from src.models.summary import Summary
from src.models.user import User

router = APIRouter(prefix="/overrides", tags=["overrides"])


class OverrideRequest(BaseModel):
    tutor_id: str
    student_id: str
    override_type: str  # "summary" | "practice" | "qa_answer"
    target_id: str  # ID of item being overridden
    action: str
    new_content: Dict[str, Any]
    reason: Optional[str] = None


@router.post("/")
async def create_override(
    request: OverrideRequest,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["tutor", "admin"])),
):
    """
    Create a tutor override of an AI suggestion

    Called by Rails app when tutor overrides AI
    """
    # Verify tutor
    tutor = db.query(User).filter(User.id == request.tutor_id).first()
    if not tutor or tutor.role not in ["tutor", "admin"]:
        raise HTTPException(status_code=403, detail="Only tutors can create overrides")

    # Get the item being overridden
    original_content = {}
    summary_id = None
    practice_assignment_id = None
    qa_interaction_id = None
    subject_id = None
    difficulty_level = None

    if request.override_type == "summary":
        summary = db.query(Summary).filter(Summary.id == request.target_id).first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        original_content = {
            "next_steps": summary.next_steps,
            "narrative": summary.narrative,
        }
        summary_id = summary.id
        subject_id = summary.session.subject_id if summary.session else None

        # Update summary
        if "next_steps" in request.new_content:
            summary.next_steps = request.new_content["next_steps"]
        if "narrative" in request.new_content:
            summary.narrative = request.new_content["narrative"]
        summary.overridden = True

    elif request.override_type == "practice":
        practice = (
            db.query(PracticeAssignment)
            .filter(PracticeAssignment.id == request.target_id)
            .first()
        )
        if not practice:
            raise HTTPException(status_code=404, detail="Practice assignment not found")
        original_content = {
            "question": practice.ai_question_text
            or (practice.bank_item.question_text if practice.bank_item else ""),
            "answer": practice.ai_answer_text
            or (practice.bank_item.answer_text if practice.bank_item else ""),
        }
        practice_assignment_id = practice.id
        subject_id = practice.subject_id
        difficulty_level = practice.difficulty_level

        # Update practice assignment
        if "question" in request.new_content:
            practice.ai_question_text = request.new_content["question"]
        if "answer" in request.new_content:
            practice.ai_answer_text = request.new_content["answer"]
        practice.overridden = True

    # Create override record
    override = Override(
        id=uuid.uuid4(),
        tutor_id=uuid.UUID(request.tutor_id),
        student_id=uuid.UUID(request.student_id),
        override_type=request.override_type,
        action=request.action,
        summary_id=summary_id,
        practice_assignment_id=practice_assignment_id,
        qa_interaction_id=qa_interaction_id,
        original_content=original_content,
        new_content=request.new_content,
        reason=request.reason,
        subject_id=subject_id,
        difficulty_level=difficulty_level,
    )

    db.add(override)

    # Link override to the overridden item
    if summary_id:
        summary.override_id = override.id
    if practice_assignment_id:
        practice.override_id = override.id

    db.commit()
    db.refresh(override)

    return {
        "success": True,
        "data": {
            "override_id": str(override.id),
            "tutor_id": request.tutor_id,
            "student_id": request.student_id,
            "override_type": request.override_type,
            "action": request.action,
            "dashboard_updated": True,
            "created_at": override.created_at.isoformat()
            if hasattr(override.created_at, "isoformat")
            else str(override.created_at),
        },
    }


@router.get("/{student_id}")
async def get_overrides(
    student_id: UUID,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(require_role(["tutor", "admin"])),
):
    """
    Get all overrides for a student (tutor view)
    """
    overrides = (
        db.query(Override)
        .filter(Override.student_id == student_id)
        .order_by(Override.created_at.desc())
        .all()
    )

    return {
        "success": True,
        "data": {
            "overrides": [
                {
                    "override_id": str(o.id),
                    "tutor_name": o.tutor.email if o.tutor else "Unknown",
                    "override_type": o.override_type,
                    "action": o.action,
                    "reason": o.reason,
                    "created_at": o.created_at.isoformat()
                    if hasattr(o.created_at, "isoformat")
                    else str(o.created_at),
                }
                for o in overrides
            ]
        },
    }
