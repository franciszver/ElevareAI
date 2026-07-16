"""
User Creation Utilities
Automatically create user records for Cognito users on first login
"""

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from src.models.user import User

logger = logging.getLogger(__name__)


def ensure_user_exists(
    db: Session, cognito_sub: str, email: str, role: str = "student"
) -> User:
    """
    Ensure a user exists in the database, creating if necessary.

    This is called when a Cognito user first authenticates.

    Args:
        db: Database session
        cognito_sub: Cognito subject (sub) from JWT token
        email: User email from JWT token (may be empty)
        role: User role (default: "student")

    Returns:
        User: The user record (existing or newly created)
    """
    # Check if user already exists by cognito_sub
    user = db.query(User).filter(User.cognito_sub == cognito_sub).first()

    if user:
        # User exists, update email if it changed and new email is not empty
        if email and user.email != email:
            logger.info(f"Updating email for user {user.id}: {user.email} -> {email}")
            user.email = email
            db.commit()
        return user

    # User doesn't exist, create it
    # Handle empty email: use a placeholder that includes cognito_sub to ensure uniqueness
    if not email or email.strip() == "":
        # Generate a unique placeholder email using cognito_sub
        email = f"user_{cognito_sub[:8]}@cognito.local"
        logger.warning(
            f"Email not provided in token for cognito_sub {cognito_sub}, using placeholder: {email}"
        )

    # Check if a user with this email already exists (shouldn't happen, but handle gracefully)
    existing_email_user = db.query(User).filter(User.email == email).first()
    if existing_email_user:
        # If email matches but cognito_sub doesn't, update the existing user's cognito_sub
        if existing_email_user.cognito_sub != cognito_sub:
            logger.warning(
                f"User with email {email} exists but different cognito_sub. Updating cognito_sub."
            )
            existing_email_user.cognito_sub = cognito_sub
            db.commit()
            return existing_email_user
        # If both match, return existing user (shouldn't happen since we checked cognito_sub above)
        return existing_email_user

    logger.info(f"Creating new user for Cognito sub: {cognito_sub}, email: {email}")

    # Initialize with proper defaults for better UX
    user = User(
        id=uuid4(),
        cognito_sub=cognito_sub,
        email=email,
        role=role,
        profile={
            "name": email.split("@")[0] if email and "@" in email else "Student",
            "preferences": {"nudge_frequency_cap": 2, "learning_style": "mixed"},
        },
        gamification={"xp": 0, "level": 1, "badges": [], "streaks": 0},
        analytics={
            "total_sessions": 0,
            "total_practice_items": 0,
            "total_qa_interactions": 0,
            "override_count": 0,
        },
        disclaimer_shown=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        f"Created user {user.id} for email {email} with initialized profile and gamification"
    )
    return user
