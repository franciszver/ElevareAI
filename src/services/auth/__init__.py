"""
Auth Service
Self-contained password hashing and JWT issuance/verification, replacing
AWS Cognito.
"""

from src.services.auth.jwt import InvalidTokenError, create_access_token, decode_token
from src.services.auth.password import hash_password, verify_password

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "InvalidTokenError",
]
