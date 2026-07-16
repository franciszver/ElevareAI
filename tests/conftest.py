"""
Pytest Configuration
Shared fixtures for testing
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.config.settings import settings
from src.config.database import get_db

# Import test models (SQLite-compatible with JSON instead of ARRAY)
from tests.test_models import (
    TestBase,
    TestUser, TestSubject, TestSession, TestSummary,
    TestQAInteraction, TestPracticeBankItem, TestGoal, TestStudentRating,
    TestMessageThread, TestMessage, TestPracticeAssignment
)


# Test database (in-memory SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session with SQLite-compatible models"""
    # Use test models that are SQLite-compatible
    TestBase.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        TestBase.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    """Create a test client"""
    from src.config.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Prevent app lifespan from hitting a real Postgres database on startup
    monkeypatch.setattr("src.api.main.check_database_connection", lambda: True)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "cognito_sub": "test-user-123",
        "email": "test@example.com",
        "role": "student"
    }


@pytest.fixture
def mock_ai(monkeypatch):
    """Mock the openai_client singleton's chat_completion so AI-dependent
    code paths (confidence, summarizer, practice generation, Q&A) work
    fully offline with deterministic canned responses.
    """
    from src.services.ai.openai_client import openai_client

    def fake_chat_completion(messages, temperature=None, max_tokens=None, response_format=None):
        text = " ".join(m.get("content", "") for m in messages)

        if "Rate your confidence" in text:
            return "0.85"

        if "summaries of tutoring sessions" in text:
            return (
                "You made great progress today reviewing key concepts.\n\n"
                "Next steps:\n1. Review notes\n2. Practice problems"
            )

        if "multiple-choice practice problems" in text:
            return (
                '{"question_text": "What is the sum of 2 and 2 in basic arithmetic?", '
                '"choices": ["A) 3", "B) 4", "C) 5", "D) 6"], '
                '"correct_answer": "B", '
                '"answer_text": "4", '
                '"explanation": "2 + 2 equals 4 by basic addition rules."}'
            )

        return "This is a helpful educational answer to your question."

    monkeypatch.setattr(openai_client, "chat_completion", fake_chat_completion)
    return openai_client

