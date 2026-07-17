"""
Tests for get_database_url() (Phase 5 render.yaml fix).
Verifies settings.database_url (Render's DATABASE_URL) is used verbatim when
set -- normalizing postgres:// to postgresql:// for SQLAlchemy 2.x -- and
that the DB_* parts are composed as before when database_url is unset.
"""

from src.config.settings import get_database_url, settings


def test_get_database_url_composes_from_parts_when_unset(monkeypatch):
    """Existing behavior: no DATABASE_URL -> compose from DB_* parts."""
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_user", "postgres")
    monkeypatch.setattr(settings, "db_password", "secret")
    monkeypatch.setattr(settings, "db_host", "localhost")
    monkeypatch.setattr(settings, "db_port", 5432)
    monkeypatch.setattr(settings, "db_name", "elevareai")

    assert get_database_url() == "postgresql://postgres:secret@localhost:5432/elevareai"


def test_get_database_url_uses_database_url_verbatim_when_set(monkeypatch):
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql://user:pass@dpg-example.render.com/dbname",
    )

    assert get_database_url() == "postgresql://user:pass@dpg-example.render.com/dbname"


def test_get_database_url_normalizes_postgres_scheme(monkeypatch):
    """Render's connectionString uses the postgres:// scheme; SQLAlchemy 2.x
    requires postgresql://, so it must be normalized defensively."""
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgres://user:pass@dpg-example.render.com/dbname",
    )

    assert get_database_url() == "postgresql://user:pass@dpg-example.render.com/dbname"
