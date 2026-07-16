"""
Authentication Middleware
Local JWT token validation
"""

from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DBSession

from src.config.database import get_db
from src.services.auth import InvalidTokenError, decode_token

security = HTTPBearer()


def verify_token(token: str) -> dict:
    """Verify and decode a locally-issued JWT token"""
    try:
        return decode_token(token)
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=str(e))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """
    Get current authenticated user from JWT token

    Returns:
        dict: Token payload with user information (sub, email, etc.)
    """
    token = credentials.credentials

    # Support mock tokens for demo accounts (allow in both dev and production for demo purposes)
    if token.startswith("mock-token-"):
        # Return a mock payload that will work with demo accounts
        # The endpoints will handle looking up by user_id from the URL/request
        return {
            "sub": "demo-user",
            "email": "demo@demo.com",
            "role": "student",
            "cognito:groups": ["students"],
        }

    payload = verify_token(token)

    # Ensure email is extracted properly - Cognito tokens may have email in different places
    if not payload.get("email"):
        # Try alternative email sources
        email = payload.get("cognito:username") or payload.get("email_verified") or ""
        # If cognito:username looks like an email, use it
        if "@" in str(email):
            payload["email"] = email
        # Otherwise, email will be empty and ensure_user_exists will handle it

    return payload


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[dict]:
    """
    Get current user if token is provided, otherwise return None
    Useful for endpoints that work with or without authentication
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials

        # Support mock tokens for demo accounts (allow in both dev and production for demo purposes)
        if token.startswith("mock-token-"):
            return {
                "sub": "demo-user",
                "email": "demo@demo.com",
                "role": "student",
                "cognito:groups": ["students"],
            }

        payload = verify_token(token)
        return payload
    except HTTPException:
        return None


def require_role(allowed_roles: list[str]):
    """
    Dependency factory to require specific user roles

    Usage:
        @app.get("/admin")
        def admin_route(user: dict = Depends(require_role(["admin"]))):
            ...
    """

    async def role_checker(
        user: dict = Depends(get_current_user), db: DBSession = Depends(get_db)
    ) -> dict:
        from src.models.user import User

        # Extract role from token (may be in 'cognito:groups' or custom claim)
        user_groups = user.get("cognito:groups", [])
        token_role = user.get("role") or (user_groups[0] if user_groups else None)

        # For demo accounts, use token role
        if user.get("sub") == "demo-user":
            user_role = token_role or "student"
        else:
            # For real users, check database role (more reliable)
            user_sub = user.get("sub")
            db_user = db.query(User).filter(User.cognito_sub == user_sub).first()
            if db_user:
                user_role = db_user.role
            else:
                # Fallback to token role if user not in database yet
                user_role = token_role

        if not user_role or user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {allowed_roles}",
            )

        return user

    return role_checker
