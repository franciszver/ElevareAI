"""Grade already-captured production outputs against the E1 deterministic
graders (zero API calls).

Reads `evals/fixtures/sample_outputs.json` (real `openai/gpt-oss-20b:free`
outputs captured for qa/practice/summary), maps each captured record to a
`Case`, and runs the existing `graders_by_surface` registry (reusing
`evals.runner._call_grader` per-grader, same calling convention as
`run_cases`) against the stored output - no `generate_fn`/API call involved.
Prints a per-case breakdown (which graders failed and why, which are
not-applicable) plus an aggregate report via `evals.report`.

Some graders need per-case data a raw captured completion doesn't carry
(e.g. practice math ground-truth needs `seed`/`math_topic`; summary's
`summary_type` is assigned by post-processing code, not present in the raw
AI text this fixture captures). Those graders report `GradeResult.applicable
=False` (see `evals/graders/deterministic.py`) and are excluded from
pass/score by `evals/runner.py::aggregate_grades` - the same shared
aggregation `run_cases` uses - rather than counted as failures: a grader
that can't apply isn't a passing grader either.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from evals.graders.deterministic import GradeResult
from evals.graders.registry import graders_by_surface
from evals.report import build_report, render_markdown
from evals.runner import CaseResult, _call_grader, aggregate_grades
from evals.schema import Case

DEFAULT_FIXTURES = Path(__file__).parent / "fixtures" / "sample_outputs.json"


def load_fixture_records(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["captured_calls"]


def record_to_case(record: Dict[str, Any]) -> Case:
    """Map a captured fixture record to a Case the registry graders expect.

    Fixture inputs use production field names (e.g. `is_out_of_scope`,
    `session_duration_minutes`); the registry adapters read `case.expect`
    ("out_of_scope") and `case.input` ("duration_minutes"). We only add
    aliases here - we don't fabricate data the capture doesn't have (e.g.
    math `seed`/`math_topic`, which the practice math grader then correctly
    treats as not-applicable).
    """
    surface = record["surface"]
    raw_input = dict(record["input"])
    expect: Dict[str, Any] = {}

    if surface == "qa":
        expect["out_of_scope"] = bool(raw_input.get("is_out_of_scope", False))
    if surface == "summary" and "session_duration_minutes" in raw_input:
        raw_input.setdefault("duration_minutes", raw_input["session_duration_minutes"])

    return Case(
        id=record["id"], surface=surface, input=raw_input, expect=expect or None
    )


def grade_case(case: Case, output: str) -> List[Dict[str, Any]]:
    """Run each grader registered for `case.surface` individually against
    `output`, tagging each result as applicable/not-applicable via the
    grader's own `GradeResult.applicable` field."""
    breakdown = []
    for grader in graders_by_surface.get(case.surface, []):
        result = _call_grader(grader, output, case)
        breakdown.append(
            {
                "name": getattr(grader, "__name__", repr(grader)),
                "passed": result.passed,
                "score": result.score,
                "detail": result.detail,
                "na": not result.applicable,
            }
        )
    return breakdown


def _split_applicable(
    breakdown: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split a grade_case breakdown into (applicable, not-applicable) grader
    results."""
    applicable = [g for g in breakdown if not g["na"]]
    na = [g for g in breakdown if g["na"]]
    return applicable, na


def to_case_result(case: Case, breakdown: List[Dict[str, Any]]) -> CaseResult:
    """Aggregate a grade_case breakdown into a CaseResult via the same
    `aggregate_grades` helper `evals/runner.py::run_cases` uses, so both
    aggregation paths share one notion of "not applicable"."""
    grades = [
        GradeResult(
            passed=g["passed"],
            score=g["score"],
            detail=g["detail"],
            applicable=not g["na"],
        )
        for g in breakdown
    ]
    passed, score, detail, applicable = aggregate_grades(grades)
    return CaseResult(
        case_id=case.id,
        surface=case.surface,
        passed=passed,
        score=score,
        detail=detail,
        latency_s=0.0,
        graded=bool(breakdown),
        applicable=applicable,
    )


def render_per_case_table(
    records: List[Dict[str, Any]],
    breakdowns_by_id: Dict[str, List[Dict[str, Any]]],
) -> str:
    lines = [
        "| ID | Surface | Latency (s) | Result | Failed Graders | N/A Graders |",
        "|---|---|---|---|---|---|",
    ]
    for record in records:
        breakdown = breakdowns_by_id[record["id"]]
        applicable, na = _split_applicable(breakdown)
        failed = [g for g in applicable if not g["passed"]]

        result = "N/A" if not applicable else ("PASS" if not failed else "FAIL")
        failed_str = "; ".join(f"{g['name']} ({g['detail']})" for g in failed) or "-"
        na_str = "; ".join(g["name"] for g in na) or "-"

        lines.append(
            f"| {record['id']} | {record['surface']} | {record['latency_s']} | "
            f"{result} | {failed_str} | {na_str} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grade captured fixture outputs with the E1 deterministic graders (no API calls)."
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES,
        help="Path to a captured-outputs fixtures JSON file.",
    )
    args = parser.parse_args()

    records = load_fixture_records(args.fixtures)
    cases = [record_to_case(record) for record in records]

    breakdowns_by_id = {
        case.id: grade_case(case, record["output"])
        for case, record in zip(cases, records)
    }
    results = [to_case_result(case, breakdowns_by_id[case.id]) for case in cases]

    print(f"Graded {len(records)} captured case(s) from {args.fixtures}\n")
    print("## Per-Case Results\n")
    print(render_per_case_table(records, breakdowns_by_id))
    print()
    print("## Aggregate Report\n")
    print(render_markdown(build_report(results)))


if __name__ == "__main__":
    main()
