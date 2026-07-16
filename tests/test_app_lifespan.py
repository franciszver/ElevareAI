"""
Tests for the FastAPI app lifespan startup checks (src/api/main.py).

Mirrors the existing database-connection fail-fast check: an empty
JWT_SECRET must also raise RuntimeError on startup so a misconfigured
deploy fails fast instead of silently accepting/issuing tokens with an
empty signing key.
"""

import pytest

from src.api.main import app, lifespan
from src.config.settings import settings


@pytest.fixture(autouse=True)
def _db_ok(monkeypatch):
    """Isolate these tests from the real database check."""
    monkeypatch.setattr("src.api.main.check_database_connection", lambda: True)


@pytest.mark.asyncio
async def test_lifespan_raises_when_jwt_secret_empty(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "")
    with pytest.raises(RuntimeError):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_lifespan_succeeds_when_jwt_secret_configured(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "a-real-secret")
    async with lifespan(app):
        pass
