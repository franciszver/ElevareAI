"""Deterministic (offline, no-API) graders.

E0 shipped two graders end-to-end to prove the harness works: a QA
confidence-line check and a practice-item JSON structure check. E1 adds the
remaining checks from the eval plan (answer length caps, no-LaTeX, summary
next-steps parsing, placeholder-distractor detection, SymPy math
ground-truth, etc.).

All functions here are pure: given plain Python values (strings/dicts), they
return a `GradeResult`. They know nothing about `Case`/`expect`/`input` -
`evals/graders/registry.py` adapts them to the runner's per-case calling
convention.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

# Matches a trailing "CONFIDENCE: ..." line (mirrors src/api/handlers/qa.py's
# _CONFIDENCE_LINE_RE so the grader agrees with what the app itself parses).
_CONFIDENCE_LINE_RE = re.compile(
    r"\n?[ \t]*CONFIDENCE:[ \t]*(\S*)[ \t]*$", re.IGNORECASE
)

VALID_ANSWER_LETTERS = {"A", "B", "C", "D"}

# The exact canned refusal text src/api/handlers/qa.py returns for
# out-of-scope queries (submit_query, `if query_analysis["is_out_of_scope"]`).
# We match on a stable substring rather than the full string so minor wording
# tweaks elsewhere in the sentence don't spuriously break the grader.
_QA_OUT_OF_SCOPE_MARKER = "designed to help with educational topics"

# Known placeholder-distractor strings from
# src/services/practice/quality.py's `_generate_multiple_choice_options`
# fallback (the bug we previously fixed). The subject-flavored ones are
# templated as f"...{subject_label} answer/alternative", so we match on the
# stable prefix/suffix rather than a fixed subject.
_PLACEHOLDER_DISTRACTOR_PATTERNS = [
    re.compile(r"^A related but incorrect .*answer$", re.IGNORECASE),
    re.compile(r"^Another plausible but wrong .*answer$", re.IGNORECASE),
    re.compile(r"^An incorrect .*alternative$", re.IGNORECASE),
]

# Bare backslash-paren/bracket LaTeX delimiters. `$...$`/`$$...$$` are the
# now-supported KaTeX delimiters (see prompts.py's conciseness_guidance) and
# must NOT be flagged.
_RAW_LATEX_DELIMITER_RE = re.compile(r"\\\(|\\\)|\\\[|\\\]")


@dataclass
class GradeResult:
    passed: bool
    score: float
    detail: str
    # False marks this grader as not-applicable to the given case/output
    # (e.g. a QA out-of-scope check on an in-scope case) rather than a real
    # pass/fail. `evals/runner.py::run_cases` and `evals/grade_fixtures.py`
    # both exclude applicable=False results from pass-rate/mean-score.
    applicable: bool = True


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


# ---------------------------------------------------------------------------
# QA graders
# ---------------------------------------------------------------------------


def qa_answer_nonempty(answer: str) -> GradeResult:
    """Check that `answer` is non-empty after stripping the CONFIDENCE line."""
    stripped = _CONFIDENCE_LINE_RE.sub("", answer or "").strip()
    if not stripped:
        return GradeResult(
            passed=False,
            score=0.0,
            detail="Answer is empty after stripping CONFIDENCE line",
        )
    return GradeResult(passed=True, score=1.0, detail="Answer is non-empty")


def qa_answer_concise(answer: str, max_words: int = 300) -> GradeResult:
    """Check that `answer` (CONFIDENCE line stripped) is under `max_words`
    words. The prompt targets ~250 words; 300 gives headroom."""
    stripped = _CONFIDENCE_LINE_RE.sub("", answer or "").strip()
    word_count = len(stripped.split())
    if word_count > max_words:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"Answer is {word_count} words, exceeds max_words={max_words}",
        )
    return GradeResult(
        passed=True, score=1.0, detail=f"Answer is {word_count} words (<= {max_words})"
    )


def qa_no_raw_latex_delimiters(answer: str) -> GradeResult:
    """Check `answer` has no bare `\\(` `\\)` `\\[` `\\]` LaTeX delimiters.
    `$...$`/`$$...$$` (KaTeX) are allowed and NOT flagged."""
    match = _RAW_LATEX_DELIMITER_RE.search(answer or "")
    if match:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"Found raw LaTeX delimiter '{match.group()}' (use $ delimiters instead)",
        )
    return GradeResult(passed=True, score=1.0, detail="No raw LaTeX delimiters found")


def qa_out_of_scope_refuses(answer: str, is_out_of_scope: bool) -> GradeResult:
    """For cases tagged out-of-scope, assert `answer` is the canned refusal
    path (src/api/handlers/qa.py's hardcoded out-of-scope response) rather
    than a full AI answer. Not applicable (auto-pass) for in-scope cases."""
    if not is_out_of_scope:
        return GradeResult(
            passed=True,
            score=1.0,
            detail="Not applicable: case is not tagged out-of-scope",
            applicable=False,
        )
    if _QA_OUT_OF_SCOPE_MARKER.lower() in (answer or "").lower():
        return GradeResult(
            passed=True,
            score=1.0,
            detail="Answer matches the canned out-of-scope refusal",
        )
    return GradeResult(
        passed=False,
        score=0.0,
        detail=(
            "Out-of-scope case did not receive the canned refusal "
            f"(expected substring '{_QA_OUT_OF_SCOPE_MARKER}')"
        ),
    )


# ---------------------------------------------------------------------------
# Practice graders (structural, operate on the parsed item dict)
# ---------------------------------------------------------------------------


def practice_question_quality(item_dict: Dict[str, Any]) -> GradeResult:
    """Mirror validate_practice_item's core thresholds: question_text >= 20
    chars, explanation >= 30 chars, correct_answer in A/B/C/D, exactly 4
    choices (src/services/practice/quality.py)."""
    issues = []

    question = (item_dict.get("question_text") or "").strip()
    if len(question) < 20:
        issues.append(f"question_text too short ({len(question)} < 20 chars)")

    explanation = (item_dict.get("explanation") or "").strip()
    if len(explanation) < 30:
        issues.append(f"explanation too short ({len(explanation)} < 30 chars)")

    correct_answer = (item_dict.get("correct_answer") or "").strip().upper()
    if correct_answer not in VALID_ANSWER_LETTERS:
        issues.append(f"correct_answer must be one of A/B/C/D, got {correct_answer!r}")

    choices = item_dict.get("choices")
    if not isinstance(choices, list) or len(choices) != 4:
        issues.append(f"expected exactly 4 choices, got {choices!r}")

    if issues:
        return GradeResult(passed=False, score=0.0, detail="; ".join(issues))
    return GradeResult(
        passed=True, score=1.0, detail="Question/explanation/answer quality OK"
    )


def practice_no_placeholder_distractors(item_dict: Dict[str, Any]) -> GradeResult:
    """Check that no choice is one of the known generic placeholder
    distractor strings from quality.py's fallback distractor generator (the
    bug this grader guards against)."""
    choices = item_dict.get("choices")
    if not isinstance(choices, list):
        return GradeResult(passed=False, score=0.0, detail="choices is not a list")

    for choice in choices:
        text = re.sub(r"^[A-D]\)\s*", "", str(choice)).strip()
        for pattern in _PLACEHOLDER_DISTRACTOR_PATTERNS:
            if pattern.match(text):
                return GradeResult(
                    passed=False,
                    score=0.0,
                    detail=f"Choice '{choice}' is a placeholder distractor",
                )
    return GradeResult(
        passed=True, score=1.0, detail="No placeholder distractors found"
    )


def practice_no_raw_latex(item_dict: Dict[str, Any]) -> GradeResult:
    """Practice JSON must be LaTeX-free entirely (prompts.py bans it so the
    response stays safe for json.loads); check all string fields."""
    for key in ("question_text", "answer_text", "explanation"):
        value = item_dict.get(key)
        if isinstance(value, str) and _RAW_LATEX_DELIMITER_RE.search(value):
            return GradeResult(
                passed=False,
                score=0.0,
                detail=f"Field '{key}' contains a raw LaTeX delimiter",
            )
    choices = item_dict.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, str) and _RAW_LATEX_DELIMITER_RE.search(choice):
                return GradeResult(
                    passed=False,
                    score=0.0,
                    detail=f"Choice '{choice}' contains a raw LaTeX delimiter",
                )
    return GradeResult(
        passed=True, score=1.0, detail="No raw LaTeX found in practice item"
    )


# ---------------------------------------------------------------------------
# Practice math ground-truth grader
# ---------------------------------------------------------------------------

# Maps a dataset-facing `math_topic` string to the MathGenerator method that
# produces it. src/services/practice/math_generator.py's generators draw
# from the global `random` module rather than a seeded local Random
# instance, so seeding `random` immediately before calling the same method
# with the same `difficulty` deterministically reproduces the same
# underlying equation/expression given the same seed. This lets us
# regenerate true ground truth with zero API/model calls: the dataset
# author picks a seed + topic + difficulty, calls MathGenerator once to
# record the produced item into the case's `expect`, and this grader
# replays the same seed/topic/difficulty and checks the recorded item's
# *labelled correct answer* against the regenerated ground truth.
#
# We deliberately do NOT compare the full `choices` list.
# `_generate_math_choices`/`_generate_expression_choices` funnel their
# distractors through `list(set(distractors))` before `random.shuffle`;
# for the string distractors used by `generate_expression_simplification`,
# Python's per-process string hash randomization (PYTHONHASHSEED) makes
# that set's iteration order - and therefore which letter ends up next to
# which value after the shuffle - not reproducible across processes, even
# with the same `random.seed()`. The distractor *values* stay the same,
# only their lettering shuffles differently. So instead of an exact
# choices-list match, we regenerate just the mathematically-correct value
# (computed before any distractor/shuffle logic runs, so it's unaffected
# by hash ordering) and verify the item's own labelled correct choice is
# equivalent to it - the "verify the stated correct answer solves the
# question" fallback the grader plan calls for when full regeneration
# isn't reliable.
_MATH_TOPIC_METHODS = {
    "linear_equation": "generate_linear_equation",
    "quadratic_equation": "generate_quadratic_equation",
    "expression_simplification": "generate_expression_simplification",
}

_CHOICE_PREFIX_RE = re.compile(r"^[A-D]\)\s*")


def _labelled_choice_text(item_dict: Dict[str, Any]) -> Optional[str]:
    """Return the choice text (prefix stripped) for item_dict's
    correct_answer letter, or None if it can't be found."""
    letter = (item_dict.get("correct_answer") or "").strip().upper()
    choices = item_dict.get("choices")
    if not isinstance(choices, list):
        return None
    for choice in choices:
        if str(choice).strip().upper().startswith(f"{letter})"):
            return _CHOICE_PREFIX_RE.sub("", str(choice)).strip()
    return None


def practice_math_answer_correct(
    topic: str, seed: int, item_dict: Dict[str, Any], operation: Optional[str] = None
) -> GradeResult:
    """Regenerate the SymPy-backed ground-truth value for `topic`/`seed`
    (and the item's own `difficulty`, defaulting to 5) and assert
    `item_dict`'s labelled correct choice is mathematically equivalent to
    it. See the module comment above `_MATH_TOPIC_METHODS` for why this
    checks the correct value rather than the full `choices` list.

    `operation` (only meaningful for topic="expression_simplification", one
    of "simplify"/"expand"/"factor") isn't recoverable from `item_dict` -
    `generate_expression_simplification` doesn't echo it back - so the
    dataset author must record it in the case's `expect` alongside
    `seed`/`math_topic` if a non-default operation was used to generate the
    item.
    """
    import random

    from sympy import simplify
    from sympy.parsing.sympy_parser import parse_expr

    from src.services.practice.math_generator import MathGenerator

    method_name = _MATH_TOPIC_METHODS.get(topic)
    if method_name is None:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"Unknown math_topic '{topic}'; expected one of {sorted(_MATH_TOPIC_METHODS)}",
        )

    item_choice_text = _labelled_choice_text(item_dict)
    if item_choice_text is None:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"Could not find a choice matching correct_answer={item_dict.get('correct_answer')!r}",
        )

    difficulty = item_dict.get("difficulty", 5)
    kwargs = {}
    if topic == "expression_simplification" and operation is not None:
        kwargs["operation"] = operation
    random.seed(seed)
    generator = MathGenerator()
    regenerated = getattr(generator, method_name)(difficulty=difficulty, **kwargs)
    ground_truth = regenerated.get("solution")

    try:
        if topic == "expression_simplification":
            item_value = parse_expr(item_choice_text)
        else:
            # "x = 2.8" -> "2.8"; choices are bare numbers, not "x = ...".
            item_value = parse_expr(
                re.sub(r"^[A-Za-z]\w*\s*=\s*", "", item_choice_text)
            )
        truth_value = parse_expr(str(ground_truth))
        matches = simplify(item_value - truth_value) == 0
    except Exception as e:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"Could not parse choice '{item_choice_text}' / ground truth '{ground_truth}': {e}",
        )

    if not matches:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=(
                f"Labelled correct choice '{item_choice_text}' does not match SymPy-regenerated "
                f"ground truth '{ground_truth}' (topic={topic}, seed={seed}, difficulty={difficulty})"
            ),
        )
    return GradeResult(
        passed=True,
        score=1.0,
        detail=f"Labelled correct choice matches SymPy-regenerated ground truth (topic={topic}, seed={seed})",
    )


# ---------------------------------------------------------------------------
# Summary graders
# ---------------------------------------------------------------------------

SummaryLike = Union[Dict[str, Any], str]


def _parse_summary_text(text: str):
    """Mirror the parsing in src/services/ai/summarizer.py's
    `generate_summary` for the (narrative, next_steps) split, used when a
    grader is given raw AI text instead of an already-assembled summary
    dict."""
    text = text or ""
    if "next steps" in text.lower() or "next:" in text.lower():
        # Single alternation - see summarizer.py's generate_summary for why
        # two separate re.split calls joined with `or` is broken (re.split
        # always returns a non-empty list, so the `or` never falls through).
        parts = re.split(r"next(?: steps)?:", text, maxsplit=1, flags=re.IGNORECASE)
        narrative = parts[0].strip()
        steps_text = parts[1].strip() if len(parts) > 1 else ""
        steps = (
            re.findall(r"[-•*]\s*(.+?)(?=\n|$)", steps_text)
            or re.findall(r"\d+\.\s*(.+?)(?=\n|$)", steps_text)
            or [s.strip() for s in steps_text.split("\n") if s.strip()]
        )
        next_steps = (
            steps[:3]
            if steps
            else ["Review session notes", "Complete practice problems"]
        )
    else:
        narrative = text
        next_steps = ["Review session notes", "Complete practice problems"]
    return narrative, next_steps


def summary_has_narrative(summary: SummaryLike) -> GradeResult:
    """Check for a non-empty narrative. Accepts either an assembled summary
    dict (`{"narrative": ...}`, mirroring the persisted Summary model) or
    raw AI text (parsed the same way generate_summary does)."""
    if isinstance(summary, dict):
        narrative = summary.get("narrative", "")
    else:
        narrative, _ = _parse_summary_text(summary)
    if not (narrative or "").strip():
        return GradeResult(passed=False, score=0.0, detail="Narrative is empty")
    return GradeResult(passed=True, score=1.0, detail="Narrative is non-empty")


def summary_has_next_steps(summary: SummaryLike) -> GradeResult:
    """Check 1-3 next-steps are present, parsed the same way as
    summary_has_narrative."""
    if isinstance(summary, dict):
        next_steps = summary.get("next_steps") or []
    else:
        _, next_steps = _parse_summary_text(summary)
    if not isinstance(next_steps, list) or not (1 <= len(next_steps) <= 3):
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"Expected 1-3 next steps, got {next_steps!r}",
        )
    return GradeResult(
        passed=True, score=1.0, detail=f"{len(next_steps)} next step(s) present"
    )


def summary_type_matches_duration(
    summary: SummaryLike, duration_min: int
) -> GradeResult:
    """Check summary_type is 'brief' when duration_min < 10, else 'normal'
    (mirrors generate_summary's threshold). Requires a summary dict with a
    `summary_type` key - raw text alone doesn't carry this field."""
    if not isinstance(summary, dict) or "summary_type" not in summary:
        return GradeResult(
            passed=True,
            score=1.0,
            detail="Not applicable: summary_type not available (requires an assembled summary dict)",
            applicable=False,
        )
    expected = "brief" if duration_min < 10 else "normal"
    actual = summary.get("summary_type")
    if actual != expected:
        return GradeResult(
            passed=False,
            score=0.0,
            detail=f"summary_type '{actual}' does not match expected '{expected}' for duration_min={duration_min}",
        )
    return GradeResult(
        passed=True,
        score=1.0,
        detail=f"summary_type '{actual}' matches duration_min={duration_min}",
    )
