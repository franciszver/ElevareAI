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
    # Proves the real parse path ran (fallback would give generic steps)
    assert summary.next_steps == ["Review notes", "Practice problems"]


def test_summarizer_parses_bare_next_marker(monkeypatch):
    """Regression test for the `re.split(...) or re.split(...)` bug:
    `re.split` always returns a non-empty list (even on no match), so the
    `or` never falls through to the "next:" pattern when the "next steps:"
    pattern doesn't match. A model response using the bare "Next:" marker
    (no "steps") must still have its actual steps parsed out, not fall back
    to the generic default."""
    summarizer = SessionSummarizer()
    monkeypatch.setattr(
        summarizer.openai,
        "chat_completion",
        lambda prompt: (
            "Great session on quadratics.\n"
            "Next: Practice factoring, Review the quadratic formula"
        ),
    )

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

    assert summary.narrative.strip() == "Great session on quadratics."
    assert summary.next_steps == ["Practice factoring, Review the quadratic formula"]


def test_summarizer_prefers_next_steps_marker_over_mid_narrative_next(monkeypatch):
    """Regression test: a response containing BOTH a mid-narrative "Next:"
    and a later "Next steps:" section must split at "next steps:" (the real
    section), not at the first "Next:" occurrence. The mid-narrative prose
    stays in the narrative and the actual steps are parsed from the "Next
    steps:" section."""
    summarizer = SessionSummarizer()
    monkeypatch.setattr(
        summarizer.openai,
        "chat_completion",
        lambda prompt: (
            "We reviewed X. Next: I'll grab coffee.\n\n"
            "Next steps:\n"
            "1. Practice factoring\n"
            "2. Review notes"
        ),
    )

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

    assert summary.narrative.strip() == "We reviewed X. Next: I'll grab coffee."
    assert summary.next_steps == ["Practice factoring", "Review notes"]


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


def test_practice_generation_requests_json_object_format(monkeypatch):
    """generate_with_context must ask the model for a JSON object response so
    gpt-oss-20b (and similar models) don't emit raw LaTeX/backslashes that
    break json.loads."""
    from src.services.ai.openai_client import openai_client

    captured = {}

    def fake_chat_completion(
        messages, temperature=None, max_tokens=None, response_format=None
    ):
        captured["response_format"] = response_format
        return (
            '{"question_text": "What is 2+2?", '
            '"choices": ["A) 3", "B) 4", "C) 5", "D) 6"], '
            '"correct_answer": "B", '
            '"answer_text": "4", '
            '"explanation": "2 + 2 equals 4."}'
        )

    monkeypatch.setattr(openai_client, "chat_completion", fake_chat_completion)

    service = PracticeQualityService()
    service.generate_with_context(
        subject="Math",
        topic="Algebra",
        difficulty_level=3,
    )

    assert captured["response_format"] == {"type": "json_object"}


def test_confidence_requests_higher_max_tokens(monkeypatch):
    """calculate_confidence must give reasoning models (e.g. gpt-oss-20b) enough
    max_tokens headroom for hidden reasoning, or the visible content comes back
    empty with finish_reason=length."""
    from src.services.ai.openai_client import openai_client

    captured = {}

    def fake_chat_completion(
        messages, temperature=None, max_tokens=None, response_format=None
    ):
        captured["max_tokens"] = max_tokens
        return "0.85"

    monkeypatch.setattr(openai_client, "chat_completion", fake_chat_completion)

    calculate_confidence(
        query="What is the Pythagorean theorem?",
        answer="a^2 + b^2 = c^2 for right triangles.",
    )

    assert captured["max_tokens"] == 400
