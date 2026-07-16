"""
JWT Issuance and Verification
HS256 access tokens signed with a local secret, replacing Cognito-issued
tokens.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from src.config.settings import settings

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when a token is expired, tampered with, or otherwise invalid."""


def create_access_token(
    sub: str, email: str, role: str, expires_minutes: Optional[int] = None
) -> str:
    """Create a signed JWT access token carrying sub, email, and role claims."""
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET not configured")

    minutes = (
        expires_minutes if expires_minutes is not None else settings.jwt_expiry_minutes
    )
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=minutes)

    claims = {
        "sub": sub,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT access token, raising InvalidTokenError on failure."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")
