"""
Tests for the User model's password_hash column (Phase 2, task 2.2).
"""

import uuid

from src.models.user import User
from tests.test_models import TestUser


def test_user_model_has_password_hash_column():
    """The SQLAlchemy User model must expose a password_hash column."""
    assert hasattr(User, "password_hash")
    column = User.__table__.columns["password_hash"]
    assert column.nullable is True


def test_user_password_hash_persists_and_reads_back(db_session):
    """A password_hash value set on the shadow TestUser model should
    round-trip through the db_session fixture (SQLite)."""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="local-user-1",
        email="password-hash-user@example.com",
        role="student",
        password_hash="$2b$12$examplebcrypthashvalue",
    )
    db_session.add(user)
    db_session.commit()

    fetched = (
        db_session.query(TestUser)
        .filter_by(email="password-hash-user@example.com")
        .one()
    )
    assert fetched.password_hash == "$2b$12$examplebcrypthashvalue"


def test_user_password_hash_nullable(db_session):
    """Existing rows without a password_hash (e.g. Cognito-only users)
    must remain valid — the column is nullable."""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="local-user-2",
        email="no-password-user@example.com",
        role="student",
    )
    db_session.add(user)
    db_session.commit()

    fetched = (
        db_session.query(TestUser).filter_by(email="no-password-user@example.com").one()
    )
    assert fetched.password_hash is None
