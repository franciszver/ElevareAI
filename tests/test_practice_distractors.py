"""
Tests for practice item distractor generation quality.

Covers:
- improve_practice_item must not drop choices/correct_answer when the model's
  improvement response only returns question_text/answer_text/explanation.
- _generate_multiple_choice_options must synthesize plausible numeric
  distractors instead of generic placeholder strings when the correct answer
  is numeric/algebraic.
- Generic placeholder strings are only used as an absolute last resort, and
  are subject-flavored when used.
"""

from src.services.ai.openai_client import openai_client
from src.services.practice.quality import PracticeQualityService

PLACEHOLDER_STRINGS = {
    "A related but incorrect option",
    "Another plausible but wrong answer",
    "An incorrect alternative",
}


def test_improve_practice_item_preserves_choices_on_3_key_response(monkeypatch):
    """Bug: improve_practice_item's AI response often only contains
    question_text/answer_text/explanation. The old code returned that dict
    wholesale, silently dropping choices/correct_answer from the item.
    Fixed: improved fields should be merged onto the original item."""

    def fake_chat_completion(
        messages, temperature=None, max_tokens=None, response_format=None
    ):
        return (
            '{"question_text": "Improved question?", '
            '"answer_text": "Improved answer", '
            '"explanation": "Improved explanation that is long enough to pass validation checks."}'
        )

    monkeypatch.setattr(openai_client, "chat_completion", fake_chat_completion)

    service = PracticeQualityService()
    original_item = {
        "question_text": "Old q",
        "answer_text": "Old answer",
        "explanation": "",  # too short -> triggers improvement
        "choices": ["A) 1", "B) 2", "C) 3", "D) 4"],
        "correct_answer": "B",
    }

    improved = service.improve_practice_item(
        original_item, subject="Math", topic="Algebra", difficulty_level=3
    )

    # Choices/correct_answer must survive even though the model's JSON omitted them
    assert improved["choices"] == ["A) 1", "B) 2", "C) 3", "D) 4"]
    assert improved["correct_answer"] == "B"
    # Improved fields should be applied
    assert improved["question_text"] == "Improved question?"


def test_generate_multiple_choice_options_numeric_no_placeholders():
    """Numeric correct answers should get plausible numeric distractors,
    never the generic placeholder strings."""
    service = PracticeQualityService()
    choices, correct_letter = service._generate_multiple_choice_options("x = 5")

    assert len(choices) == 4
    assert correct_letter in ("A", "B", "C", "D")

    option_texts = [c.split(") ", 1)[1] for c in choices]
    assert len(set(option_texts)) == 4  # all distinct
    for text in option_texts:
        assert text not in PLACEHOLDER_STRINGS
    assert "x = 5" in option_texts


def test_generate_multiple_choice_options_bare_number_no_placeholders():
    service = PracticeQualityService()
    choices, correct_letter = service._generate_multiple_choice_options("12")

    option_texts = [c.split(") ", 1)[1] for c in choices]
    assert len(set(option_texts)) == 4
    for text in option_texts:
        assert text not in PLACEHOLDER_STRINGS
    assert "12" in option_texts


def test_generate_multiple_choice_options_non_numeric_last_resort_is_subject_flavored():
    """Non-numeric answers with no way to request real choices from the model
    fall back to generic distractors, but they must be subject-flavored, not
    the bare old placeholder strings."""
    service = PracticeQualityService()
    choices, correct_letter = service._generate_multiple_choice_options(
        "The mitochondria is the powerhouse of the cell", subject="Biology"
    )

    option_texts = [c.split(") ", 1)[1] for c in choices]
    assert len(choices) == 4
    for text in option_texts:
        assert text not in PLACEHOLDER_STRINGS
    # At least the distractors should reference the subject
    assert any("Biology" in text for text in option_texts)


def test_add_multiple_choice_format_numeric_answer_no_placeholders():
    service = PracticeQualityService()
    item = {"answer_text": "x = 7", "question_text": "Solve for x: x + 2 = 9"}
    result = service._add_multiple_choice_format(item)

    option_texts = [c.split(") ", 1)[1] for c in result["choices"]]
    for text in option_texts:
        assert text not in PLACEHOLDER_STRINGS
    assert len(set(option_texts)) == 4
