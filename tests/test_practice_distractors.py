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


def test_improve_practice_item_ignores_empty_choices_from_model(monkeypatch):
    """Bug: if the model's JSON explicitly returns `"choices": []`, the naive
    {**item, **improved} merge clobbers the original's valid choices with an
    empty list. Fixed: falsy/empty improved fields are filtered out before
    merging, so the original's choices survive."""

    def fake_chat_completion(
        messages, temperature=None, max_tokens=None, response_format=None
    ):
        return (
            '{"question_text": "Improved question?", '
            '"answer_text": "Improved answer", '
            '"explanation": "Improved explanation that is long enough to pass validation checks.", '
            '"choices": [], '
            '"correct_answer": ""}'
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

    assert improved["choices"] == ["A) 1", "B) 2", "C) 3", "D) 4"]
    assert improved["correct_answer"] == "B"


def test_improve_practice_item_regression_falls_back_to_original(monkeypatch):
    """If the model's "improved" response introduces a format regression
    (only 3 choices instead of 4) while leaving the item's pre-existing
    deficiencies unfixed (empty answer_text/explanation get filtered out of
    the merge, so the original's short answer and missing explanation
    persist), the merged item scores worse than the original. Defensive
    check: improve_practice_item must return the original unchanged rather
    than ship a regression."""

    def fake_chat_completion(
        messages, temperature=None, max_tokens=None, response_format=None
    ):
        return (
            '{"question_text": "", '
            '"answer_text": "", '
            '"explanation": "", '
            '"choices": ["A) new1", "B) new2", "C) new3"]}'
        )

    monkeypatch.setattr(openai_client, "chat_completion", fake_chat_completion)

    service = PracticeQualityService()
    original_item = {
        "question_text": "Old q",  # too short -> triggers improvement
        "answer_text": "ok",  # too short
        "explanation": "",  # missing
        "choices": ["A) 1", "B) 2", "C) 3", "D) 4"],
        "correct_answer": "B",
    }
    original_validation = service.validate_practice_item(original_item)
    assert not original_validation["is_valid"]  # sanity: AI path is taken

    improved = service.improve_practice_item(
        original_item, subject="Math", topic="Algebra", difficulty_level=3
    )

    merged_validation = service.validate_practice_item(improved)
    # The fix must never regress below the original's score - and since the
    # regression is caught, the original item itself should come back.
    assert merged_validation["quality_score"] >= original_validation["quality_score"]
    assert improved == original_item


def test_improve_practice_item_merges_when_all_fields_valid(monkeypatch):
    """Sanity check: when the model returns a fully valid improved item, the
    merge should proceed normally (not defensively fall back to original)."""

    def fake_chat_completion(
        messages, temperature=None, max_tokens=None, response_format=None
    ):
        return (
            '{"question_text": "What is the improved question here?", '
            '"answer_text": "Improved answer text", '
            '"explanation": "Improved explanation that is long enough to pass validation checks.", '
            '"choices": ["A) new1", "B) new2", "C) new3", "D) new4"], '
            '"correct_answer": "C"}'
        )

    monkeypatch.setattr(openai_client, "chat_completion", fake_chat_completion)

    service = PracticeQualityService()
    original_item = {
        "question_text": "Old q",  # too short -> triggers improvement
        "answer_text": "Old answer",
        "explanation": "",  # missing
        "choices": ["A) 1", "B) 2", "C) 3", "D) 4"],
        "correct_answer": "B",
    }

    improved = service.improve_practice_item(
        original_item, subject="Math", topic="Algebra", difficulty_level=3
    )

    assert improved["question_text"] == "What is the improved question here?"
    assert improved["choices"] == ["A) new1", "B) new2", "C) new3", "D) new4"]
    assert improved["correct_answer"] == "C"


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


def test_generate_numeric_distractors_distinct_and_no_placeholders():
    """Distractors must be distinct, non-placeholder, and structurally
    numeric (common-mistake perturbations of the answer)."""
    service = PracticeQualityService()
    distractors = service._generate_numeric_distractors("", 12.0)

    assert len(distractors) == 3
    assert len(set(distractors)) == 3
    for d in distractors:
        assert d not in PLACEHOLDER_STRINGS
        assert d != "12"  # never equal to the correct answer


def test_generate_numeric_distractors_are_close_to_the_answer():
    """Common-mistake perturbations (off-by-one/two, sign error,
    doubled/halved) should be prioritized closest-to-the-answer first, not
    random far-off values. For a reasonably sized answer, the generated
    distractors should stay within a small multiple of the answer's
    magnitude rather than jumping to arbitrary far values."""
    service = PracticeQualityService()
    value = 20.0
    distractors = service._generate_numeric_distractors("", value)

    numeric_distractors = [float(d) for d in distractors]
    for d in numeric_distractors:
        # Closest-first ordering means the top 3 candidates (+1, -1, +2)
        # should be picked before doubled/halved for a non-colliding value.
        assert abs(d - value) <= value  # not wildly far off (e.g. not 10x)


def test_generate_numeric_distractors_zero_value_still_distinct():
    """Edge case: correct_value == 0 makes sign-flip and doubling collide
    with 0 itself; the top-up/dedup logic must still yield 3 distinct
    non-zero distractors."""
    service = PracticeQualityService()
    distractors = service._generate_numeric_distractors("", 0.0)

    assert len(distractors) == 3
    assert len(set(distractors)) == 3
    assert "0" not in distractors


def test_practice_generation_prompt_includes_distractor_plausibility_guidance():
    """The non-math practice generation prompt must explicitly instruct the
    model to produce plausible, on-topic, era/context-appropriate distractors
    that represent realistic misconceptions - not obviously-wrong throwaway
    options - while preserving the JSON-only + no-LaTeX constraints."""
    from src.services.ai.prompts import PromptTemplates

    messages = PromptTemplates.practice_generation_prompt(
        subject="History", topic="Ancient Rome", difficulty_level=5
    )
    system_content = messages[0]["content"]

    assert "plausible" in system_content.lower()
    assert "anachronism" in system_content.lower()
    assert "misconception" in system_content.lower()
    # JSON-only + no-LaTeX constraints must still be present
    assert "JSON" in system_content
    assert "LaTeX" in system_content
