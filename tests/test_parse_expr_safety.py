"""
Security regression tests: sympy's parse_expr/sympify execute arbitrary
Python when fed untrusted strings (they eval() the string against an
unrestricted namespace). Confirmed PoC:
`_canonical_key('__import__("os").system("echo PWNED")')` ran the command.

These tests assert that PoC payloads NEVER execute -- via
`safe_parse_expr` directly, via `_canonical_key`, via
`MathGenerator.validate_answer`, and via the eval grader's
`practice_math_answer_correct` -- and that legitimate math expressions
still parse/simplify identically to before.
"""

from unittest.mock import patch

import pytest

from src.services.practice.math_generator import MathGenerator, _canonical_key
from src.services.practice.safe_expr import UnsafeExpressionError, safe_parse_expr

PAYLOADS = [
    '__import__("os").system("echo PWNED")',
    "os.system('echo PWNED')",
    "eval('1+1')",
    "lambda: os.system('echo PWNED')",
    "().__class__.__bases__[0]",
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_safe_parse_expr_never_executes_payload(payload):
    with patch("os.system") as mock_system:
        with pytest.raises(UnsafeExpressionError):
            safe_parse_expr(payload)
        mock_system.assert_not_called()


@pytest.mark.parametrize("payload", PAYLOADS)
def test_canonical_key_never_executes_payload(payload):
    with patch("os.system") as mock_system:
        key = _canonical_key(payload)
        mock_system.assert_not_called()
    # Unparseable/rejected candidates fall back to the raw-string safety net.
    assert key == f"__RAW__:{payload}"


@pytest.mark.parametrize("payload", PAYLOADS)
def test_validate_answer_never_executes_payload(payload):
    mg = MathGenerator()
    with patch("os.system") as mock_system:
        result = mg.validate_answer("irrelevant", payload, "1")
        mock_system.assert_not_called()
    assert result["is_correct"] is False


@pytest.mark.parametrize("payload", PAYLOADS)
def test_grader_never_executes_payload(payload):
    from evals.graders.deterministic import practice_math_answer_correct

    item_dict = {
        "correct_answer": "A",
        "choices": [f"A) {payload}"],
        "difficulty": 5,
    }
    with patch("os.system") as mock_system:
        result = practice_math_answer_correct(
            topic="expression_simplification", seed=1, item_dict=item_dict
        )
        mock_system.assert_not_called()
    assert result.passed is False


def test_canonical_key_still_collapses_equivalent_expressions():
    """Regression: legitimate expressions must still dedup identically."""
    assert _canonical_key("x**2+7*x+10 + 1") == _canonical_key("x**2+7*x+11")


def test_safe_parse_expr_still_parses_legit_expressions():
    assert str(safe_parse_expr("x**2 + 7*x + 10")) == "x**2 + 7*x + 10"
    assert str(safe_parse_expr("2*(x+1)")) == "2*x + 2"
    assert str(safe_parse_expr("sqrt(2)")) == "sqrt(2)"
    assert str(safe_parse_expr("3/4")) == "3/4"


def test_validate_answer_still_validates_legit_answers():
    mg = MathGenerator()
    correct = mg.validate_answer("solve", "x**2 + 7*x + 10", "x**2+7*x+10")
    assert correct["is_correct"] is True

    wrong = mg.validate_answer("solve", "x**2 + 7*x + 10", "x**2+7*x+11")
    assert wrong["is_correct"] is False
