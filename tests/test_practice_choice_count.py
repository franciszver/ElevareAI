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
