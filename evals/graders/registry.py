"""Adapts the pure `evals/graders/deterministic.py` grader functions to the
runner's per-case calling convention and wires them into `graders_by_surface`.

The deterministic graders are pure functions over plain values (a raw output
string, or a parsed practice-item dict) - they know nothing about `Case`.
Some of them need extra per-case hints that only `Case.expect`/`Case.input`
carry (QA's `out_of_scope` flag, practice math's `math_topic`/`seed`,
summary's `duration_minutes`). The adapters below read those fields and are
themselves `(output, case) -> GradeResult` callables, which `run_cases`
(see `evals/runner.py::_call_grader`) detects by their 2-parameter arity and
calls accordingly.

Convention for `expect`/`input` fields consumed here:
  - qa:       expect.out_of_scope (bool, default False)
  - practice: expect.math_topic (str) + expect.seed (int) - both required
              together to trigger `practice_math_answer_correct`; omitted
              for non-math practice items (that grader then auto-passes as
              not-applicable).
  - summary:  input.duration_minutes (int) - drives
              `summary_type_matches_duration`.

Practice/summary graders that operate on a parsed dict rather than the raw
output string parse the output as JSON here; a parse failure is reported as
a grading failure with a clear detail message rather than raising.
"""

import json
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

from evals.graders import deterministic as det
from evals.schema import Case

GraderFn = Any  # Callable[[str], GradeResult] | Callable[[str, Case], GradeResult]


@lru_cache(maxsize=128)
def _parse_json_object(
    output: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[det.GradeResult]]:
    """Parse `output` as a JSON object. Returns (item, None) on success, or
    (None, failing GradeResult) if `output` isn't valid JSON / not an object.

    Cached: the 3 `_on_parsed_item`-wrapped graders plus the math
    ground-truth adapter all call this with the same output string per
    practice case, so caching avoids re-parsing identical JSON repeatedly
    within a grading pass."""
    try:
        item = json.loads(output)
    except json.JSONDecodeError as e:
        return None, det.GradeResult(
            passed=False, score=0.0, detail=f"Invalid JSON: {e}"
        )
    if not isinstance(item, dict):
        return None, det.GradeResult(
            passed=False, score=0.0, detail="Parsed JSON is not an object"
        )
    return item, None


@lru_cache(maxsize=128)
def _summary_like(output: str):
    """A summary case's example output is either a JSON object (an assembled
    summary dict with narrative/next_steps/summary_type) or raw text (an
    unassembled AI response). Try JSON first; fall back to the raw string so
    `_parse_summary_text`-based graders still work.

    Cached: all 3 summary graders call this with the same output string per
    case."""
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return output
    return parsed if isinstance(parsed, dict) else output


# ---------------------------------------------------------------------------
# QA adapters
# ---------------------------------------------------------------------------


def _qa_confidence_line_if_applicable(output: str, case: Case) -> det.GradeResult:
    """Out-of-scope cases get the fixed canned refusal (no CONFIDENCE line by
    design - see src/api/handlers/qa.py); skip this check for them."""
    if (case.expect or {}).get("out_of_scope", False):
        return det.GradeResult(
            passed=True,
            score=1.0,
            detail="Not applicable: out-of-scope refusal has no CONFIDENCE line by design",
        )
    return det.confidence_line_present(output)


def _qa_out_of_scope_refuses(output: str, case: Case) -> det.GradeResult:
    is_out_of_scope = bool((case.expect or {}).get("out_of_scope", False))
    return det.qa_out_of_scope_refuses(output, is_out_of_scope)


def _qa_answer_concise(output: str, case: Case) -> det.GradeResult:
    """`qa_answer_concise`'s second parameter is `max_words` (a default,
    not `case`) - wrap it so the runner's arity-based dispatch
    (`evals/runner.py::_call_grader`) doesn't mistake it for a
    `(output, case)`-style grader and pass a `Case` where a word-count
    limit is expected."""
    return det.qa_answer_concise(output)


# ---------------------------------------------------------------------------
# Practice adapters
# ---------------------------------------------------------------------------


def _on_parsed_item(
    grader: Callable[[Dict[str, Any]], det.GradeResult],
) -> Callable[[str, Case], det.GradeResult]:
    """Wrap a practice-item grader (which expects a parsed dict) as a
    `(output, case)` adapter that parses `output` as JSON first, surfacing a
    parse failure as a grading failure instead of raising."""

    def adapter(output: str, case: Case) -> det.GradeResult:
        item, error = _parse_json_object(output)
        if error:
            return error
        return grader(item)

    return adapter


_practice_question_quality = _on_parsed_item(det.practice_question_quality)
_practice_no_placeholder_distractors = _on_parsed_item(
    det.practice_no_placeholder_distractors
)
_practice_no_raw_latex = _on_parsed_item(det.practice_no_raw_latex)


def _practice_math_answer_correct_if_applicable(
    output: str, case: Case
) -> det.GradeResult:
    expect = case.expect or {}
    topic = expect.get("math_topic")
    seed = expect.get("seed")
    if topic is None or seed is None:
        return det.GradeResult(
            passed=True,
            score=1.0,
            detail="Not applicable: case has no math_topic/seed in expect",
        )
    item, error = _parse_json_object(output)
    if error:
        return error
    operation = expect.get("operation")
    return det.practice_math_answer_correct(topic, seed, item, operation=operation)


# ---------------------------------------------------------------------------
# Summary adapters
# ---------------------------------------------------------------------------


def _summary_has_narrative(output: str, case: Case) -> det.GradeResult:
    return det.summary_has_narrative(_summary_like(output))


def _summary_has_next_steps(output: str, case: Case) -> det.GradeResult:
    return det.summary_has_next_steps(_summary_like(output))


def _summary_type_matches_duration(output: str, case: Case) -> det.GradeResult:
    duration_min = case.input.get("duration_minutes")
    return det.summary_type_matches_duration(_summary_like(output), duration_min)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

graders_by_surface: Dict[str, List[GraderFn]] = {
    "qa": [
        _qa_confidence_line_if_applicable,
        det.qa_answer_nonempty,
        _qa_answer_concise,
        det.qa_no_raw_latex_delimiters,
        _qa_out_of_scope_refuses,
    ],
    "practice": [
        det.practice_json_valid,
        _practice_question_quality,
        _practice_no_placeholder_distractors,
        _practice_no_raw_latex,
        _practice_math_answer_correct_if_applicable,
    ],
    "summary": [
        _summary_has_narrative,
        _summary_has_next_steps,
        _summary_type_matches_duration,
    ],
}
