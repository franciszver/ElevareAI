"""
Eval Harness Regression/Perf Tests (Phase E4)

Covers latency aggregation (evals/report.py's percentile/build_perf_report),
baseline load/save round-trip (evals/baselines), and regression detection
(evals/regression.py). Zero API calls throughout.
"""

import json

import pytest

from evals.baselines import build_baseline, load_baseline, save_baseline
from evals.regression import (
    DEFAULT_LATENCY_RATIO_THRESHOLD,
    DEFAULT_PASS_RATE_DROP_THRESHOLD,
    RegressionResult,
    compare_to_baseline,
    render_regression_markdown,
)
from evals.report import build_perf_report, percentile, render_perf_markdown
from evals.runner import CaseResult


def _case_result(surface, latency_s, tokens=None, finish_reason="stop", passed=True):
    return CaseResult(
        case_id=f"{surface}-{latency_s}",
        surface=surface,
        passed=passed,
        score=1.0 if passed else 0.0,
        detail="ok",
        latency_s=latency_s,
        tokens=tokens,
        finish_reason=finish_reason,
    )


def _baseline(pass_rate=0.9, latency_p95_s=10.0, surfaces=("qa",)):
    return {
        "schema_version": 1,
        "captured_from": {"fixtures": [], "model": "x", "date": "2026-07-16"},
        "surfaces": {
            surface: {
                "deterministic": {"pass_rate": pass_rate, "mean_score": pass_rate},
                "perf": {
                    "latency_p95_s": latency_p95_s,
                    "latency_p50_s": latency_p95_s / 2,
                },
            }
            for surface in surfaces
        },
    }


class TestPercentile:
    def test_p50_and_p95_on_known_list(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert percentile(values, 50) == 5
        assert percentile(values, 95) == 10

    def test_p50_single_value(self):
        assert percentile([42.0], 50) == 42.0
        assert percentile([42.0], 95) == 42.0

    def test_empty_list_returns_zero(self):
        assert percentile([], 50) == 0.0

    def test_unsorted_input_still_correct(self):
        values = [30, 10, 20]
        assert percentile(values, 50) == 20


class TestBuildPerfReport:
    def test_latency_and_tokens_aggregated_per_surface(self):
        results = [
            _case_result("qa", 1.0, tokens=100),
            _case_result("qa", 2.0, tokens=200),
            _case_result("qa", 3.0, tokens=300),
        ]
        report = build_perf_report(results)
        assert report["qa"]["count"] == 3
        assert report["qa"]["latency_p50_s"] == 2.0
        assert report["qa"]["latency_p95_s"] == 3.0
        assert report["qa"]["mean_tokens"] == pytest.approx(200.0)
        assert report["qa"]["truncated_count"] == 0

    def test_missing_tokens_produce_none_mean(self):
        results = [_case_result("qa", 1.0, tokens=None)]
        report = build_perf_report(results)
        assert report["qa"]["mean_tokens"] is None

    def test_length_finish_reason_counted_as_truncated(self):
        results = [
            _case_result("qa", 1.0, finish_reason="length"),
            _case_result("qa", 2.0, finish_reason="stop"),
        ]
        report = build_perf_report(results)
        assert report["qa"]["truncated_count"] == 1

    def test_render_perf_markdown_contains_surface_and_na(self):
        results = [_case_result("qa", 1.0, tokens=None)]
        md = render_perf_markdown(build_perf_report(results))
        assert "qa" in md
        assert "N/A" in md


class TestBaselineRoundTrip:
    def test_build_baseline_from_fixtures_has_expected_shape(self):
        baseline = build_baseline()
        assert baseline["schema_version"] == 1
        assert "captured_from" in baseline
        assert baseline["captured_from"]["model"]
        assert "qa" in baseline["surfaces"]
        assert "deterministic" in baseline["surfaces"]["qa"]
        assert "perf" in baseline["surfaces"]["qa"]

    def test_save_and_load_round_trip(self, tmp_path):
        baseline = _baseline()
        path = tmp_path / "baseline.json"
        save_baseline(baseline, path)
        loaded = load_baseline(path)
        assert loaded == baseline

    def test_save_produces_valid_json_file(self, tmp_path):
        baseline = _baseline()
        path = tmp_path / "baseline.json"
        save_baseline(baseline, path)
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["surfaces"]["qa"]["deterministic"]["pass_rate"] == 0.9


class TestCompareToBaseline:
    def test_pass_rate_drop_over_threshold_regresses(self):
        current_report = {"qa": {"pass_rate": 0.75, "mean_score": 0.75}}
        current_perf = {"qa": {"latency_p95_s": 10.0, "latency_p50_s": 5.0}}
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert isinstance(result, RegressionResult)
        assert result.regressed is True
        assert result.surfaces["qa"].regressed is True
        assert result.surfaces["qa"].pass_rate_delta == pytest.approx(-0.15)
        assert any("pass_rate" in r for r in result.surfaces["qa"].reasons)

    def test_pass_rate_drop_within_threshold_does_not_regress(self):
        current_report = {"qa": {"pass_rate": 0.85, "mean_score": 0.85}}
        current_perf = {"qa": {"latency_p95_s": 10.0, "latency_p50_s": 5.0}}
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert result.regressed is False
        assert result.surfaces["qa"].regressed is False

    def test_pass_rate_drop_exactly_at_threshold_does_not_regress(self):
        # 0.10 drop is NOT ">10 points" (strictly greater), so it must pass.
        current_report = {"qa": {"pass_rate": 0.80, "mean_score": 0.80}}
        current_perf = {"qa": {"latency_p95_s": 10.0, "latency_p50_s": 5.0}}
        baseline = _baseline(pass_rate=0.90, latency_p95_s=10.0)

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert result.surfaces["qa"].regressed is False

    def test_latency_p95_over_1_5x_regresses(self):
        current_report = {"qa": {"pass_rate": 0.9, "mean_score": 0.9}}
        current_perf = {"qa": {"latency_p95_s": 16.0, "latency_p50_s": 8.0}}
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert result.regressed is True
        assert result.surfaces["qa"].regressed is True
        assert result.surfaces["qa"].latency_p95_ratio == pytest.approx(1.6)
        assert any("latency" in r for r in result.surfaces["qa"].reasons)

    def test_latency_p95_within_1_5x_does_not_regress(self):
        current_report = {"qa": {"pass_rate": 0.9, "mean_score": 0.9}}
        current_perf = {"qa": {"latency_p95_s": 14.0, "latency_p50_s": 7.0}}
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert result.surfaces["qa"].regressed is False

    def test_new_surface_not_in_baseline_is_noted_not_failed(self):
        current_report = {
            "qa": {"pass_rate": 0.9, "mean_score": 0.9},
            "brand_new": {"pass_rate": 0.1, "mean_score": 0.1},
        }
        current_perf = {
            "qa": {"latency_p95_s": 10.0, "latency_p50_s": 5.0},
            "brand_new": {"latency_p95_s": 100.0, "latency_p50_s": 50.0},
        }
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert result.regressed is False
        assert "brand_new" not in result.surfaces
        assert any("brand_new" in note for note in result.notes)

    def test_surface_missing_from_current_run_is_noted_not_failed(self):
        current_report = {}
        current_perf = {}
        baseline = _baseline(
            pass_rate=0.9, latency_p95_s=10.0, surfaces=("qa", "summary")
        )

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert result.regressed is False
        assert result.surfaces == {}
        assert any("qa" in note for note in result.notes)
        assert any("summary" in note for note in result.notes)

    def test_none_pass_rate_in_current_or_baseline_is_not_a_hard_fail(self):
        """A surface with no graded cases (pass_rate=None, e.g. guardrail
        today) must not be treated as a fabricated regression - there's no
        deterministic signal to compare."""
        current_report = {"guardrail": {"pass_rate": None, "mean_score": None}}
        current_perf = {"guardrail": {"latency_p95_s": 10.0, "latency_p50_s": 5.0}}
        baseline = {
            "surfaces": {
                "guardrail": {
                    "deterministic": {"pass_rate": None, "mean_score": None},
                    "perf": {"latency_p95_s": 10.0, "latency_p50_s": 5.0},
                }
            }
        }

        result = compare_to_baseline(current_report, current_perf, baseline)

        assert result.regressed is False
        assert result.surfaces["guardrail"].pass_rate_delta is None

    def test_custom_thresholds_respected(self):
        current_report = {"qa": {"pass_rate": 0.85, "mean_score": 0.85}}
        current_perf = {"qa": {"latency_p95_s": 10.0, "latency_p50_s": 5.0}}
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)

        # 5-point drop fails a tightened 3-point threshold.
        result = compare_to_baseline(
            current_report, current_perf, baseline, pass_rate_drop_threshold=0.03
        )
        assert result.surfaces["qa"].regressed is True

    def test_default_thresholds_match_locked_plan(self):
        assert DEFAULT_PASS_RATE_DROP_THRESHOLD == 0.10
        assert DEFAULT_LATENCY_RATIO_THRESHOLD == 1.5


class TestRenderRegressionMarkdown:
    def test_pass_verdict_rendered(self):
        current_report = {"qa": {"pass_rate": 0.9, "mean_score": 0.9}}
        current_perf = {"qa": {"latency_p95_s": 10.0, "latency_p50_s": 5.0}}
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)
        result = compare_to_baseline(current_report, current_perf, baseline)

        md = render_regression_markdown(result)
        assert "## Regression check: PASS" in md
        assert "REGRESSED" not in md
        assert "qa" in md

    def test_regression_verdict_and_reason_rendered(self):
        current_report = {"qa": {"pass_rate": 0.5, "mean_score": 0.5}}
        current_perf = {"qa": {"latency_p95_s": 10.0, "latency_p50_s": 5.0}}
        baseline = _baseline(pass_rate=0.9, latency_p95_s=10.0)
        result = compare_to_baseline(current_report, current_perf, baseline)

        md = render_regression_markdown(result)
        assert "REGRESSION" in md
        assert "pass_rate" in md
        assert "REGRESSED" in md
