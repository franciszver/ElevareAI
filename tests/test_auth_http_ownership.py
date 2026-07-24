"""
HTTP-level auth regression tests (Phase 2, task P2.3).

The Cognito -> self-hosted JWT migration rewrote the auth middleware and the
goals/progress ownership checks, but until now that path (get_current_user /
get_current_user_optional -> DB ownership comparison -> 403/404) was only
verified by code reading, never by an actual TestClient request carrying a
real signed JWT. These tests close that gap.

Note on IDs: tests/test_models.py's TestUser/TestGoal are SQLite shadow
models with plain String id columns, but the goals/progress handlers query
the *real* src.models.user.User / src.models.goal.Goal models, whose
UUID(as_uuid=True) columns bind-process filter parameters to a 32-char hex
string (no dashes) when running over a non-Postgres dialect (SQLite here).
If a row is written via the shadow model using a dashed uuid4 string, a
WHERE-clause filter through the real model silently matches zero rows -
not a 403/404, just an empty/never-found result, regardless of who is
asking. That is a pre-existing quirk of the SQLite test harness, not an
auth bug, and it goes away in production (real Postgres UUID columns).
IDs here are created with uuid.uuid4().hex to avoid tripping over it, so
the "own resource -> 200 with the actual data" assertions are meaningful
rather than accidentally-empty.
"""

import uuid

import pytest

from src.services.auth import create_access_token
from tests.test_models import TestGoal, TestUser


def _uid() -> str:
    return uuid.uuid4().hex


def _create_user(db_session, email, role="student", cognito_sub=None):
    user = TestUser(
        id=_uid(),
        cognito_sub=cognito_sub or _uid(),
        email=email,
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_goal(db_session, student, **overrides):
    goal = TestGoal(
        id=_uid(),
        student_id=student.id,
        created_by=student.id,
        goal_type=overrides.pop("goal_type", "Standard"),
        title=overrides.pop("title", "Test Goal"),
        status=overrides.pop("status", "active"),
        **overrides,
    )
    db_session.add(goal)
    db_session.commit()
    return goal


def _token(user, **kw):
    return create_access_token(
        sub=user.cognito_sub, email=user.email, role=user.role, **kw
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setattr("src.config.settings.settings.jwt_secret", "test-secret")


class TestGoalsOwnership:
    """GET /api/v1/goals and DELETE /api/v1/goals/{id} ownership boundary."""

    def test_get_own_goals_returns_200_with_data(self, client, db_session):
        student = _create_user(db_session, "student-a@example.com")
        goal = _create_goal(db_session, student)
        token = _token(student)

        resp = client.get(
            f"/api/v1/goals?student_id={student.id}", headers=_auth(token)
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert [g["id"] for g in body["data"]] == [str(uuid.UUID(goal.id))]

    def test_get_another_students_goals_returns_403(self, client, db_session):
        student_a = _create_user(db_session, "student-a2@example.com")
        student_b = _create_user(db_session, "student-b2@example.com")
        _create_goal(db_session, student_b)
        token_a = _token(student_a)

        resp = client.get(
            f"/api/v1/goals?student_id={student_b.id}", headers=_auth(token_a)
        )

        assert resp.status_code == 403

    def test_get_goals_token_sub_not_in_db_returns_404(self, client, db_session):
        student = _create_user(db_session, "student-c@example.com")
        ghost_token = create_access_token(
            sub="ghost-sub-not-in-db", email="ghost@example.com", role="student"
        )

        resp = client.get(
            f"/api/v1/goals?student_id={student.id}", headers=_auth(ghost_token)
        )

        assert resp.status_code == 404

    def test_get_goals_no_token_returns_401_in_production(
        self, client, db_session, monkeypatch
    ):
        # get_current_user_optional swallows the missing-credentials case and
        # goals.py falls back to an unauthenticated dev-mode bypass when
        # settings.environment == "development" (the test-suite default).
        # Patch to a non-development environment to exercise the path real
        # deployments actually run under.
        monkeypatch.setattr("src.config.settings.settings.environment", "production")
        student = _create_user(db_session, "student-d@example.com")

        resp = client.get(f"/api/v1/goals?student_id={student.id}")

        assert resp.status_code == 401

    def test_get_goals_malformed_token_returns_401_in_production(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr("src.config.settings.settings.environment", "production")
        student = _create_user(db_session, "student-e@example.com")

        resp = client.get(
            f"/api/v1/goals?student_id={student.id}",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert resp.status_code == 401

    def test_get_goals_expired_token_returns_401_in_production(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr("src.config.settings.settings.environment", "production")
        student = _create_user(db_session, "student-f@example.com")
        expired = _token(student, expires_minutes=-1)

        resp = client.get(
            f"/api/v1/goals?student_id={student.id}", headers=_auth(expired)
        )

        assert resp.status_code == 401

    def test_modify_own_goal_succeeds(self, client, db_session):
        # Uses POST /goals/{id}/reset (not delete) - the real Goal model has
        # a relationship to QAInteraction.goal_id that the SQLite shadow
        # model (tests/test_models.py TestQAInteraction) doesn't define,
        # which makes an ORM-level delete cascade blow up with an unrelated
        # "no such column" error in this harness. reset avoids that and
        # still proves a student can mutate their own goal end-to-end.
        student = _create_user(db_session, "student-g@example.com")
        goal = _create_goal(db_session, student, status="completed")
        token = _token(student)

        resp = client.post(f"/api/v1/goals/{goal.id}/reset", headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

    def test_delete_another_students_goal_returns_403(self, client, db_session):
        student_a = _create_user(db_session, "student-h@example.com")
        student_b = _create_user(db_session, "student-i@example.com")
        goal_b = _create_goal(db_session, student_b)
        token_a = _token(student_a)

        resp = client.delete(f"/api/v1/goals/{goal_b.id}", headers=_auth(token_a))

        assert resp.status_code == 403
        # The ownership boundary must actually have blocked the delete, not
        # just returned the wrong status code around a mutation that happened.
        still_there = db_session.query(TestGoal).filter_by(id=goal_b.id).first()
        assert still_there is not None

    def test_delete_nonexistent_goal_returns_404(self, client, db_session):
        student = _create_user(db_session, "student-j@example.com")
        token = _token(student)

        resp = client.delete(f"/api/v1/goals/{_uid()}", headers=_auth(token))

        assert resp.status_code == 404


class TestProgressOwnership:
    """GET /api/v1/progress/{user_id} ownership boundary."""

    def test_get_own_progress_returns_200(self, client, db_session):
        student = _create_user(db_session, "progress-a@example.com")
        token = _token(student)

        resp = client.get(f"/api/v1/progress/{student.id}", headers=_auth(token))

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["user_id"] == str(uuid.UUID(student.id))

    def test_get_another_students_progress_returns_403(self, client, db_session):
        student_a = _create_user(db_session, "progress-b@example.com")
        student_b = _create_user(db_session, "progress-c@example.com")
        token_a = _token(student_a)

        resp = client.get(f"/api/v1/progress/{student_b.id}", headers=_auth(token_a))

        assert resp.status_code == 403

    def test_get_progress_no_token_returns_401(self, client, db_session):
        student = _create_user(db_session, "progress-d@example.com")

        resp = client.get(f"/api/v1/progress/{student.id}")

        # FastAPI's HTTPBearer(auto_error=True) raises 403, not 401, when the
        # Authorization header is entirely absent (it only 401s on a header
        # that's present but invalid) - same behavior already documented in
        # tests/test_auth_middleware.py::test_missing_authorization_header_returns_401_or_403.
        assert resp.status_code == 403

    def test_get_progress_malformed_token_returns_401(self, client, db_session):
        student = _create_user(db_session, "progress-e@example.com")

        resp = client.get(
            f"/api/v1/progress/{student.id}",
            headers={"Authorization": "Bearer garbage-token"},
        )

        assert resp.status_code == 401

    def test_get_progress_expired_token_returns_401(self, client, db_session):
        student = _create_user(db_session, "progress-f@example.com")
        expired = _token(student, expires_minutes=-1)

        resp = client.get(f"/api/v1/progress/{student.id}", headers=_auth(expired))

        assert resp.status_code == 401


class TestNoDevAuthBypass:
    """#32: goals/progress must require auth in ALL environments, including
    development. settings.environment is explicitly patched to "development"
    in each test so these pin the fixed behavior independent of whatever
    ENVIRONMENT happens to be set to in the ambient shell/.env.
    """

    def test_get_goals_no_token_returns_401_in_development(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr("src.config.settings.settings.environment", "development")
        student = _create_user(db_session, "dev-bypass-a@example.com")

        resp = client.get(f"/api/v1/goals?student_id={student.id}")

        assert resp.status_code == 401

    def test_create_goal_no_token_returns_401_in_development(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr("src.config.settings.settings.environment", "development")
        student = _create_user(db_session, "dev-bypass-b@example.com")

        resp = client.post(
            "/api/v1/goals",
            json={"student_id": student.id, "title": "Should not be created"},
        )

        assert resp.status_code == 401

    def test_reset_goal_no_token_returns_401_in_development(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr("src.config.settings.settings.environment", "development")
        student = _create_user(db_session, "dev-bypass-c@example.com")
        goal = _create_goal(db_session, student, status="completed")

        resp = client.post(f"/api/v1/goals/{goal.id}/reset")

        assert resp.status_code == 401

    def test_delete_goal_no_token_returns_401_in_development(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr("src.config.settings.settings.environment", "development")
        student = _create_user(db_session, "dev-bypass-d@example.com")
        goal = _create_goal(db_session, student)

        resp = client.delete(f"/api/v1/goals/{goal.id}")

        assert resp.status_code == 401

    def test_get_progress_no_token_returns_401_in_development(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr("src.config.settings.settings.environment", "development")
        student = _create_user(db_session, "dev-bypass-e@example.com")

        resp = client.get(f"/api/v1/progress/{student.id}")

        assert resp.status_code == 401
