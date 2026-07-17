"""Deterministic (offline, no-API) graders.

E0 ships two graders end-to-end to prove the harness works: a QA confidence-
line check and a practice-item JSON structure check. E1 adds the remaining
checks from the eval plan (answer length caps, no-LaTeX, summary next-steps
parsing, placeholder-distractor detection, SymPy math ground-truth, etc.).
"""

import json
import re
from dataclasses import dataclass

# Matches a trailing "CONFIDENCE: ..." line (mirrors src/api/handlers/qa.py's
# _CONFIDENCE_LINE_RE so the grader agrees with what the app itself parses).
_CONFIDENCE_LINE_RE = re.compile(
    r"\n?[ \t]*CONFIDENCE:[ \t]*(\S*)[ \t]*$", re.IGNORECASE
)

VALID_ANSWER_LETTERS = {"A", "B", "C", "D"}


@dataclass
class GradeResult:
    passed: bool
    score: float
    detail: str


def confidence_line_present(answer: str) -> GradeResult:
    """Check that `answer` ends with a `CONFIDENCE: 0.NN` line parseable to [0, 1]."""
    match = _CONFIDENCE_LINE_RE.search(answer or "")
    if not match:
        return GradeResult(passed=False, score=0.0, detail="No CONFIDENCE line found")

    raw_value = match.group(1)
    try:
        value = float(raw_value)
    except ValueError:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"CONFIDENCE value '{raw_value}' is not a number",
        )

    if not (0.0 <= value <= 1.0):
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"CONFIDENCE value {value} is out of range [0, 1]",
        )

    return GradeResult(
        passed=True, score=1.0, detail=f"CONFIDENCE: {value} present and valid"
    )


def practice_json_valid(raw: str) -> GradeResult:
    """Check that `raw` is valid JSON with question_text, exactly 4 choices,
    and a correct_answer in {A, B, C, D}."""
    try:
        item = json.loads(raw)
    except json.JSONDecodeError as e:
        return GradeResult(passed=False, score=0.0, detail=f"Invalid JSON: {e}")

    if not isinstance(item, dict):
        return GradeResult(
            passed=False, score=0.0, detail="Parsed JSON is not an object"
        )

    issues = []

    question_text = item.get("question_text")
    if not isinstance(question_text, str) or not question_text.strip():
        issues.append("missing or empty question_text")

    choices = item.get("choices")
    if not isinstance(choices, list) or len(choices) != 4:
        issues.append(f"expected exactly 4 choices, got {choices!r}")

    correct_answer = item.get("correct_answer")
    if (
        not isinstance(correct_answer, str)
        or correct_answer.strip().upper() not in VALID_ANSWER_LETTERS
    ):
        issues.append(f"correct_answer must be one of A/B/C/D, got {correct_answer!r}")

    if issues:
        return GradeResult(passed=False, score=0.0, detail="; ".join(issues))

    return GradeResult(passed=True, score=1.0, detail="Valid practice item JSON")
