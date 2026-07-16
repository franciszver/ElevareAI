"""
Authentication Handler
Endpoints for user authentication and user info
"""

import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from src.api.middleware.auth import get_current_user
from src.config.database import get_db
from src.models.user import User
from src.services.auth import create_access_token, hash_password, verify_password
from src.utils.user_creation import ensure_user_exists

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ALLOWED_REGISTER_ROLES = {"student", "tutor", "parent"}
_LOGIN_FAILED_MESSAGE = "Invalid email or password"


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    name: str | None = None
    role: str = "student"

    @validator("email")
    def validate_email(cls, v):
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email format")
        return v

    @validator("role")
    def validate_role(cls, v):
        if v not in _ALLOWED_REGISTER_ROLES:
            raise ValueError(f"role must be one of {sorted(_ALLOWED_REGISTER_ROLES)}")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with an email/password."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        cognito_sub=str(uuid4()),
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"user_id": str(user.id), "email": user.email, "role": user.role}


@router.post("/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user with email/password and issue an access token."""
    user = db.query(User).filter(User.email == payload.email).first()
    if (
        not user
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail=_LOGIN_FAILED_MESSAGE)

    access_token = create_access_token(
        sub=user.cognito_sub, email=user.email, role=user.role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role,
    }


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
