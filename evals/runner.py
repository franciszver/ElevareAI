"""Eval runner skeleton.

Runs a list of `Case`s through a `generate_fn` (injectable — tests pass a
mock, live runs will pass a wrapper around `openai_client`) and grades the
output with the deterministic grader(s) registered for that case's surface.

E1 TODO: wire a real `generate_fn` per surface (QA/summary/practice) that
calls the actual prompt-building + `openai_client.chat_completion` code
paths, and route cases needing multiple prompt inputs (e.g. summary
transcripts) accordingly. `live_generate_stub` below is the placeholder
that live callers must replace.
"""

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from evals.graders.deterministic import GradeResult
from evals.schema import Case

GenerateFn = Callable[[Case], str]
GraderFn = Callable[[str], GradeResult]


@dataclass
class CaseResult:
    case_id: str
    surface: str
    passed: bool
    score: float
    detail: str
    latency_s: float
    tokens: Optional[int] = None


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

    If a surface has no graders registered, the case is recorded as passed
    with a "no grader registered" detail (E1 fills these in per surface).
    """
    generate = generate_fn or live_generate_stub

    results: List[CaseResult] = []
    for case in cases:
        start = time.perf_counter()
        output = generate(case)
        latency_s = time.perf_counter() - start

        graders = graders_by_surface.get(case.surface, [])
        if not graders:
            results.append(
                CaseResult(
                    case_id=case.id,
                    surface=case.surface,
                    passed=True,
                    score=1.0,
                    detail="no grader registered for this surface (E1 TODO)",
                    latency_s=latency_s,
                )
            )
            continue

        grades = [grader(output) for grader in graders]
        passed = all(g.passed for g in grades)
        score = sum(g.score for g in grades) / len(grades)
        detail = "; ".join(g.detail for g in grades)

        results.append(
            CaseResult(
                case_id=case.id,
                surface=case.surface,
                passed=passed,
                score=score,
                detail=detail,
                latency_s=latency_s,
            )
        )

    return results
