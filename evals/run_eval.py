"""Offline eval entry point: grade the real fixtures, report incl.
cost/latency, and gate on regression vs the committed baseline (Phase E4).

    python -m evals.run_eval                 # grade + report + regression gate
    python -m evals.run_eval --update-baseline  # regenerate evals/baselines/baseline.json

Zero API calls: grades `evals/fixtures/sample_outputs.json` +
`evals/fixtures/guardrail_outputs.json` via
`evals/grade_fixtures.py::grade_fixture_file`, exactly like
`evals/baselines/__init__.py::build_baseline` does for the snapshot itself.

Exit code: nonzero if `evals.regression.compare_to_baseline` flags a
regression, so this can gate CI (E5).
"""

import argparse
import sys

from evals.baselines import BASELINE_PATH, load_baseline, snapshot_baseline
from evals.grade_fixtures import (
    DEFAULT_FIXTURES,
    GUARDRAIL_FIXTURES,
    grade_fixture_files,
)
from evals.regression import compare_to_baseline, render_regression_markdown
from evals.report import (
    build_perf_report,
    build_report,
    render_markdown,
    render_perf_markdown,
)

FIXTURES = [DEFAULT_FIXTURES, GUARDRAIL_FIXTURES]


def grade_all_fixtures():
    return grade_fixture_files(FIXTURES)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Grade the real eval fixtures offline, print the report + "
            "perf stats, and gate on regression vs the committed baseline."
        )
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Regenerate evals/baselines/baseline.json from the current fixtures instead of comparing against it.",
    )
    args = parser.parse_args()

    if args.update_baseline:
        baseline = snapshot_baseline()
        print(f"Baseline snapshot written to {BASELINE_PATH}")
        print(f"Surfaces: {sorted(baseline['surfaces'])}")
        return 0

    results = grade_all_fixtures()
    report = build_report(results)
    perf_report = build_perf_report(results)

    print(f"Graded {len(results)} captured case(s) from {[str(p) for p in FIXTURES]}\n")
    print("## Aggregate Report\n")
    print(render_markdown(report))
    print()
    print("## Cost/Latency\n")
    print(render_perf_markdown(perf_report))
    print()

    baseline = load_baseline(BASELINE_PATH)
    regression_result = compare_to_baseline(report, perf_report, baseline)
    print(render_regression_markdown(regression_result))

    return 1 if regression_result.regressed else 0


if __name__ == "__main__":
    sys.exit(main())
