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
    Numbers differing only in 3rd/4th decimals should format to the same
    display string so they never both appear as "distinct" choices.
    E.g. 1.2301 and 1.2349 both round to "1.23" at 2dp."""
    from src.services.practice.math_generator import MathGenerator

    mg = MathGenerator()

    # Helper should collapse both to same display string (both round to 1.23)
    assert mg._format_choice_value(1.2301) == mg._format_choice_value(1.2349)
    assert mg._format_choice_value(1.2301) == "1.23"

    # Integer special case
    assert mg._format_choice_value(2.0) == "2"
    assert mg._format_choice_value(2.1) == "2.1"
    assert mg._format_choice_value(2.12) == "2.12"
    assert mg._format_choice_value(2.126) == "2.13"  # rounds at 2dp


def test_dedup_uses_display_formatter_not_raw_precision():
    """Regression guard for #38: dedup must key on the display-formatted
    value, not raw 4dp rounding. The display loop calls _format_choice_value
    once per final choice (4 times); if dedup ALSO routes through it (the fix),
    the helper is invoked well more than 4 times (seed + every candidate).
    A revert to round(candidate, 4) for dedup would drop the call count to 4."""
    from unittest.mock import patch

    from src.services.practice.math_generator import MathGenerator

    mg = MathGenerator()
    with patch.object(mg, "_format_choice_value", wraps=mg._format_choice_value) as spy:
        choices, _ = mg._generate_math_choices(7.5, difficulty=5)
    assert len(choices) == 4
    # 4 display calls + dedup seed + per-candidate calls => strictly > 4
    assert spy.call_count > 4, (
        f"dedup did not route through _format_choice_value "
        f"(call_count={spy.call_count}); precision mismatch regression"
    )
