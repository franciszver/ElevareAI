"""Eval report aggregation and rendering.

`build_report` groups `CaseResult`s by surface and computes pass rate + mean
score over GRADED cases only — cases with no grader registered for their
surface (`graded=False`) are tallied separately as `ungraded_count` and
excluded from `pass_rate`/`mean_score` so an unverified surface can't look
falsely green. `render_markdown` turns that into a small human-readable
table. E4 will extend `build_report` with latency/token stats and a
baseline-delta comparison; kept simple here on purpose.
"""

from typing import Dict, List, Optional

from evals.runner import CaseResult


def build_report(results: List[CaseResult]) -> Dict[str, Dict[str, Optional[float]]]:
    """Aggregate CaseResults per surface: count, graded_count, ungraded_count,
    pass_rate, mean_score. `pass_rate` and `mean_score` are computed over
    graded cases only; `pass_rate` is None if graded_count is 0."""
    by_surface: Dict[str, List[CaseResult]] = {}
    for result in results:
        by_surface.setdefault(result.surface, []).append(result)

    report: Dict[str, Dict[str, Optional[float]]] = {}
    for surface, surface_results in by_surface.items():
        count = len(surface_results)
        graded_results = [r for r in surface_results if r.graded]
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
