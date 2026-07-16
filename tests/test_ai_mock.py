"""
Tests for the mock_ai fixture - verifies AI-dependent consumers work offline.
"""

import asyncio

from src.services.ai.confidence import calculate_confidence
from src.services.ai.summarizer import SessionSummarizer
from src.services.practice.quality import PracticeQualityService


def test_confidence_calculation_offline(mock_ai):
    """calculate_confidence should parse a canned confidence score with no network call"""
    result = calculate_confidence(
        query="What is the Pythagorean theorem?",
        answer="The Pythagorean theorem states that a^2 + b^2 = c^2 for right triangles.",
    )
    assert result["factors"]["llm_confidence"] == 0.85
    assert result["confidence"] in ("High", "Medium", "Low")
    assert isinstance(result["confidence_score"], float)


class _FakeDb:
    """Minimal stand-in for a DB session - generate_summary only needs
    add/commit/refresh, and this test isn't about persistence."""

    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_summarizer_offline(mock_ai):
    """SessionSummarizer should parse narrative + next steps with no network call"""
    summarizer = SessionSummarizer()

    async def run():
        return await summarizer.generate_summary(
            session_id="11111111-1111-1111-1111-111111111111",
            student_id="22222222-2222-2222-2222-222222222222",
            tutor_id="33333333-3333-3333-3333-333333333333",
            transcript="We covered quadratic equations today.",
            session_duration_minutes=45,
            subject="Math",
            topics_covered=["Quadratic Equations"],
            db=_FakeDb(),
        )

    summary = asyncio.run(run())

    assert summary.narrative
    assert "Next steps:" in summary.narrative
    assert summary.next_steps  # non-empty list of next steps


def test_practice_generation_offline(mock_ai):
    """generate_with_context should return a valid multiple-choice item with no network call"""
    service = PracticeQualityService()
    item = service.generate_with_context(
        subject="Math",
        topic="Algebra",
        difficulty_level=3,
    )

    assert item["question_text"]
    assert len(item["choices"]) == 4
    assert item["correct_answer"] in ("A", "B", "C", "D")
    assert item["answer_text"]
    assert item["explanation"]
