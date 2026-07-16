"""
Tests for src/api/middleware/auth.py (Phase 2, task 2.4).

Covers local JWT validation via src.services.auth.decode_token (including
confirming the sunset mock-token-* demo bypass is rejected), and require_role
semantics.
"""

import uuid

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.middleware.auth import (
    get_current_user,
    get_current_user_optional,
    require_role,
    verify_token,
)
from src.services.auth import create_access_token
from tests.test_models import TestUser


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setattr("src.config.settings.settings.jwt_secret", "test-secret")


def _make_token(sub="user-sub-1", email="student@example.com", role="student", **kw):
    return create_access_token(sub=sub, email=email, role=role, **kw)


# --- A tiny standalone app to exercise the dependencies directly ---


def _build_app():
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user: dict = Depends(get_current_user)):
        return user

    @app.get("/whoami-optional")
    async def whoami_optional(user=Depends(get_current_user_optional)):
        return {"user": user}

    return app


@pytest.fixture
def middleware_client():
    return TestClient(_build_app())


class TestGetCurrentUser:
    def test_valid_token_returns_claims_with_sub_email_role(self, middleware_client):
        token = _make_token(sub="abc-123", email="a@b.com", role="tutor")
        resp = middleware_client.get(
            "/whoami", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sub"] == "abc-123"
        assert body["email"] == "a@b.com"
        assert body["role"] == "tutor"

    def test_expired_token_returns_401(self, middleware_client):
        token = _make_token(expires_minutes=-1)
        resp = middleware_client.get(
            "/whoami", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    def test_tampered_token_returns_401(self, middleware_client):
        token = _make_token()
        tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
        resp = middleware_client.get(
            "/whoami", headers={"Authorization": f"Bearer {tampered}"}
        )
        assert resp.status_code == 401

    def test_wrong_secret_returns_401(self, middleware_client, monkeypatch):
        token = _make_token()
        monkeypatch.setattr(
            "src.config.settings.settings.jwt_secret", "a-different-secret"
        )
        resp = middleware_client.get(
            "/whoami", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    def test_missing_authorization_header_returns_401_or_403(self, middleware_client):
        # HTTPBearer's default behavior for a missing header (unchanged by
        # this rewrite) - snapshot whatever the current status is.
        resp = middleware_client.get("/whoami")
        assert resp.status_code in (401, 403)

    def test_malformed_scheme_returns_401_or_403(self, middleware_client):
        resp = middleware_client.get(
            "/whoami", headers={"Authorization": "Basic sometoken"}
        )
        assert resp.status_code in (401, 403)

    def test_mock_token_is_rejected_with_401(self, middleware_client):
        """The mock-token-* bypass has been sunset; it must be treated as an
        ordinary invalid token and rejected with 401."""
        resp = middleware_client.get(
            "/whoami", headers={"Authorization": "Bearer mock-token-anything"}
        )
        assert resp.status_code == 401


class TestGetCurrentUserOptional:
    def test_no_credentials_returns_none(self, middleware_client):
        resp = middleware_client.get("/whoami-optional")
        assert resp.status_code == 200
        assert resp.json() == {"user": None}

    def test_valid_token_returns_claims(self, middleware_client):
        token = _make_token(sub="opt-user", email="opt@example.com", role="parent")
        resp = middleware_client.get(
            "/whoami-optional", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()["user"]
        assert body["sub"] == "opt-user"
        assert body["email"] == "opt@example.com"

    def test_invalid_token_returns_none(self, middleware_client):
        resp = middleware_client.get(
            "/whoami-optional", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"user": None}

    def test_mock_token_is_rejected_returns_none(self, middleware_client):
        """The mock-token-* bypass has been sunset; it must be treated as an
        ordinary invalid token and return None (not a demo user)."""
        resp = middleware_client.get(
            "/whoami-optional",
            headers={"Authorization": "Bearer mock-token-anything"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"] is None


class TestVerifyToken:
    def test_valid_token_decodes(self):
        token = _make_token(sub="s1", email="e@x.com", role="student")
        claims = verify_token(token)
        assert claims["sub"] == "s1"
        assert claims["email"] == "e@x.com"
        assert claims["role"] == "student"

    def test_invalid_token_raises_http_401(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_token("garbage.not.a.token")
        assert exc_info.value.status_code == 401


class TestRequireRole:
    def _build_role_app(self, allowed_roles):
        app = FastAPI()

        @app.get("/protected")
        async def protected(user: dict = Depends(require_role(allowed_roles))):
            return user

        return app

    def test_db_role_takes_precedence_over_token_role(self, db_session):
        """require_role prefers the DB role over the token's role claim."""
        from src.config.database import get_db

        user = TestUser(
            id=str(uuid.uuid4()),
            cognito_sub="db-role-sub",
            email="dbrole@example.com",
            role="admin",
        )
        db_session.add(user)
        db_session.commit()

        app = self._build_role_app(["admin"])

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        # Token claims role=student, but DB says admin -> DB wins, access granted.
        token = create_access_token(
            sub="db-role-sub", email="dbrole@example.com", role="student"
        )
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_token_role_fallback_when_user_not_in_db(self, db_session):
        from src.config.database import get_db

        app = self._build_role_app(["tutor"])

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        token = create_access_token(
            sub="not-in-db-sub", email="ghost@example.com", role="tutor"
        )
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_forbidden_role_returns_403(self, db_session):
        from src.config.database import get_db

        app = self._build_role_app(["tutor"])

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        token = create_access_token(
            sub="not-in-db-sub-2", email="ghost2@example.com", role="student"
        )
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestEndToEndLoginToMe:
    def test_register_login_then_get_me(self, client, db_session):
        email = "e2e-auth@example.com"
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123"},
        )
        assert resp.status_code == 201

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["email"] == email
        assert body["data"]["role"] == "student"
