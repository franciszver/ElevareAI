"""
Progress Dashboard Handler
GET /progress/:user_id - Get multi-goal progress dashboard
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from src.api.middleware.auth import get_current_user
from src.config.database import get_db
from src.config.settings import settings
from src.models.goal import Goal
from src.models.practice import StudentRating
from src.models.user import User
from src.utils.user_creation import ensure_user_exists

logger = logging.getLogger(__name__)


def _get_related_subjects(
    subject_name: str, goal_type: Optional[str] = None
) -> List[str]:
    """Get related subject suggestions based on completed goal"""
    subject_lower = subject_name.lower()

    # SAT-specific suggestions (when goal_type is SAT and goal is completed)
    if goal_type and goal_type.upper() == "SAT":
        if "math" in subject_lower:
            return ["College Essays", "Study Skills", "AP Prep"]
        elif "english" in subject_lower or "essay" in subject_lower:
            return ["SAT Math", "AP English Literature", "AP Language"]
        else:
            # General SAT completion
            return ["College Essays", "Study Skills", "AP Prep"]

    # Subject-based suggestions
    if any(kw in subject_lower for kw in ["sat", "test prep"]):
        if "math" in subject_lower:
            return ["College Essays", "Study Skills", "AP Prep"]
        elif "english" in subject_lower or "essay" in subject_lower:
            return ["SAT Math", "AP English Literature", "AP Language"]
        else:
            return ["College Essays", "Study Skills", "AP Prep"]

    elif "algebra" in subject_lower:
        return ["Geometry", "Pre-Calculus", "AP Calculus"]
    elif "geometry" in subject_lower:
        return ["Algebra 2", "Trigonometry", "AP Calculus"]
    elif "calculus" in subject_lower:
        return ["AP Statistics", "Physics", "Advanced Math"]

    elif "chemistry" in subject_lower:
        # Enhanced Chemistry suggestions
        return ["Physics", "Biology", "AP Chemistry", "STEM Prep"]
    elif "physics" in subject_lower:
        return ["Chemistry", "AP Physics", "Calculus"]
    elif "biology" in subject_lower:
        return ["Chemistry", "AP Biology", "Environmental Science"]

    elif "ap" in subject_lower:
        if "math" in subject_lower:
            return ["AP Statistics", "AP Physics", "Calculus BC"]
        elif (
            "science" in subject_lower
            or "chemistry" in subject_lower
            or "physics" in subject_lower
        ):
            return ["AP Math", "AP Biology", "AP Environmental Science"]
        else:
            return ["AP Math", "AP Science", "Test Prep"]

    elif "basic math" in subject_lower or (
        "math" in subject_lower and "basic" in subject_lower
    ):
        # Basic Math → Algebra is the natural next step
        return ["Algebra", "Geometry", "Pre-Calculus"]
    elif "math" in subject_lower and not any(
        kw in subject_lower
        for kw in [
            "algebra",
            "geometry",
            "calculus",
            "trig",
            "statistics",
            "pre-calc",
            "precalc",
        ]
    ):
        # General math (not specific) → suggest foundational next steps
        return ["Algebra", "Geometry", "Pre-Calculus"]

    # Default suggestions - provide more helpful defaults
    return ["Algebra", "Geometry"]  # Better default than placeholder text


router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/{user_id}")
async def get_progress(
    user_id: UUID,
    include_suggestions: bool = Query(
        True, description="Include related subject suggestions"
    ),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get multi-goal progress dashboard data

    Called by React frontend on login
    """
    # Production: Verify user has access via database lookup
    user_sub = current_user.get("sub")
    # Try multiple ways to get email from Cognito token
    user_email = current_user.get("email") or current_user.get("cognito:username") or ""
    # Only use email if it looks like an email address
    if user_email and "@" not in user_email:
        user_email = ""

    # Ensure user exists in database (auto-create on first login)
    db_user = ensure_user_exists(db, user_sub, user_email, role="student")

    # The user_id in the URL might be the Cognito sub or the database UUID
    # If it's the Cognito sub, use the database user's ID instead
    # If it's already the database UUID, verify it matches
    if str(user_id) == user_sub:
        # Frontend sent Cognito sub instead of database UUID - use database user ID
        user_id = db_user.id
    elif db_user.id != user_id:
        # Frontend sent a different UUID - verify it matches the authenticated user
        raise HTTPException(status_code=403, detail="Access denied")

    # Get user's goals (active and recently completed)
    active_goals = (
        db.query(Goal).filter(Goal.student_id == user_id, Goal.status == "active").all()
    )

    # Get recently completed goals (last 30 days) for suggestions
    from datetime import datetime, timedelta, timezone

    # Use timezone-aware datetime for comparison
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
    recent_completed = (
        db.query(Goal)
        .filter(
            Goal.student_id == user_id,
            Goal.status == "completed",
            Goal.completed_at.isnot(None),
            Goal.completed_at >= cutoff_date,
        )
        .all()
    )

    # Check if first login (disclaimer not shown)
    disclaimer_required = not db_user.disclaimer_shown

    # Handle no goals scenario (only if no active AND no completed goals)
    if not active_goals and not recent_completed:
        return {
            "success": True,
            "data": {
                "user_id": str(user_id),
                "goals": [],
                "insights": [],
                "suggestions": [
                    {
                        "type": "onboarding",
                        "message": "You don't have any active goals yet. Set up your first learning goal to get started!",
                        "action": "create_goal",
                        "suggested_subjects": [
                            "SAT Math",
                            "AP Chemistry",
                            "Algebra",
                            "Geometry",
                        ],
                    }
                ]
                if include_suggestions
                else [],
                "disclaimer_required": disclaimer_required,
                "disclaimer": {
                    "message": "Important Notice: This AI Study Companion is designed to support your learning between tutoring sessions. While I can help with practice problems, explanations, and study guidance, I'm not a replacement for your tutor. For complex topics or when you see a 'Low Confidence' label, please consult with your tutor.",
                    "acknowledgment_required": True,
                }
                if disclaimer_required
                else None,
                "empty_state": True,
            },
        }

    # Build insights
    insights = []
    if active_goals:
        avg_completion = sum(g.completion_percentage for g in active_goals) / len(
            active_goals
        )
        if avg_completion > 70:
            insights.append("You're making great progress! Keep up the excellent work!")
        elif avg_completion < 40:
            insights.append(
                "Consider scheduling extra practice sessions to boost your progress"
            )
        elif avg_completion >= 40 and avg_completion <= 70:
            insights.append(
                "You're on track! Consistent practice will help you reach your goals"
            )

    # Build suggestions if requested
    suggestions = []
    if include_suggestions:
        # Suggest related subjects for completed goals
        if recent_completed:
            for goal in recent_completed:
                if goal.subject:
                    # Generate related subject suggestions based on completed goal
                    related = _get_related_subjects(goal.subject.name, goal.goal_type)
                    if related:
                        suggestions.append(
                            {
                                "type": "related_subject",
                                "triggered_by": {
                                    "goal_id": str(goal.id),
                                    "goal_name": goal.title,
                                    "subject": goal.subject.name,
                                },
                                "subjects": related,
                                "message": f"Great job completing {goal.title}! Based on your success, you might enjoy:",
                            }
                        )

        # Suggest cross-subject exploration if student has multiple goals in one area
        math_goals = [
            g
            for g in active_goals
            if g.subject
            and any(
                kw in g.subject.name.lower()
                for kw in ["math", "algebra", "geometry", "calculus"]
            )
        ]
        science_goals = [
            g
            for g in active_goals
            if g.subject
            and any(
                kw in g.subject.name.lower()
                for kw in ["science", "chemistry", "physics", "biology"]
            )
        ]

        if len(math_goals) >= 2 and not any(
            g.subject and "science" in g.subject.name.lower() for g in active_goals
        ):
            suggestions.append(
                {
                    "type": "cross_subject",
                    "message": "You're doing great with math! Consider exploring science subjects too.",
                    "subjects": ["Chemistry", "Physics", "Biology"],
                }
            )
        elif len(science_goals) >= 2 and not any(
            g.subject and "math" in g.subject.name.lower() for g in active_goals
        ):
            suggestions.append(
                {
                    "type": "cross_subject",
                    "message": "You're excelling in science! Math skills can complement your studies.",
                    "subjects": ["Algebra", "Geometry", "Calculus"],
                }
            )

    # Combine active and recently completed goals for display
    all_goals_for_display = active_goals + recent_completed

    # Get Elo ratings for each goal's subject
    goals_with_ratings = []
    for g in all_goals_for_display:
        goal_data = {
            "goal_id": str(g.id),
            "subject": g.subject.name if g.subject else "Unknown",
            "goal_type": g.goal_type,
            "title": g.title,
            "completion_percentage": float(g.completion_percentage),
            "current_streak": g.current_streak,
            "xp_earned": g.xp_earned,
            "status": g.status,
            "target_date": str(g.target_completion_date)
            if g.target_completion_date
            else None,
            "completed_at": str(g.completed_at) if g.completed_at else None,
        }

        # Get Elo rating for this goal's subject
        if g.subject_id:
            rating = (
                db.query(StudentRating)
                .filter(
                    StudentRating.student_id == user_id,
                    StudentRating.subject_id == g.subject_id,
                )
                .first()
            )

            if rating:
                goal_data["elo_rating"] = rating.rating
                goal_data["elo_rating_updated"] = (
                    str(rating.last_updated) if rating.last_updated else None
                )
            else:
                # No rating yet - use default
                goal_data["elo_rating"] = settings.elo_default_rating
                goal_data["elo_rating_updated"] = None
        else:
            goal_data["elo_rating"] = None
            goal_data["elo_rating_updated"] = None

        goals_with_ratings.append(goal_data)

    return {
        "success": True,
        "data": {
            "user_id": str(user_id),
            "goals": goals_with_ratings,
            "insights": insights,
            "suggestions": suggestions,
            "disclaimer_required": disclaimer_required,
            "disclaimer": {
                "message": "Important Notice: This AI Study Companion is designed to support your learning between tutoring sessions. While I can help with practice problems, explanations, and study guidance, I'm not a replacement for your tutor. For complex topics or when you see a 'Low Confidence' label, please consult with your tutor.",
                "acknowledgment_required": True,
            }
            if disclaimer_required
            else None,
            "stats": {
                "total_goals": len(active_goals),
                "completed_goals": len(recent_completed),
                "average_completion": float(
                    sum(g.completion_percentage for g in active_goals)
                    / len(active_goals)
                )
                if active_goals
                else 0.0,
            },
        },
    }
