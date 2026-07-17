"""
Regression tests for MathGenerator distractors that are distinct as STRINGS
but symbolically/numerically identical.

Root cause (found by the P1.5 Claude judge, tracked as P1.6):
`_generate_expression_choices` deduped candidate distractors by string
equality only. For `generate_expression_simplification(5, "expand")` with
seed 1, the candidates "x**2 + 7*x + 10 + 1" and "x**2 + 7*x + 11" are
different strings but both simplify to x**2 + 7*x + 11, so both passed the
`seen` set as "distinct" and the item shipped with only 3 distinct VALUES
across its 4 choices - a broken multiple-choice question with two
mathematically-identical options.

Fixed: `_generate_expression_choices` now dedupes candidates by a SymPy
canonical key (`_canonical_key`, via `simplify(parse_expr(...))`), falling
back to raw-string distinctness only when SymPy can't parse a candidate.
"""

import random

import sympy

from src.services.practice.math_generator import MathGenerator


def _symbolic_values(choices):
    """Return the SymPy-canonicalized value of each choice's text, falling
    back to the raw text if it isn't parseable (mirrors the grader's
    tolerance for non-expression choices, e.g. plain numbers)."""
    values = []
    for choice in choices:
        text = choice.split(") ", 1)[1]
        try:
            values.append(str(sympy.simplify(sympy.sympify(text))))
        except Exception:
            values.append(text)
    return values


def test_generate_expression_simplification_seed1_expand_4_symbolically_distinct():
    """GREEN: seed 1 with operation='expand', difficulty 5 (the P1.5 judge's
    repro) previously produced only 3 symbolically-distinct values across 4
    string-distinct choices. After the fix, all 4 must be symbolically
    distinct."""
    mg = MathGenerator()
    random.seed(1)
    item = mg.generate_expression_simplification(5, "expand")

    values = _symbolic_values(item["choices"])
    assert len(item["choices"]) == 4
    assert len(set(values)) == 4, (item["choices"], values)


def test_generate_expression_simplification_symbolic_sweep():
    """Sweep seeds across simplify/expand/factor; every item's 4 choices
    must be pairwise SYMBOLICALLY distinct (stronger than mere string
    distinctness), with the correct answer among them."""
    mg = MathGenerator()
    for seed in range(250):
        for operation in ("simplify", "expand", "factor"):
            random.seed(seed)
            item = mg.generate_expression_simplification(operation=operation)
            choices = item["choices"]
            option_texts = [c.split(") ", 1)[1] for c in choices]
            values = _symbolic_values(choices)

            assert len(choices) == 4, (seed, operation, choices)
            assert len(set(values)) == 4, (seed, operation, choices, values)
            assert item["answer_text"] in option_texts, (seed, operation, choices)


def test_generate_linear_equation_symbolic_sweep():
    """Linear equation choices are plain numbers; numeric equality is the
    same thing as symbolic equality here, but sweep it for parity with the
    expression-choice guarantee above."""
    mg = MathGenerator()
    for seed in range(250):
        random.seed(seed)
        item = mg.generate_linear_equation(random.randint(1, 10))
        choices = item["choices"]
        values = _symbolic_values(choices)

        assert len(choices) == 4, (seed, choices)
        assert len(set(values)) == 4, (seed, choices, values)


def test_generate_quadratic_equation_symbolic_sweep():
    mg = MathGenerator()
    for seed in range(250):
        random.seed(seed)
        item = mg.generate_quadratic_equation(random.randint(1, 10))
        choices = item["choices"]
        values = _symbolic_values(choices)

        assert len(choices) == 4, (seed, choices)
        assert len(set(values)) == 4, (seed, choices, values)
