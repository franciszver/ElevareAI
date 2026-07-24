"""
Tests for bounded retry of the startup database connectivity check
(src/api/main.py lifespan).

On Render free-tier Postgres, a transient connection refusal at boot can
instantly kill the deploy. The lifespan handler should retry
check_database_connection() a small bounded number of times (with a short
sleep between attempts) before giving up and raising RuntimeError.
"""

import pytest

from src.api import main as main_module
from src.api.main import app, lifespan
from src.config.settings import settings


@pytest.fixture(autouse=True)
def _jwt_ok(monkeypatch):
    """Isolate these tests from the JWT secret check."""
    monkeypatch.setattr(settings, "jwt_secret", "a-real-secret")


@pytest.fixture
def fake_sleep(monkeypatch):
    """Patch asyncio.sleep as used in src.api.main so retries are instant."""
    calls = []

    async def _fake_sleep(delay):
        calls.append(delay)

    monkeypatch.setattr(main_module.asyncio, "sleep", _fake_sleep)
    return calls


@pytest.mark.asyncio
async def test_lifespan_retries_then_succeeds(monkeypatch, fake_sleep):
    call_count = {"n": 0}

    def flaky_check():
        call_count["n"] += 1
        return call_count["n"] > 2  # fails first 2 calls, succeeds on 3rd

    monkeypatch.setattr("src.api.main.check_database_connection", flaky_check)

    async with lifespan(app):
        pass

    assert call_count["n"] == 3
    assert len(fake_sleep) == 2  # slept between attempts 1->2 and 2->3


@pytest.mark.asyncio
async def test_lifespan_raises_after_exhausting_retries(monkeypatch, fake_sleep):
    call_count = {"n": 0}

    def always_fails():
        call_count["n"] += 1
        return False

    monkeypatch.setattr("src.api.main.check_database_connection", always_fails)

    with pytest.raises(RuntimeError, match="Database connection failed on startup"):
        async with lifespan(app):
            pass

    assert call_count["n"] == 5  # DB_STARTUP_MAX_ATTEMPTS
    assert len(fake_sleep) == 4  # slept between each attempt, not after the last
