"""
Tests for the self-contained auth service (Phase 2, task 2.1).
Covers password hashing (passlib/bcrypt) and JWT issuance/verification
(python-jose, HS256) that replace AWS Cognito.
"""

import time

import pytest
from jose import jwt as jose_jwt

from src.config.settings import settings
from src.services.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.services.auth.jwt import InvalidTokenError


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    """Give every test a non-empty secret unless it overrides it explicitly."""
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-key")
    monkeypatch.setattr(settings, "jwt_expiry_minutes", 1440)


def test_hash_and_verify_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_hash_is_salted():
    hashed1 = hash_password("same-password")
    hashed2 = hash_password("same-password")
    assert hashed1 != hashed2
    assert verify_password("same-password", hashed1) is True
    assert verify_password("same-password", hashed2) is True


def test_create_and_decode_roundtrip_preserves_claims():
    token = create_access_token(sub="user-123", email="a@example.com", role="student")
    payload = decode_token(token)

    assert payload["sub"] == "user-123"
    assert payload["email"] == "a@example.com"
    assert payload["role"] == "student"
    assert "exp" in payload
    assert "iat" in payload


def test_expired_token_raises():
    token = create_access_token(
        sub="user-123", email="a@example.com", role="student", expires_minutes=-1
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_tampered_token_raises():
    token = create_access_token(sub="user-123", email="a@example.com", role="student")
    header, payload, signature = token.split(".")
    flipped_char = "A" if signature[0] != "A" else "B"
    tampered_signature = flipped_char + signature[1:]
    tampered = f"{header}.{payload}.{tampered_signature}"
    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_wrong_secret_token_raises():
    other_token = jose_jwt.encode(
        {"sub": "user-123", "email": "a@example.com", "role": "student"},
        "a-completely-different-secret",
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_token(other_token)


def test_empty_jwt_secret_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "")
    with pytest.raises(RuntimeError):
        create_access_token(sub="user-123", email="a@example.com", role="student")


def test_default_expiry_minutes_used_when_not_specified():
    monkeypatch_expiry = 1440
    token = create_access_token(sub="user-123", email="a@example.com", role="student")
    payload = decode_token(token)
    assert payload["exp"] - payload["iat"] == monkeypatch_expiry * 60
