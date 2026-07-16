"""
Tests for POST /auth/register and POST /auth/login (Phase 2, task 2.3).
"""

import uuid

import pytest

from src.services.auth import decode_token
from tests.test_models import TestUser


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    """All register/login flows require a JWT secret to issue tokens."""
    monkeypatch.setattr("src.config.settings.settings.jwt_secret", "test-secret")


def _create_user(db_session, email, password_hash=None, role="student"):
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub=str(uuid.uuid4()),
        email=email,
        role=role,
        password_hash=password_hash,
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestRegister:
    def test_register_happy_path(self, client, db_session):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@example.com", "password": "password123"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@example.com"
        assert body["role"] == "student"
        assert "user_id" in body

        stored = db_session.query(TestUser).filter_by(email="newuser@example.com").one()
        assert stored.password_hash is not None
        assert stored.password_hash != "password123"

        # Registered users should get the same enriched defaults that
        # ensure_user_exists gives Cognito-created users, not a bare row.
        assert stored.profile
        assert stored.gamification == {
            "xp": 0,
            "level": 1,
            "badges": [],
            "streaks": 0,
        }
        assert stored.analytics == {
            "total_sessions": 0,
            "total_practice_items": 0,
            "total_qa_interactions": 0,
            "override_count": 0,
        }

    def test_register_stores_name_in_profile_when_provided(self, client, db_session):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "named@example.com",
                "password": "password123",
                "name": "Ada Lovelace",
            },
        )
        assert resp.status_code == 201

        stored = db_session.query(TestUser).filter_by(email="named@example.com").one()
        assert stored.profile["name"] == "Ada Lovelace"

    def test_register_without_name_does_not_crash(self, client, db_session):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "noname@example.com", "password": "password123"},
        )
        assert resp.status_code == 201

        stored = db_session.query(TestUser).filter_by(email="noname@example.com").one()
        assert stored.profile

    def test_register_duplicate_email_returns_409(self, client, db_session):
        _create_user(db_session, "dupe@example.com", password_hash="somehash")

        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "dupe@example.com", "password": "password123"},
        )
        assert resp.status_code == 409

    def test_register_invalid_email_returns_422(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_register_short_password_returns_422(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "shortpw@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_register_rejects_admin_role(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "wannabeadmin@example.com",
                "password": "password123",
                "role": "admin",
            },
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_happy_path(self, client, db_session):
        from src.services.auth import hash_password

        _create_user(
            db_session,
            "logintest@example.com",
            password_hash=hash_password("correctpassword"),
            role="tutor",
        )

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "logintest@example.com", "password": "correctpassword"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["email"] == "logintest@example.com"
        assert body["role"] == "tutor"

        claims = decode_token(body["access_token"])
        assert claims["email"] == "logintest@example.com"
        assert claims["role"] == "tutor"
        assert claims["sub"]

    def test_login_wrong_password_returns_401(self, client, db_session):
        from src.services.auth import hash_password

        _create_user(
            db_session,
            "wrongpw@example.com",
            password_hash=hash_password("correctpassword"),
        )

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@example.com", "password": "incorrect"},
        )
        assert resp.status_code == 401
        wrong_body = resp.json()

        resp2 = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown-user@example.com", "password": "incorrect"},
        )
        assert resp2.status_code == 401
        assert resp2.json() == wrong_body

    def test_login_unknown_email_returns_401(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown-user@example.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_login_legacy_user_without_password_hash_returns_401(
        self, client, db_session
    ):
        _create_user(db_session, "legacy@example.com", password_hash=None)

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "legacy@example.com", "password": "anything"},
        )
        assert resp.status_code == 401
