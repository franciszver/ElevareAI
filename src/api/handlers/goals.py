"""
Goals Handler
GET /goals - List goals for a student
POST /goals - Create a new goal
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import joinedload

from src.api.middleware.auth import get_current_user, get_current_user_optional
from src.config.database import get_db
from src.config.settings import settings
from src.models.goal import Goal
from src.models.practice import PracticeAssignment, StudentRating
from src.models.qa import QAInteraction
from src.models.subject import Subject
from src.models.user import User
from src.services.practice.adaptive import AdaptivePracticeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/goals", tags=["goals"])


class CreateGoalRequest(BaseModel):
    student_id: str
    title: str
    description: Optional[str] = None
    goal_type: Optional[str] = "Standard"
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None  # Alternative: find subject by name
    target_completion_date: Optional[str] = None


@router.get("/", include_in_schema=False)
@router.get("")
async def get_goals(
    student_id: str = Query(..., description="Student ID"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get all goals for a student
    """
    # Convert student_id string to UUID
    try:
        student_uuid = UUID(student_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid student_id format")

    # Development mode: Support mock tokens
    if (
        settings.environment == "development"
        and current_user
        and current_user.get("sub") == "demo-user"
    ):
        # Verify user exists
        db_user = db.query(User).filter(User.id == student_uuid).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        # Production: Verify user has access
        if current_user:
            user_sub = current_user.get("sub")
            db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify the student_id matches the authenticated user
            if db_user.id != student_uuid:
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            # No auth - allow in development
            if settings.environment != "development":
                raise HTTPException(status_code=401, detail="Authentication required")
            db_user = db.query(User).filter(User.id == student_uuid).first()
            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

    # Eager load subject relationship to avoid lazy loading issues
    goals = (
        db.query(Goal)
        .options(joinedload(Goal.subject))
        .filter(Goal.student_id == student_uuid)
        .order_by(Goal.created_at.desc())
        .all()
    )

    # Get Elo ratings for each goal's subject
    goals_with_ratings = []
    for g in goals:
        try:
            # Helper to safely format datetime
            def format_datetime(dt):
                if dt is None:
                    return None
                if hasattr(dt, "isoformat"):
                    return dt.isoformat()
                return str(dt)

            goal_data = {
                "id": str(g.id),
                "title": g.title,
                "description": g.description,
                "goal_type": g.goal_type,
                "subject_id": str(g.subject_id) if g.subject_id else None,
                "subject": g.subject.name
                if (g.subject and hasattr(g.subject, "name"))
                else None,
                "status": g.status,
                "completion_percentage": float(g.completion_percentage)
                if g.completion_percentage is not None
                else 0.0,
                "target_completion_date": format_datetime(g.target_completion_date),
                "completed_at": format_datetime(g.completed_at),
                "current_streak": g.current_streak or 0,
                "xp_earned": g.xp_earned or 0,
                "created_at": format_datetime(g.created_at),
            }

            # Get Elo rating for this goal's subject
            if g.subject_id:
                rating = (
                    db.query(StudentRating)
                    .filter(
                        StudentRating.student_id == student_uuid,
                        StudentRating.subject_id == g.subject_id,
                    )
                    .first()
                )

                if rating:
                    goal_data["elo_rating"] = (
                        float(rating.rating)
                        if rating.rating is not None
                        else settings.elo_default_rating
                    )
                    goal_data["elo_rating_updated"] = format_datetime(
                        rating.last_updated
                    )
                else:
                    # No rating yet - use default
                    goal_data["elo_rating"] = settings.elo_default_rating
                    goal_data["elo_rating_updated"] = None
            else:
                goal_data["elo_rating"] = None
                goal_data["elo_rating_updated"] = None

            # Get question count for this goal (for daily cap display)
            # Count only questions from today (UTC)
            # Note: goal_id column may not exist if migration hasn't been run
            # Use a savepoint to isolate errors so they don't abort the entire transaction
            question_count = 0
            savepoint = db.begin_nested()  # Create a savepoint
            try:
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                question_count = (
                    db.query(QAInteraction)
                    .filter(
                        QAInteraction.student_id == student_uuid,
                        QAInteraction.goal_id == g.id,
                        QAInteraction.created_at >= today_start,
                    )
                    .count()
                )
                savepoint.commit()  # Commit the savepoint if successful
            except Exception as qa_error:
                savepoint.rollback()  # Rollback only the savepoint, not the entire transaction
                # If goal_id column doesn't exist, just set to 0
                error_str = str(qa_error).lower()
                if "goal_id" in error_str and (
                    "does not exist" in error_str or "undefinedcolumn" in error_str
                ):
                    logger.debug(
                        f"goal_id column doesn't exist, skipping question count for goal {g.id}"
                    )
                else:
                    logger.warning(
                        f"Could not query QAInteraction for goal {g.id}: {str(qa_error)}"
                    )
                question_count = 0
            goal_data["question_count"] = question_count
            goal_data["question_limit"] = 20

            goals_with_ratings.append(goal_data)
        except Exception as e:
            logger.error(f"Error processing goal {g.id}: {str(e)}", exc_info=True)
            # Skip this goal but continue with others
            continue

    return {"success": True, "data": goals_with_ratings}


@router.post("/", include_in_schema=False)
@router.post("")
async def create_goal(
    request: CreateGoalRequest,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Create a new goal
    """
    # Development mode: Support mock tokens
    if (
        settings.environment == "development"
        and current_user
        and current_user.get("sub") == "demo-user"
    ):
        db_user = db.query(User).filter(User.id == request.student_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        creator_id = db_user.id
    else:
        # Production: Verify user has access
        if current_user:
            user_sub = current_user.get("sub")
            db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify the student_id matches the authenticated user
            if db_user.id != UUID(request.student_id):
                raise HTTPException(status_code=403, detail="Access denied")

            creator_id = db_user.id
        else:
            # No auth - allow in development
            if settings.environment != "development":
                raise HTTPException(status_code=401, detail="Authentication required")
            db_user = db.query(User).filter(User.id == request.student_id).first()
            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")
            creator_id = db_user.id

    # Find subject if subject_name is provided, or create it if it doesn't exist
    subject_id = None
    if request.subject_id:
        subject_id = UUID(request.subject_id)
    elif request.subject_name:
        subject = db.query(Subject).filter(Subject.name == request.subject_name).first()
        if subject:
            subject_id = subject.id
        else:
            # Auto-create subject if it doesn't exist
            # Use try-except to handle race conditions (if subject is created between query and insert)
            try:
                logger.info(
                    f"Subject not found: {request.subject_name}, creating new subject"
                )
                new_subject = Subject(
                    id=uuid.uuid4(),
                    name=request.subject_name,
                    category=None,  # Can be set later
                    description=None,
                )
                db.add(new_subject)
                db.flush()  # Flush to get the ID without committing
                subject_id = new_subject.id
                logger.info(
                    f"Created new subject: {request.subject_name} with ID {subject_id}"
                )
            except Exception as e:
                # If subject creation fails (e.g., unique constraint violation from race condition),
                # try to fetch it again
                logger.warning(
                    f"Failed to create subject {request.subject_name}, retrying query: {str(e)}"
                )
                db.rollback()  # Rollback the failed insert
                subject = (
                    db.query(Subject)
                    .filter(Subject.name == request.subject_name)
                    .first()
                )
                if subject:
                    subject_id = subject.id
                    logger.info(
                        f"Found subject after retry: {request.subject_name} with ID {subject_id}"
                    )
                else:
                    # If still not found, log error but continue without subject
                    logger.error(
                        f"Could not create or find subject: {request.subject_name}, creating goal without subject"
                    )
                    subject_id = None

    # Parse target date if provided
    target_date = None
    if request.target_completion_date:
        try:
            target_date = datetime.fromisoformat(
                request.target_completion_date.replace("Z", "+00:00")
            ).date()
        except Exception as e:
            logger.warning(
                f"Invalid target_completion_date: {request.target_completion_date}, {e}"
            )

    # Create goal
    goal = Goal(
        id=uuid.uuid4(),
        student_id=UUID(request.student_id),
        created_by=creator_id,
        subject_id=subject_id,
        goal_type=request.goal_type or "Standard",
        title=request.title,
        description=request.description,
        target_completion_date=target_date,
        status="active",
        completion_percentage=0.00,
        current_streak=0,
        xp_earned=0,
    )

    db.add(goal)
    db.commit()
    db.refresh(goal)

    return {
        "success": True,
        "data": {
            "id": str(goal.id),
            "title": goal.title,
            "description": goal.description,
            "goal_type": goal.goal_type,
            "subject_id": str(goal.subject_id) if goal.subject_id else None,
            "subject": goal.subject.name if goal.subject else None,
            "status": goal.status,
            "completion_percentage": float(goal.completion_percentage),
            "target_completion_date": goal.target_completion_date.isoformat()
            if goal.target_completion_date
            else None,
            "created_at": goal.created_at.isoformat() if goal.created_at else None,
        },
    }


@router.post("/{goal_id}/reset")
async def reset_goal(
    goal_id: UUID,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Reset a completed goal back to active status

    This allows students to retry goals if they completed with a low Elo rating.
    Resets:
    - Status: completed -> active
    - completion_percentage: back to 0.00
    - completed_at: cleared
    """
    # Get the goal
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Verify user has access
    if (
        settings.environment == "development"
        and current_user
        and current_user.get("sub") == "demo-user"
    ):
        # In development mode with mock auth, allow reset
        pass
    else:
        # Production: Verify user has access
        if current_user:
            user_sub = current_user.get("sub")
            db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify the goal belongs to the authenticated user
            if db_user.id != goal.student_id:
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            # No auth - allow in development
            if settings.environment != "development":
                raise HTTPException(status_code=401, detail="Authentication required")

    # Only allow resetting completed goals
    if goal.status != "completed":
        raise HTTPException(status_code=400, detail="Can only reset completed goals")

    # Reset the goal
    goal.status = "active"
    goal.completion_percentage = 0.00
    goal.completed_at = None

    # Reset Elo rating for this goal's subject
    elo_reset = False
    if goal.subject_id:
        rating = (
            db.query(StudentRating)
            .filter(
                StudentRating.student_id == goal.student_id,
                StudentRating.subject_id == goal.subject_id,
            )
            .first()
        )

        if rating:
            # Reset to default rating
            old_rating = rating.rating
            rating.rating = settings.elo_default_rating
            elo_reset = True
            logger.info(
                f"Reset Elo rating for goal {goal_id}: "
                f"student {goal.student_id}, subject {goal.subject_id}: "
                f"{old_rating} -> {settings.elo_default_rating}"
            )
        else:
            # No rating exists yet, create one with default
            rating = StudentRating(
                student_id=goal.student_id,
                subject_id=goal.subject_id,
                rating=settings.elo_default_rating,
            )
            db.add(rating)
            elo_reset = True
            logger.info(
                f"Created default Elo rating for goal {goal_id}: "
                f"student {goal.student_id}, subject {goal.subject_id}: "
                f"{settings.elo_default_rating}"
            )

    try:
        db.commit()
        db.refresh(goal)

        logger.info(
            f"Reset goal {goal_id} from completed to active"
            + (", Elo rating reset" if elo_reset else "")
        )

        return {
            "success": True,
            "data": {
                "id": str(goal.id),
                "title": goal.title,
                "status": goal.status,
                "completion_percentage": float(goal.completion_percentage),
                "completed_at": None,
                "elo_reset": elo_reset,
                "new_elo_rating": settings.elo_default_rating if elo_reset else None,
            },
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to reset goal {goal_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset goal: {str(e)}")


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: UUID,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Delete a goal and remove all related progress data

    This will:
    - Delete the goal
    - Remove goal ID from practice assignments' goal_tags arrays
    - Delete practice assignments that only have this goal tag (if any)
    """
    # Get the goal
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Verify user has access
    if (
        settings.environment == "development"
        and current_user
        and current_user.get("sub") == "demo-user"
    ):
        # In development mode with mock auth, allow deletion (frontend will handle user verification)
        pass
    else:
        # Production: Verify user has access
        if current_user:
            user_sub = current_user.get("sub")
            db_user = db.query(User).filter(User.cognito_sub == user_sub).first()

            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify the goal belongs to the authenticated user
            if db_user.id != goal.student_id:
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            # No auth - allow in development
            if settings.environment != "development":
                raise HTTPException(status_code=401, detail="Authentication required")

    goal_id_str = str(goal_id)

    # Find all practice assignments that reference this goal
    # Get all assignments for the student and filter in Python (more reliable than SQL array operators)
    all_assignments = (
        db.query(PracticeAssignment)
        .filter(PracticeAssignment.student_id == goal.student_id)
        .all()
    )

    practice_assignments = [
        a for a in all_assignments if a.goal_tags and goal_id_str in a.goal_tags
    ]

    # Remove goal ID from practice assignments' goal_tags arrays
    # If a practice assignment only has this goal tag, delete it
    deleted_assignments = 0
    updated_assignments = 0

    for assignment in practice_assignments:
        if assignment.goal_tags:
            # Remove this goal ID from the array
            updated_tags = [tag for tag in assignment.goal_tags if tag != goal_id_str]

            if len(updated_tags) == 0:
                # No other goal tags, delete the assignment
                db.delete(assignment)
                deleted_assignments += 1
            else:
                # Update with remaining tags
                assignment.goal_tags = updated_tags
                updated_assignments += 1

    # Delete the goal itself
    db.delete(goal)

    try:
        db.commit()
        logger.info(
            f"Deleted goal {goal_id_str}, removed {deleted_assignments} practice assignments, updated {updated_assignments} assignments"
        )

        return {
            "success": True,
            "data": {
                "goal_id": goal_id_str,
                "deleted": True,
                "practice_assignments_deleted": deleted_assignments,
                "practice_assignments_updated": updated_assignments,
            },
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete goal {goal_id_str}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete goal: {str(e)}")
