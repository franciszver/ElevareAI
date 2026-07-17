"""Regression detection against a committed baseline (Phase E4).

Compares a freshly-graded `build_report`/`build_perf_report` pair against
`evals/baselines/baseline.json` (see `evals/baselines/__init__.py` for the
snapshot schema) and flags a surface as regressed per the locked plan in
`evals/README.md`: "fail if a surface pass-rate drops >10 points OR p95
latency >1.5x baseline".

Only the DETERMINISTIC pass_rate and latency stats are compared here — judge
scores are advisory (re-judging needs a live model/subagent judge, not
available in an offline/CI gate) and are intentionally NOT part of this hard
regression check.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

DEFAULT_PASS_RATE_DROP_THRESHOLD = 0.10
DEFAULT_LATENCY_RATIO_THRESHOLD = 1.5


@dataclass
class SurfaceRegression:
    pass_rate_delta: Any  # Optional[float]: current - baseline (negative = worse)
    latency_p95_ratio: Any  # Optional[float]: current / baseline
    regressed: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class RegressionResult:
    surfaces: Dict[str, SurfaceRegression]
    regressed: bool
    notes: List[str] = field(default_factory=list)


def _compare_surface(
    current_stats: Dict[str, Any],
    current_perf: Dict[str, Any],
    baseline_stats: Dict[str, Any],
    baseline_perf: Dict[str, Any],
    pass_rate_drop_threshold: float,
    latency_ratio_threshold: float,
) -> SurfaceRegression:
    reasons: List[str] = []

    pass_rate_delta = None
    current_pass_rate = current_stats.get("pass_rate")
    baseline_pass_rate = baseline_stats.get("pass_rate")
    if current_pass_rate is not None and baseline_pass_rate is not None:
        pass_rate_delta = current_pass_rate - baseline_pass_rate
        if pass_rate_delta < -pass_rate_drop_threshold:
            reasons.append(
                f"pass_rate dropped {abs(pass_rate_delta):.1%} "
                f"(baseline {baseline_pass_rate:.1%} -> current {current_pass_rate:.1%}, "
                f"threshold {pass_rate_drop_threshold:.0%})"
            )

    latency_p95_ratio = None
    current_p95 = current_perf.get("latency_p95_s")
    baseline_p95 = baseline_perf.get("latency_p95_s")
    if current_p95 is not None and baseline_p95 is not None and baseline_p95 > 0:
        latency_p95_ratio = current_p95 / baseline_p95
        if latency_p95_ratio > latency_ratio_threshold:
            reasons.append(
                f"p95 latency {latency_p95_ratio:.2f}x baseline "
                f"(baseline {baseline_p95:.3f}s -> current {current_p95:.3f}s, "
                f"threshold {latency_ratio_threshold}x)"
            )

    return SurfaceRegression(
        pass_rate_delta=pass_rate_delta,
        latency_p95_ratio=latency_p95_ratio,
        regressed=bool(reasons),
        reasons=reasons,
    )


def compare_to_baseline(
    current_report: Dict[str, Dict[str, Any]],
    current_perf_report: Dict[str, Dict[str, Any]],
    baseline: Dict[str, Any],
    pass_rate_drop_threshold: float = DEFAULT_PASS_RATE_DROP_THRESHOLD,
    latency_ratio_threshold: float = DEFAULT_LATENCY_RATIO_THRESHOLD,
) -> RegressionResult:
    """Compare current deterministic report + perf report against
    `baseline` (the dict loaded from `evals/baselines/baseline.json`, see
    `evals/baselines/__init__.py::load_baseline`).

    A surface regresses if EITHER:
      - its pass_rate dropped by more than `pass_rate_drop_threshold`
        (default 10 points) vs baseline, OR
      - its latency p95 exceeds `latency_ratio_threshold`x (default 1.5x)
        the baseline p95.

    A surface present in `current_report`/`current_perf_report` but absent
    from the baseline (new surface) or vice versa (missing surface, e.g. a
    fixture was removed) is noted in `RegressionResult.notes` rather than
    treated as a hard failure — there's nothing to compare against.
    """
    baseline_surfaces: Dict[str, Dict[str, Any]] = baseline.get("surfaces", {})

    surfaces: Dict[str, SurfaceRegression] = {}
    notes: List[str] = []

    current_surface_names = set(current_report) | set(current_perf_report)
    all_surface_names = current_surface_names | set(baseline_surfaces)

    for surface in sorted(all_surface_names):
        if surface not in baseline_surfaces:
            notes.append(
                f"'{surface}' has no baseline entry (new surface) - not compared"
            )
            continue
        if surface not in current_surface_names:
            notes.append(
                f"'{surface}' is in the baseline but missing from the current run "
                "- not compared"
            )
            continue

        surfaces[surface] = _compare_surface(
            current_report.get(surface, {}),
            current_perf_report.get(surface, {}),
            baseline_surfaces[surface].get("deterministic", {}),
            baseline_surfaces[surface].get("perf", {}),
            pass_rate_drop_threshold,
            latency_ratio_threshold,
        )

    regressed = any(s.regressed for s in surfaces.values())
    return RegressionResult(surfaces=surfaces, regressed=regressed, notes=notes)


def render_regression_markdown(result: RegressionResult) -> str:
    """Render a clear PASS/REGRESSION verdict with per-surface deltas and
    reasons."""
    verdict = "REGRESSION" if result.regressed else "PASS"
    lines = [f"## Regression check: {verdict}", ""]
    lines.append("| Surface | Pass Rate Delta | Latency p95 Ratio | Status |")
    lines.append("|---|---|---|---|")
    for surface in sorted(result.surfaces):
        s = result.surfaces[surface]
        delta = f"{s.pass_rate_delta:+.1%}" if s.pass_rate_delta is not None else "N/A"
        ratio = (
            f"{s.latency_p95_ratio:.2f}x" if s.latency_p95_ratio is not None else "N/A"
        )
        status = "REGRESSED" if s.regressed else "ok"
        lines.append(f"| {surface} | {delta} | {ratio} | {status} |")

    if result.regressed:
        lines.append("")
        lines.append("### Reasons")
        for surface in sorted(result.surfaces):
            s = result.surfaces[surface]
            for reason in s.reasons:
                lines.append(f"- **{surface}**: {reason}")

    if result.notes:
        lines.append("")
        lines.append("### Notes")
        for note in result.notes:
            lines.append(f"- {note}")

    return "\n".join(lines)
