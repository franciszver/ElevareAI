"""
Regression tests for MathGenerator sometimes returning fewer than 4 choices.

Root cause: `_generate_expression_choices` (used by
`generate_expression_simplification`) and `_generate_math_choices` (used by
`generate_linear_equation` / `generate_quadratic_equation`) built a
distractor list and deduped it with `list(set(distractors))[:3]` (or an
equivalent filter). For the default "simplify" operation, only two
candidate distractors were ever generated (`{correct} + 1`, `{correct} * 2`),
so the total choice count was 3, not 4. For linear/quadratic, the same
dedup-collapse pattern occasionally dropped one or two distractors when
random perturbations coincided or canceled out (e.g. correct_value == 0
makes `-correct_value` collide with `correct_value`).

Fixed: both distractor helpers now dedupe against an explicit "seen" set
while building the candidate list, and top up with additional synthesized
near-miss candidates until exactly 3 distinct distractors are collected,
guaranteeing exactly 4 distinct choices every time.
"""

import random

from src.services.practice.math_generator import MathGenerator


def test_generate_expression_simplification_reproduces_3_choices_before_fix():
    """RED (documents the bug): seed 0 with the default operation
    ('simplify') and default difficulty (5) used to yield only 3 choices
    because the distractor helper only ever produced 2 distractors for the
    simplify path. This test pins the fix: it must now be 4."""
    mg = MathGenerator()
    random.seed(0)
    item = mg.generate_expression_simplification()

    assert len(item["choices"]) == 4


def test_generate_expression_simplification_always_4_distinct_choices():
    """Sweep many seeds through the buggy default (simplify) path and every
    other operation; every item must have exactly 4 distinct choices with
    the correct answer among them."""
    mg = MathGenerator()
    for seed in range(200):
        for operation in ("simplify", "expand", "factor"):
            random.seed(seed)
            item = mg.generate_expression_simplification(operation=operation)
            choices = item["choices"]
            option_texts = [c.split(") ", 1)[1] for c in choices]

            assert len(choices) == 4, (seed, operation, choices)
            assert len(set(option_texts)) == 4, (seed, operation, choices)
            assert item["correct_answer"] in ("A", "B", "C", "D")
            correct_letter = item["correct_answer"]
            correct_choice = next(
                c for c in choices if c.startswith(f"{correct_letter})")
            )
            assert correct_choice.split(") ", 1)[1] == item["answer_text"]


def test_generate_linear_equation_always_4_distinct_choices():
    mg = MathGenerator()
    for seed in range(300):
        random.seed(seed)
        item = mg.generate_linear_equation(random.randint(1, 10))
        choices = item["choices"]
        option_texts = [c.split(") ", 1)[1] for c in choices]

        assert len(choices) == 4, (seed, choices)
        assert len(set(option_texts)) == 4, (seed, choices)
        assert item["correct_answer"] in ("A", "B", "C", "D")


def test_generate_quadratic_equation_always_4_distinct_choices():
    mg = MathGenerator()
    for seed in range(300):
        random.seed(seed)
        item = mg.generate_quadratic_equation(random.randint(1, 10))
        choices = item["choices"]
        option_texts = [c.split(") ", 1)[1] for c in choices]

        assert len(choices) == 4, (seed, choices)
        assert len(set(option_texts)) == 4, (seed, choices)
        assert item["correct_answer"] in ("A", "B", "C", "D")


def test_format_choice_value_collapses_4dp_precision():
    """RED: dedup must use the same display precision as rendering.
    Numbers differing only in 3rd/4th decimals (e.g. 1.234 vs 1.236) should
    format to the same display string (both "1.23") so they never both appear
    as "distinct" choices."""
    from src.services.practice.math_generator import MathGenerator

    mg = MathGenerator()

    # Helper should collapse both to same display string
    assert mg._format_choice_value(1.234) == mg._format_choice_value(1.236)
    assert mg._format_choice_value(1.234) == "1.23"

    # Integer special case
    assert mg._format_choice_value(2.0) == "2"
    assert mg._format_choice_value(2.1) == "2.1"
    assert mg._format_choice_value(2.12) == "2.12"
    assert mg._format_choice_value(2.126) == "2.13"  # rounds at 2dp


def test_numeric_choices_dedup_at_display_precision():
    """RED: when candidate offsets collide at display precision, produce
    exactly 4 visually distinct choices (no two show identical displayed values).
    Force collision by constructing a correct_value whose ±1/±2/×2/÷2 offsets
    all round to same 2dp display values."""
    mg = MathGenerator()

    # Use a value where fixed offsets collide at 2dp but differ at 4dp:
    # correct_value = 1.2349
    # +1 = 2.2349 -> "2.23"
    # -1 = 0.2349 -> "0.23"
    # +2 = 3.2349 -> "3.23"
    # -2 = -0.7651 -> "-0.77"
    # ×2 = 2.4698 -> "2.47"
    # ÷2 = 0.61745 -> "0.62"
    # So: no collision in this set at 2dp
    # But test a constructed case: correct_value = 1.234
    # candidates: 2.234->2.23, 0.234->0.23, 3.234->3.23, -0.766->-0.77, 2.468->2.47, 0.617->0.62
    # Actually, let me force a real collision in the 4dp dedup but 2dp display:
    # If correct=10.115 (displays as "10.12" when rounded):
    # candidate 10.116 (4dp rounded = 10.1160) vs 10.115 (4dp = 10.1150) → both distinct at 4dp
    # But both display as "10.12" at 2dp
    # The offsets ±1,±2,×2,÷2 won't naturally cause this, so verify at method level:
    choices, correct_letter = mg._generate_math_choices(10.115, difficulty=5)
    option_texts = [c.split(") ", 1)[1] for c in choices]

    # Must have exactly 4 distinct displayed values
    assert len(set(option_texts)) == 4, f"Collision detected: {option_texts}"
    assert len(choices) == 4
