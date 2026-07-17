"""Eval report aggregation and rendering.

`build_report` groups `CaseResult`s by surface and computes pass rate + mean
score over APPLICABLE cases only — cases with no grader registered for their
surface, or whose registered graders all produced a not-applicable
`GradeResult` (`applicable=False`, see `evals/runner.py::aggregate_grades`),
are tallied separately as `ungraded_count` and excluded from
`pass_rate`/`mean_score` so an unverified surface can't look falsely green.
`render_markdown` turns that into a small human-readable table. E2 adds
`build_judge_report`/`render_markdown_with_judge` alongside this for the
LLM-judge quality dimension (see `evals/judge.py`) — deterministic pass-rate
and judge mean-score are kept as two separate dimensions, never blended.
E4 will extend `build_report` with latency/token stats and a baseline-delta
comparison; kept simple here on purpose.
"""

from typing import Dict, List, Optional

from evals.judge import JudgeResult
from evals.runner import CaseResult
from evals.schema import Case


def build_report(results: List[CaseResult]) -> Dict[str, Dict[str, Optional[float]]]:
    """Aggregate CaseResults per surface: count, graded_count, ungraded_count,
    pass_rate, mean_score. `pass_rate` and `mean_score` are computed over
    applicable cases only (see module docstring); `pass_rate` is None if
    graded_count is 0."""
    by_surface: Dict[str, List[CaseResult]] = {}
    for result in results:
        by_surface.setdefault(result.surface, []).append(result)

    report: Dict[str, Dict[str, Optional[float]]] = {}
    for surface, surface_results in by_surface.items():
        count = len(surface_results)
        graded_results = [r for r in surface_results if r.applicable]
        graded_count = len(graded_results)
        ungraded_count = count - graded_count
        passed = sum(1 for r in graded_results if r.passed)
        report[surface] = {
            "count": count,
            "graded_count": graded_count,
            "ungraded_count": ungraded_count,
            "pass_rate": (passed / graded_count) if graded_count else None,
            "mean_score": (
                (sum(r.score for r in graded_results) / graded_count)
                if graded_count
                else None
            ),
        }
    return report


def build_judge_report(
    cases: List[Case], judge_results: Dict[str, JudgeResult]
) -> Dict[str, Dict[str, Optional[float]]]:
    """Aggregate JudgeResults per surface: judge_count, judge_applicable_count,
    judge_mean_score. Mirrors `build_report`'s applicable-based exclusion, but
    for the LLM-judge QUALITY dimension rather than the deterministic
    structural-pass dimension — kept as a separate report so a case can pass
    structure while scoring low on quality, or vice versa."""
    by_surface: Dict[str, List[JudgeResult]] = {}
    for case in cases:
        result = judge_results.get(case.id)
        if result is not None:
            by_surface.setdefault(case.surface, []).append(result)

    report: Dict[str, Dict[str, Optional[float]]] = {}
    for surface, surface_results in by_surface.items():
        judge_count = len(surface_results)
        applicable_results = [r for r in surface_results if r.applicable]
        applicable_count = len(applicable_results)
        report[surface] = {
            "judge_count": judge_count,
            "judge_applicable_count": applicable_count,
            "judge_mean_score": (
                (sum(r.score for r in applicable_results) / applicable_count)
                if applicable_count
                else None
            ),
        }
    return report


def render_markdown(report: Dict[str, Dict[str, Optional[float]]]) -> str:
    """Render a report dict as a small markdown table."""
    lines = [
        "| Surface | Count | Graded | Ungraded | Pass Rate | Mean Score |",
        "|---|---|---|---|---|---|",
    ]
    total_ungraded = 0
    for surface in sorted(report):
        stats = report[surface]
        total_ungraded += stats["ungraded_count"]
        pass_rate = (
            f"{stats['pass_rate']:.0%}" if stats["pass_rate"] is not None else "N/A"
        )
        mean_score = (
            f"{stats['mean_score']:.2f}" if stats["mean_score"] is not None else "N/A"
        )
        lines.append(
            f"| {surface} | {stats['count']} | {stats['graded_count']} | "
            f"{stats['ungraded_count']} | {pass_rate} | {mean_score} |"
        )
    lines.append("")
    lines.append(f"Ungraded cases (no grader registered): {total_ungraded}")
    return "\n".join(lines)


def render_markdown_with_judge(
    report: Dict[str, Dict[str, Optional[float]]],
    judge_report: Dict[str, Dict[str, Optional[float]]],
) -> str:
    """Render `build_report`'s deterministic pass-rate table alongside
    `build_judge_report`'s LLM-judge quality-mean-score, one row per surface,
    clearly labeled as two separate dimensions (a case can pass structure but
    score low on quality, or vice versa — never blended into one number)."""

    def fmt(value: Optional[float], spec: str) -> str:
        return format(value, spec) if value is not None else "N/A"

    lines = [
        "| Surface | Count | Pass Rate (deterministic) | Mean Score (deterministic) | Judge Mean Score (quality) |",
        "|---|---|---|---|---|",
    ]
    for surface in sorted(set(report) | set(judge_report)):
        stats = report.get(surface, {})
        judge_stats = judge_report.get(surface, {})
        pass_rate = fmt(stats.get("pass_rate"), ".0%")
        mean_score = fmt(stats.get("mean_score"), ".2f")
        judge_mean_score = fmt(judge_stats.get("judge_mean_score"), ".2f")
        lines.append(
            f"| {surface} | {stats.get('count', 0)} | {pass_rate} | {mean_score} | "
            f"{judge_mean_score} |"
        )
    return "\n".join(lines)
