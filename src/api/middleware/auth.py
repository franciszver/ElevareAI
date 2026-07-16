"""
Authentication Middleware
AWS Cognito JWT token validation
"""

import json
from functools import lru_cache
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode
from sqlalchemy.orm import Session as DBSession

from src.config.database import get_db
from src.config.settings import settings

security = HTTPBearer()


@lru_cache()
def get_cognito_public_keys():
    """Get Cognito public keys for JWT verification"""
    try:
        # Cognito JWKS endpoint
        jwks_url = f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/{settings.cognito_user_pool_id}/.well-known/jwks.json"

        # Fetch JWKS
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch Cognito public keys: {str(e)}"
        )


def verify_token(token: str) -> dict:
    """Verify and decode JWT token from Cognito"""
    try:
        # Get token header to find the key
        unverified_header = jwt.get_unverified_header(token)

        # Get public keys
        jwks = get_cognito_public_keys()

        # Find the matching key
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=401, detail="Unable to find appropriate key"
            )

        # Verify and decode token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/{settings.cognito_user_pool_id}",
        )

        return payload

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=401, detail=f"Token verification failed: {str(e)}"
        )


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
