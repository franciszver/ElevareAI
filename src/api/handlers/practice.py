"""
Practice Assignment Handler
POST /practice/assign - Assign adaptive practice items
POST /practice/complete - Record practice completion
"""

import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from starlette.concurrency import run_in_threadpool

from src.api.middleware.auth import get_current_user_optional
from src.config.database import get_db
from src.models.job import Job, JobStatus
from src.models.practice import PracticeAssignment, PracticeBankItem, StudentRating
from src.models.subject import Subject
from src.models.user import User
from src.services.goals.progress import GoalProgressService
from src.services.jobs.practice_job import PracticeJobService
from src.services.practice.adaptive import AdaptivePracticeService
from src.services.practice.generator import PracticeGenerator
from src.services.practice.utils import generate_choices_from_answer

logger = logging.getLogger(__name__)

# Alias for backward compatibility
_generate_choices_from_answer = generate_choices_from_answer

router = APIRouter(prefix="/practice", tags=["practice"])


class CompletePracticeRequest(BaseModel):
    """Request body for completing a practice item"""

    student_answer: str
    correct: bool
    time_taken_seconds: int
    hints_used: int = 0


class AsyncPracticeRequest(BaseModel):
    """Request body for async practice assignment"""

    student_id: str
    subject: str
    topic: Optional[str] = None
    num_items: int = 5
    goal_tags: Optional[list[str]] = None
    webhook_url: Optional[
        str
    ] = None  # Optional webhook URL for completion notification


@router.post("/assign/async")
async def assign_practice_async(
    request: AsyncPracticeRequest,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Assign practice items asynchronously (returns immediately with job ID)

    Use this endpoint for long-running practice generation that may take 30+ seconds.
    The job will be processed in the background and you can:
    - Poll the job status via GET /api/v1/jobs/{job_id}
    - Connect via WebSocket to /api/v1/jobs/{job_id}/ws for real-time updates
    - Provide a webhook_url to receive completion notification
    """
    job_service = PracticeJobService(db)

    # Create job
    job = job_service.create_job(
        student_id=request.student_id,
        subject=request.subject,
        topic=request.topic,
        num_items=request.num_items,
        goal_tags=request.goal_tags,
        webhook_url=request.webhook_url,
    )

    # Process job in background
    background_tasks.add_task(job_service.process_job, job.id)

    return {
        "success": True,
        "job_id": str(job.id),
        "status": job.status,
        "message": "Practice generation started. Use the job_id to check status.",
        "status_url": f"/api/v1/jobs/{job.id}",
        "websocket_url": f"/api/v1/jobs/{job.id}/ws",
    }


@router.post("/assign")
async def assign_practice(
    student_id: str,
    subject: str,
    topic: Optional[str] = None,
    num_items: int = 5,
    goal_tags: Optional[list[str]] = None,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Assign adaptive practice items to a student

    Called by Rails app or React frontend
    """
    # Get subject - handle case-insensitive and suggest similar subjects if not found
    subject_obj = (
        db.query(Subject)
        .filter(func.lower(Subject.name) == func.lower(subject))
        .first()
    )

    if not subject_obj:
        # Try to find similar subjects
        similar_subjects = (
            db.query(Subject).filter(Subject.name.ilike(f"%{subject}%")).limit(5).all()
        )

        if similar_subjects:
            suggestions = [s.name for s in similar_subjects]
            raise HTTPException(
                status_code=404,
                detail=f"Subject '{subject}' not found. Did you mean: {', '.join(suggestions)}?",
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Subject '{subject}' not found. Please check the subject name and try again.",
            )

    # Get student
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Initialize adaptive practice service
    adaptive_service = AdaptivePracticeService(db)

    # Get student rating for this subject
    student_rating = adaptive_service.get_student_rating(
        student_id, str(subject_obj.id)
    )

    # Select difficulty range
    difficulty_min, difficulty_max = adaptive_service.select_difficulty_range(
        student_rating
    )

    # Get all previously assigned questions for this student to avoid repeats
    # Only fetch the fields we need for efficiency
    previous_assignments = (
        db.query(PracticeAssignment.bank_item_id, PracticeAssignment.ai_question_text)
        .filter(PracticeAssignment.student_id == student_id)
        .all()
    )

    # Build sets of excluded items
    excluded_bank_item_ids = set()
    excluded_question_texts = set()
    bank_item_ids_to_fetch = set()

    for prev_assignment in previous_assignments:
        # Exclude bank items that were already assigned
        if prev_assignment.bank_item_id:
            excluded_bank_item_ids.add(prev_assignment.bank_item_id)
            bank_item_ids_to_fetch.add(prev_assignment.bank_item_id)

        # Exclude AI-generated question texts
        if prev_assignment.ai_question_text:
            excluded_question_texts.add(
                prev_assignment.ai_question_text.strip().lower()
            )

    # Fetch question texts for bank items in a single query
    if bank_item_ids_to_fetch:
        bank_items_with_texts = (
            db.query(PracticeBankItem.question_text)
            .filter(
                PracticeBankItem.id.in_(bank_item_ids_to_fetch),
                PracticeBankItem.question_text.isnot(None),
            )
            .all()
        )
        for bank_item in bank_items_with_texts:
            if bank_item.question_text:
                excluded_question_texts.add(bank_item.question_text.strip().lower())

    # Try to find bank items first - request more than needed to account for duplicates
    bank_items = adaptive_service.find_bank_items(
        subject_id=str(subject_obj.id),
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        goal_tags=goal_tags,
        limit=num_items * 3,  # Request more to account for excluded items
    )

    items = []
    assignment_id = uuid.uuid4()
    all_ai_generated = len(bank_items) == 0

    # Track used questions to prevent duplicates within this assignment
    used_bank_item_ids = set()
    used_question_texts = set()

    # Add previously excluded items to the used sets
    used_bank_item_ids.update(excluded_bank_item_ids)
    used_question_texts.update(excluded_question_texts)

    # If no bank items found, try expanding difficulty range
    if len(bank_items) == 0:
        logger.info(
            f"No bank items found for subject {subject}, difficulty {difficulty_min}-{difficulty_max}. "
            f"Expanding search range."
        )
        # Expand difficulty range by ±2
        expanded_min = max(1, difficulty_min - 2)
        expanded_max = min(10, difficulty_max + 2)
        bank_items = adaptive_service.find_bank_items(
            subject_id=str(subject_obj.id),
            difficulty_min=expanded_min,
            difficulty_max=expanded_max,
            goal_tags=None,  # Remove goal tag filter for broader search
            limit=num_items * 3,  # Request more to account for excluded items
        )

    # Use bank items if available, skipping duplicates and previously assigned questions
    for bank_item in bank_items:
        # Skip if we've already used this bank item in this assignment
        if bank_item.id in used_bank_item_ids:
            continue
        # Skip if this question text was already used in this assignment
        if (
            bank_item.question_text
            and bank_item.question_text.strip().lower() in used_question_texts
        ):
            continue
        # Skip if this bank item was previously assigned to this student
        if bank_item.id in excluded_bank_item_ids:
            continue
        # Skip if this question text was previously assigned to this student
        if (
            bank_item.question_text
            and bank_item.question_text.strip().lower() in excluded_question_texts
        ):
            continue

        # Check if we have enough items already
        if len(items) >= num_items:
            break
        assignment = PracticeAssignment(
            id=uuid.uuid4(),
            student_id=uuid.UUID(student_id),
            source="bank",
            bank_item_id=bank_item.id,
            subject_id=subject_obj.id,
            difficulty_level=bank_item.difficulty_level,
            goal_tags=goal_tags or [],
            student_rating_before=student_rating,
            assigned_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(assignment)

        # Track this question as used
        used_bank_item_ids.add(bank_item.id)
        if bank_item.question_text:
            used_question_texts.add(bank_item.question_text.strip().lower())

        # Convert bank item to multiple choice format
        # For existing bank items, generate choices from answer
        choices, correct_answer = _generate_choices_from_answer(bank_item.answer_text)

        items.append(
            {
                "item_id": str(assignment.id),
                "source": "bank",
                "question": bank_item.question_text,
                "answer": bank_item.answer_text,
                "choices": choices,
                "correct_answer": correct_answer,
                "explanation": bank_item.explanation,
                "difficulty": bank_item.difficulty_level,
                "subject": subject,
                "goal_tags": bank_item.goal_tags or [],
            }
        )

    # Generate AI items if we need more
    if len(items) < num_items:
        generator = PracticeGenerator()
        needed = num_items - len(items)

        logger.info(
            f"Generating {needed} AI practice items for subject {subject}, "
            f"topic {topic or 'general'}, difficulty {difficulty_min}-{difficulty_max}"
        )

        max_attempts_per_item = 5  # Maximum attempts to generate a unique question
        attempts = 0

        while len(items) < num_items and attempts < needed * max_attempts_per_item:
            attempts += 1

            # Generate AI item (offloaded - generate_practice_item makes
            # synchronous openai_client calls that would otherwise block
            # the event loop for the duration of the LLM round-trip)
            ai_item_data = await run_in_threadpool(
                generator.generate_practice_item,
                subject=subject,
                topic=topic or subject,
                difficulty_level=(difficulty_min + difficulty_max) // 2,
                goal_tags=goal_tags,
            )

            # Check if this question text is already used in this assignment or previously assigned
            question_text = ai_item_data.get("question_text", "").strip().lower()
            if question_text in used_question_texts:
                logger.debug(
                    f"Skipping duplicate AI-generated question: {question_text[:50]}..."
                )
                continue  # Skip this duplicate and try again
            if question_text in excluded_question_texts:
                logger.debug(
                    f"Skipping previously assigned AI-generated question: {question_text[:50]}..."
                )
                continue  # Skip this previously assigned question and try again

            assignment = PracticeAssignment(
                id=uuid.uuid4(),
                student_id=uuid.UUID(student_id),
                source="ai_generated",
                ai_question_text=ai_item_data["question_text"],
                ai_answer_text=ai_item_data["answer_text"],
                ai_explanation=ai_item_data["explanation"],
                flagged=True,  # AI items are always flagged
                subject_id=subject_obj.id,
                difficulty_level=(difficulty_min + difficulty_max) // 2,
                goal_tags=goal_tags or [],
                student_rating_before=student_rating,
                assigned_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
            )
            db.add(assignment)

            # Track this question as used
            used_question_texts.add(question_text)

            # Ensure AI-generated items have multiple choice format
            choices = ai_item_data.get("choices", [])
            correct_answer = ai_item_data.get("correct_answer", "A")

            # If choices not provided, generate them
            if not choices or len(choices) < 4:
                choices, correct_answer = _generate_choices_from_answer(
                    ai_item_data["answer_text"]
                )

            items.append(
                {
                    "item_id": str(assignment.id),
                    "source": "ai_generated",
                    "flagged": True,
                    "question": ai_item_data["question_text"],
                    "answer": ai_item_data["answer_text"],
                    "choices": choices,
                    "correct_answer": correct_answer,
                    "explanation": ai_item_data["explanation"],
                    "difficulty": (difficulty_min + difficulty_max) // 2,
                    "subject": subject,
                    "goal_tags": goal_tags or [],
                    "requires_tutor_review": True,
                    "note": "AI-generated item - flagged for tutor review",
                }
            )

    db.commit()

    # Build response metadata
    response_metadata = {
        "student_rating_before": student_rating,
        "selected_difficulty_range": f"{difficulty_min}-{difficulty_max}",
        "bank_items_used": len([i for i in items if i.get("source") == "bank"]),
        "ai_items_generated": len(
            [i for i in items if i.get("source") == "ai_generated"]
        ),
        "all_ai_generated": all_ai_generated,
    }

    if all_ai_generated:
        response_metadata["message"] = (
            f"No bank items available for {subject} at your current level. "
            f"AI-generated items have been created and flagged for tutor review."
        )

    return {
        "success": True,
        "data": {
            "assignment_id": str(assignment_id),
            "items": items,
            "adaptive_metadata": response_metadata,
        },
    }


@router.post("/complete")
async def complete_practice(
    assignment_id: str = Query(
        ..., description="Practice assignment ID (for compatibility)"
    ),
    item_id: str = Query(
        ..., description="Practice item ID (actual PracticeAssignment.id)"
    ),
    request: CompletePracticeRequest = ...,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Record completion of a practice item

    Updates student rating and calculates performance

    Note: item_id is the actual PracticeAssignment.id in the database.
    assignment_id is kept for API compatibility but item_id is used for lookup.
    """
    # Get assignment - use item_id as it's the actual PracticeAssignment.id
    assignment = (
        db.query(PracticeAssignment).filter(PracticeAssignment.id == item_id).first()
    )

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail=f"Practice assignment not found with item_id: {item_id}",
        )

    # Initialize adaptive service
    adaptive_service = AdaptivePracticeService(db)

    # Calculate performance score
    performance_score = adaptive_service.calculate_performance_score(
        correct=request.correct,
        time_taken_seconds=request.time_taken_seconds,
        hints_used=request.hints_used,
    )

    # Get question rating (convert difficulty to Elo scale)
    question_rating = (
        assignment.difficulty_level * 100 if assignment.difficulty_level else 1000
    )

    # Update student rating
    student_rating_before = (
        assignment.student_rating_before
        or adaptive_service.get_student_rating(
            str(assignment.student_id),
            str(assignment.subject_id) if assignment.subject_id else "",
        )
    )

    # Update Elo rating regardless of correctness
    # This allows ratings to decrease when students perform poorly
    if assignment.subject_id:
        student_rating_after = adaptive_service.update_student_rating(
            str(assignment.student_id),
            str(assignment.subject_id),
            question_rating,
            performance_score,
        )
    else:
        student_rating_after = student_rating_before

    # Store rating update in assignment (regardless of correctness)
    assignment.student_rating_after = student_rating_after
    assignment.performance_score = performance_score

    # Only mark as completed if answer is correct
    # This allows students to retry incorrect answers
    if request.correct:
        assignment.completed = True
        assignment.completed_at = datetime.now(timezone.utc)

        # Update goal progress based on this practice completion
        goal_progress_service = GoalProgressService(db)
        goal_progress_service.update_goal_progress_from_practice(
            student_id=str(assignment.student_id),
            goal_tags=assignment.goal_tags,
            subject_id=str(assignment.subject_id) if assignment.subject_id else None,
        )

    else:
        # Incorrect answer - don't mark as completed, but rating still updated
        # This allows ratings to decrease on poor performance
        pass

    db.commit()

    # Calculate next difficulty suggestion
    if assignment.subject_id:
        next_min, next_max = adaptive_service.select_difficulty_range(
            student_rating_after
        )
        next_difficulty = (next_min + next_max) // 2
    else:
        next_difficulty = assignment.difficulty_level or 5

    response_data = {
        "performance_score": float(performance_score),
        "student_rating_before": student_rating_before,
        "student_rating_after": student_rating_after,
        "next_difficulty_suggestion": next_difficulty,
    }

    # Gamification removed - no longer included in response

    return {"success": True, "data": response_data}


@router.post("/summary")
async def get_practice_summary(
    assignment_id: str = Query(..., description="Practice assignment ID"),
    student_id: str = Query(..., description="Student ID"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get summary of practice session and determine if tutor notification is needed

    Checks all completed questions in the assignment and calculates:
    - Total questions
    - Correct/incorrect count
    - Average attempts
    - Whether tutor help is needed
    """
    from sqlalchemy import func

    # Get all assignments for this assignment_id (all items in the session)
    # Note: assignment_id here refers to the session ID, not individual item IDs
    # We need to get all items that were assigned together
    # For now, we'll get all recent assignments for the student in the last hour
    # Get student's recent practice assignments (within last hour)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
    assignments = (
        db.query(PracticeAssignment)
        .filter(
            PracticeAssignment.student_id == student_id,
            PracticeAssignment.assigned_at >= cutoff_time,
        )
        .all()
    )

    if not assignments:
        raise HTTPException(status_code=404, detail="No practice assignments found")

    # Calculate summary
    total_questions = len(assignments)
    completed_assignments = [a for a in assignments if a.completed]
    correct_count = len(
        [
            a
            for a in completed_assignments
            if a.performance_score and float(a.performance_score) >= 0.5
        ]
    )
    incorrect_count = len(completed_assignments) - correct_count

    # Calculate average attempts (we'll estimate based on performance scores)
    # Lower performance scores might indicate more attempts
    total_performance = (
        sum(
            [
                float(a.performance_score)
                for a in completed_assignments
                if a.performance_score
            ]
        )
        or 0
    )
    avg_performance = (
        total_performance / len(completed_assignments) if completed_assignments else 0
    )

    # Estimate attempts: if performance is very low, likely multiple attempts
    # This is a heuristic - in production, you'd track actual attempts
    estimated_avg_attempts = (
        1.0 if avg_performance >= 0.7 else (2.0 if avg_performance >= 0.4 else 3.0)
    )

    # Determine if tutor notification is needed
    # Criteria: Less than 50% correct OR average attempts > 2
    accuracy = correct_count / total_questions if total_questions > 0 else 0
    needs_tutor_help = accuracy < 0.5 or estimated_avg_attempts > 2

    # Notify tutor if needed
    tutor_notified = False
    if needs_tutor_help:
        try:
            # Get student info
            student = db.query(User).filter(User.id == student_id).first()
            if student:
                # Find tutor (in production, this would be the student's assigned tutor)
                # For now, find any tutor user
                tutor = db.query(User).filter(User.role == "tutor").first()

                if tutor:
                    # Create a message thread or send notification
                    try:
                        from src.services.notifications.email import EmailService

                        email_service = EmailService(db)

                        email_service.send_email(
                            to_email=tutor.email,
                            subject=f"Student Needs Help: {student.email}",
                            body_html=f"""
                            <html>
                            <body>
                                <h2>Student Needs Additional Support</h2>
                                <p>A student has completed a practice session with the following results:</p>
                                <ul>
                                    <li>Total Questions: {total_questions}</li>
                                    <li>Correct: {correct_count}</li>
                                    <li>Incorrect: {incorrect_count}</li>
                                    <li>Accuracy: {(accuracy * 100):.1f}%</li>
                                    <li>Estimated Average Attempts: {estimated_avg_attempts:.1f}</li>
                                </ul>
                                <p>Please reach out to provide additional support.</p>
                            </body>
                            </html>
                            """,
                            body_text=f"""
                            Student Needs Additional Support
                            
                            A student has completed a practice session with the following results:
                            - Total Questions: {total_questions}
                            - Correct: {correct_count}
                            - Incorrect: {incorrect_count}
                            - Accuracy: {(accuracy * 100):.1f}%
                            - Estimated Average Attempts: {estimated_avg_attempts:.1f}
                            
                            Please reach out to provide additional support.
                            """,
                        )
                        tutor_notified = True
                        logger.info(f"Tutor notification sent for student {student_id}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to send tutor notification email: {str(e)}"
                        )
        except Exception as e:
            logger.warning(f"Failed to notify tutor: {str(e)}")

    return {
        "success": True,
        "data": {
            "total_questions": total_questions,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "completed_count": len(completed_assignments),
            "accuracy": round(accuracy * 100, 1),
            "average_attempts": round(estimated_avg_attempts, 1),
            "needs_tutor_help": needs_tutor_help,
            "tutor_notified": tutor_notified,
        },
    }
