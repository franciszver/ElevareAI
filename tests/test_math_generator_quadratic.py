"""
Regression test for MathGenerator.generate_quadratic_equation crashing on
complex roots.

Root cause: the "general quadratics" branch (difficulty > 7) picks random
a/b/c and calls sympy's solve(), which solves over the complex domain by
default. When the discriminant is negative, solve() returns two complex
roots (never an empty list), so the existing `if len(roots) == 0: retry`
guard never triggers. `float(solutions[0].evalf())` then raises
"Cannot convert complex to float", which generator.py's broad
`except Exception` catches, silently falling back to the OpenAI path -
where a model response missing "choices" triggers the generic placeholder
distractors ("A related but incorrect option", etc.) that users saw in the
UI.
"""

import random

from src.services.practice.math_generator import MathGenerator


def test_generate_quadratic_equation_never_raises_on_complex_roots():
    """Regression: seed 7 with difficulty 9 previously raised
    'Cannot convert complex to float' inside generate_quadratic_equation."""
    mg = MathGenerator()
    random.seed(7)
    # Replay the same random draws that used to crash (difficulty 9 branch)
    item = mg.generate_quadratic_equation(9)

    assert item["question_text"]
    assert len(item["choices"]) == 4
    assert item["correct_answer"] in ("A", "B", "C", "D")


def test_generate_quadratic_equation_always_returns_real_valued_choices():
    """Sweep many seeds/difficulties through the high-difficulty branch and
    confirm no exception and no complex numbers leak into choices. (Distractor
    count/dedup is a separate, pre-existing concern out of scope here.)"""
    mg = MathGenerator()
    for seed in range(200):
        random.seed(seed)
        item = mg.generate_quadratic_equation(random.randint(8, 10))
        assert len(item["choices"]) >= 1
        for choice in item["choices"]:
            assert "I" not in choice.split(") ", 1)[1]  # sympy complex marker
