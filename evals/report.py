"""Eval report aggregation and rendering.

`build_report` groups `CaseResult`s by surface and computes pass rate + mean
score. `render_markdown` turns that into a small human-readable table. E4
will extend `build_report` with latency/token stats and a baseline-delta
comparison; kept simple here on purpose.
"""

from typing import Dict, List

from evals.runner import CaseResult


def build_report(results: List[CaseResult]) -> Dict[str, Dict[str, float]]:
    """Aggregate CaseResults per surface: count, pass_rate, mean_score."""
    by_surface: Dict[str, List[CaseResult]] = {}
    for result in results:
        by_surface.setdefault(result.surface, []).append(result)

    report: Dict[str, Dict[str, float]] = {}
    for surface, surface_results in by_surface.items():
        count = len(surface_results)
        passed = sum(1 for r in surface_results if r.passed)
        report[surface] = {
            "count": count,
            "pass_rate": passed / count,
            "mean_score": sum(r.score for r in surface_results) / count,
        }
    return report


def render_markdown(report: Dict[str, Dict[str, float]]) -> str:
    """Render a report dict as a small markdown table."""
    lines = [
        "| Surface | Count | Pass Rate | Mean Score |",
        "|---|---|---|---|",
    ]
    for surface in sorted(report):
        stats = report[surface]
        lines.append(
            f"| {surface} | {stats['count']} | {stats['pass_rate']:.0%} | {stats['mean_score']:.2f} |"
        )
    return "\n".join(lines)
