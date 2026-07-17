"""Eval runner skeleton.

Runs a list of `Case`s through a `generate_fn` (injectable — tests pass a
mock, live runs will pass a wrapper around `openai_client`) and grades the
output with the deterministic grader(s) registered for that case's surface.

E1 TODO: wire a real `generate_fn` per surface (QA/summary/practice) that
calls the actual prompt-building + `openai_client.chat_completion` code
paths, and route cases needing multiple prompt inputs (e.g. summary
transcripts) accordingly. `live_generate_stub` below is the placeholder
that live callers must replace.

Grader calling convention: a grader may accept either `(output)` (E0-style,
still supported) or `(output, case)` - the second form lets a grader read
extra per-case grading hints from `case.expect`/`case.input` (e.g. QA's
out-of-scope flag, practice math's seed/topic, summary's duration). See
`evals/graders/registry.py` for the adapters that implement this for the
E1 graders.
"""

import inspect
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Union

from evals.graders.deterministic import GradeResult
from evals.schema import Case

GenerateFn = Callable[[Case], str]
GraderFn = Union[Callable[[str], GradeResult], Callable[[str, Case], GradeResult]]


@lru_cache(maxsize=None)
def _grader_arity(grader: GraderFn) -> int:
    """A grader function's parameter count never changes between calls, so
    this is cached rather than re-derived via `inspect.signature` for every
    (case, grader) pair `_call_grader` is invoked on."""
    try:
        return len(inspect.signature(grader).parameters)
    except (TypeError, ValueError):
        return 1


def _call_grader(grader: GraderFn, output: str, case: Case) -> GradeResult:
    """Call `grader` with `(output, case)` if it accepts 2+ params, else the
    original E0 `(output)` form, so old single-arg graders keep working."""
    if _grader_arity(grader) >= 2:
        return grader(output, case)
    return grader(output)


@dataclass
class CaseResult:
    case_id: str
    surface: str
    passed: Optional[bool]
    score: float
    detail: str
    latency_s: float
    tokens: Optional[int] = None
    graded: bool = True
    # False when no grader for this surface produced an applicable result
    # (either no grader was registered, or every registered grader's
    # GradeResult was applicable=False). Excluded from build_report's
    # pass-rate/mean-score, same as grade_fixtures.py's aggregation.
    applicable: bool = True


def aggregate_grades(
    grades: List[GradeResult],
) -> "tuple[Optional[bool], float, str, bool]":
    """Aggregate a case's GradeResults into (passed, score, detail, applicable),
    excluding applicable=False results from the pass/score computation. The
    single shared notion of "not applicable" used by both `run_cases` below
    and `evals/grade_fixtures.py`'s `to_case_result`.

    Returns (None, 0.0, "No applicable graders for this case", False) if no
    grade is applicable.
    """
    applicable_grades = [g for g in grades if g.applicable]
    if not applicable_grades:
        return None, 0.0, "No applicable graders for this case", False
    passed = all(g.passed for g in applicable_grades)
    score = sum(g.score for g in applicable_grades) / len(applicable_grades)
    detail = "; ".join(g.detail for g in applicable_grades)
    return passed, score, detail, True


def live_generate_stub(case: Case) -> str:
    """Placeholder for the real generate_fn. E1 will replace this with a
    wrapper that builds the surface-appropriate prompt and calls
    `openai_client.chat_completion`. Not used by the harness self-tests,
    which always inject their own mock generate_fn."""
    raise NotImplementedError(
        f"live_generate_stub: no real generator wired yet for surface '{case.surface}' "
        "(E1 TODO) - pass an explicit generate_fn"
    )


def run_cases(
    cases: List[Case],
    graders_by_surface: Dict[str, List[GraderFn]],
    generate_fn: Optional[GenerateFn] = None,
) -> List[CaseResult]:
    """Run `cases` through `generate_fn`, grading each output with the
    grader(s) registered for its surface in `graders_by_surface`.

    If a surface has no graders registered, the case is recorded as ungraded
    (graded=False, passed=None) rather than a fabricated pass (E1 fills these
    in per surface).
    """
    generate = generate_fn or live_generate_stub

    results: List[CaseResult] = []
    for case in cases:
        start = time.perf_counter()
        output = generate(case)
        latency_s = time.perf_counter() - start

        graders = graders_by_surface.get(case.surface, [])
        if graders:
            grades = [_call_grader(grader, output, case) for grader in graders]
            passed, score, detail, applicable = aggregate_grades(grades)
            graded = True
        else:
            passed, score = None, 0.0
            detail = f"no grader registered for surface '{case.surface}'"
            graded = False
            applicable = False

        results.append(
            CaseResult(
                case_id=case.id,
                surface=case.surface,
                passed=passed,
                score=score,
                detail=detail,
                latency_s=latency_s,
                graded=graded,
                applicable=applicable,
            )
        )

    return results
