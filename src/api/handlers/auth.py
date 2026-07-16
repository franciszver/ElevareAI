"""
Authentication Handler
Endpoints for user authentication and user info
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.middleware.auth import get_current_user
from src.config.database import get_db
from src.models.user import User
from src.utils.user_creation import ensure_user_exists

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get current user's database record

    This endpoint ensures the user exists in the database and returns their info.
    Called by frontend after Cognito login to get the database user_id.
    """
    # Support mock auth tokens for demo accounts
    if current_user.get("sub") == "demo-user":
        raise HTTPException(
            status_code=400, detail="This endpoint is not available for demo accounts"
        )

    # Production: Get or create user in database
    user_sub = current_user.get("sub")
    # Try multiple ways to get email from Cognito token
    user_email = current_user.get("email") or current_user.get("cognito:username") or ""
    # Only use email if it looks like an email address
    if user_email and "@" not in user_email:
        user_email = ""

    # Ensure user exists (creates if doesn't exist)
    db_user = ensure_user_exists(db, user_sub, user_email, role="student")

    return {
        "success": True,
        "data": {
            "id": str(db_user.id),
            "email": db_user.email,
            "role": db_user.role,
            "cognito_sub": db_user.cognito_sub,
            "profile": db_user.profile or {},
            "disclaimer_shown": db_user.disclaimer_shown,
        },
    }
