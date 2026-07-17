"""
Eval Harness Self-Tests (Phase E0)

These tests exercise the eval harness scaffolding itself (dataset loader,
deterministic graders, runner, report) with ZERO API calls. Live eval cases
(gated behind `-m eval` and OPENROUTER_API_KEY) are a later phase.
"""

import pytest

from evals.graders.deterministic import (
    GradeResult,
    confidence_line_present,
    practice_json_valid,
)
from evals.report import build_report, render_markdown
from evals.runner import CaseResult, run_cases
from evals.schema import Case, load_cases

EXAMPLE_DATASET = "evals/datasets/example.yaml"


class TestLoadCases:
    def test_loads_valid_file(self):
        cases = load_cases(EXAMPLE_DATASET)
        assert len(cases) >= 3
        for case in cases:
            assert isinstance(case, Case)
            assert case.id
            assert case.surface in {"qa", "summary", "practice", "guardrail"}
            assert isinstance(case.input, dict)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_cases("evals/datasets/does_not_exist.yaml")

    def test_malformed_case_missing_required_field_raises(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text(
            "cases:\n  - id: missing-surface\n    input:\n      question: hi\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="surface"):
            load_cases(str(bad_file))

    def test_malformed_case_bad_surface_raises(self, tmp_path):
        bad_file = tmp_path / "bad_surface.yaml"
        bad_file.write_text(
            "cases:\n  - id: bad-surface\n    surface: not-a-surface\n    input:\n      question: hi\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="surface"):
            load_cases(str(bad_file))

    def test_malformed_case_not_a_dict_raises(self, tmp_path):
        bad_file = tmp_path / "not_a_mapping.yaml"
        bad_file.write_text("cases:\n  - just a string\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_cases(str(bad_file))


class TestConfidenceLineGrader:
    def test_valid_confidence_line_passes(self):
        result = confidence_line_present(
            "Photosynthesis converts light energy into chemical energy.\nCONFIDENCE: 0.85"
        )
        assert isinstance(result, GradeResult)
        assert result.passed is True
        assert result.score == 1.0

    def test_missing_confidence_line_fails(self):
        result = confidence_line_present(
            "Photosynthesis converts light energy into chemical energy."
        )
        assert result.passed is False
        assert result.score == 0.0

    def test_out_of_range_confidence_fails(self):
        result = confidence_line_present("An answer.\nCONFIDENCE: 1.50")
        assert result.passed is False

    def test_garbage_confidence_value_fails(self):
        result = confidence_line_present("An answer.\nCONFIDENCE: not-a-number")
        assert result.passed is False


class TestPracticeJsonGrader:
    VALID_JSON = (
        '{"question_text": "What is the sum of 2 and 2 in basic arithmetic?", '
        '"choices": ["A) 3", "B) 4", "C) 5", "D) 6"], '
        '"correct_answer": "B", '
        '"answer_text": "4", '
        '"explanation": "2 + 2 equals 4 by basic addition rules."}'
    )

    def test_valid_practice_json_passes(self):
        result = practice_json_valid(self.VALID_JSON)
        assert result.passed is True
        assert result.score == 1.0

    def test_invalid_json_fails(self):
        result = practice_json_valid("not json at all")
        assert result.passed is False

    def test_wrong_choice_count_fails(self):
        bad = (
            '{"question_text": "What is the sum of 2 and 2?", '
            '"choices": ["A) 3", "B) 4", "C) 5"], '
            '"correct_answer": "B"}'
        )
        result = practice_json_valid(bad)
        assert result.passed is False

    def test_bad_correct_answer_letter_fails(self):
        bad = (
            '{"question_text": "What is the sum of 2 and 2?", '
            '"choices": ["A) 3", "B) 4", "C) 5", "D) 6"], '
            '"correct_answer": "Z"}'
        )
        result = practice_json_valid(bad)
        assert result.passed is False


class TestRunner:
    def test_run_cases_end_to_end_with_injected_mock(self):
        cases = load_cases(EXAMPLE_DATASET)

        def fake_generate(case: Case) -> str:
            if case.surface == "qa":
                return "This is a helpful educational answer.\nCONFIDENCE: 0.85"
            if case.surface == "practice":
                return (
                    '{"question_text": "What is the sum of 2 and 2 in basic arithmetic?", '
                    '"choices": ["A) 3", "B) 4", "C) 5", "D) 6"], '
                    '"correct_answer": "B", '
                    '"answer_text": "4", '
                    '"explanation": "2 + 2 equals 4 by basic addition rules."}'
                )
            return "generated output"

        graders_by_surface = {
            "qa": [confidence_line_present],
            "practice": [practice_json_valid],
        }

        results = run_cases(cases, graders_by_surface, generate_fn=fake_generate)

        assert len(results) == len(cases)
        for result in results:
            assert isinstance(result, CaseResult)
            assert result.case_id
            assert result.surface in {"qa", "summary", "practice", "guardrail"}
            if result.graded:
                assert isinstance(result.passed, bool)
            else:
                assert result.passed is None
            assert 0.0 <= result.score <= 1.0
            assert result.latency_s >= 0.0

        qa_results = [r for r in results if r.surface == "qa"]
        assert qa_results
        assert all(r.passed for r in qa_results)
        assert all(r.graded for r in qa_results)

        practice_results = [r for r in results if r.surface == "practice"]
        assert practice_results
        assert all(r.passed for r in practice_results)
        assert all(r.graded for r in practice_results)

    def test_ungraded_surface_is_not_auto_passed(self):
        """A case whose surface has no registered grader must be reported
        as ungraded (graded=False, passed=None), not as an auto-pass."""
        cases = load_cases(EXAMPLE_DATASET)

        def fake_generate(case: Case) -> str:
            return "generated output"

        # No grader registered for "summary" (or any surface).
        results = run_cases(cases, graders_by_surface={}, generate_fn=fake_generate)

        summary_results = [r for r in results if r.surface == "summary"]
        assert summary_results
        for result in summary_results:
            assert result.graded is False
            assert result.passed is None
            assert "no grader registered" in result.detail


class TestReport:
    def test_build_report_computes_pass_rate(self):
        results = [
            CaseResult("c1", "qa", True, 1.0, "ok", 0.01),
            CaseResult("c2", "qa", False, 0.0, "missing confidence", 0.02),
            CaseResult("c3", "practice", True, 1.0, "ok", 0.03),
        ]
        report = build_report(results)

        assert report["qa"]["count"] == 2
        assert report["qa"]["pass_rate"] == pytest.approx(0.5)
        assert report["qa"]["mean_score"] == pytest.approx(0.5)

        assert report["practice"]["count"] == 1
        assert report["practice"]["pass_rate"] == pytest.approx(1.0)

    def test_ungraded_cases_excluded_from_pass_rate(self):
        results = [
            CaseResult("c1", "qa", True, 1.0, "ok", 0.01),
            CaseResult(
                "c2",
                "qa",
                None,
                0.0,
                "no grader registered for surface 'qa'",
                0.02,
                graded=False,
                applicable=False,
            ),
        ]
        report = build_report(results)

        assert report["qa"]["count"] == 2
        assert report["qa"]["graded_count"] == 1
        assert report["qa"]["ungraded_count"] == 1
        # Only the graded case counts toward pass_rate/mean_score.
        assert report["qa"]["pass_rate"] == pytest.approx(1.0)
        assert report["qa"]["mean_score"] == pytest.approx(1.0)

    def test_all_ungraded_surface_has_no_pass_rate(self):
        results = [
            CaseResult(
                "c1",
                "summary",
                None,
                0.0,
                "no grader registered for surface 'summary'",
                0.01,
                graded=False,
                applicable=False,
            ),
        ]
        report = build_report(results)

        assert report["summary"]["graded_count"] == 0
        assert report["summary"]["ungraded_count"] == 1
        assert report["summary"]["pass_rate"] is None
        assert report["summary"]["mean_score"] is None

    def test_render_markdown_contains_surfaces(self):
        results = [CaseResult("c1", "qa", True, 1.0, "ok", 0.01)]
        report = build_report(results)
        md = render_markdown(report)
        assert "qa" in md
        assert "pass" in md.lower()

    def test_render_markdown_surfaces_ungraded_count(self):
        results = [
            CaseResult(
                "c1",
                "summary",
                None,
                0.0,
                "no grader registered for surface 'summary'",
                0.01,
                graded=False,
                applicable=False,
            ),
        ]
        report = build_report(results)
        md = render_markdown(report)
        assert "Ungraded" in md
        assert "N/A" in md
