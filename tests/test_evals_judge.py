"""
Eval Judge (LLM-as-judge) Tests (Phase E2)

Covers `evals/judge.py`: prompt shape, score parsing, `run_judge` over
rubric'd cases with the zero-API `mock_judge`, and the judge dimension in
`evals/report.py`. NO real API calls - `openrouter_judge` is imported but
never invoked here.
"""

import json

import pytest

from evals.judge import (
    JudgeResult,
    build_judge_prompt,
    export_judge_batch,
    import_judge_results,
    mock_judge,
    parse_judge_score,
    run_judge,
)
from evals.report import build_judge_report, render_markdown_with_judge
from evals.schema import Case, load_cases

EXAMPLE_DATASET = "evals/datasets/example.yaml"


def _case(surface: str, rubric=None, input_=None, case_id="t") -> Case:
    return Case(id=case_id, surface=surface, input=input_ or {}, rubric=rubric)


# ---------------------------------------------------------------------------
# build_judge_prompt
# ---------------------------------------------------------------------------


class TestBuildJudgePrompt:
    def test_returns_system_and_user_messages(self):
        prompt = build_judge_prompt(
            "qa", {"question": "What is water?"}, "Water is H2O.", "Must be correct."
        )
        assert isinstance(prompt, list)
        assert len(prompt) == 2
        assert prompt[0]["role"] == "system"
        assert prompt[1]["role"] == "user"

    def test_user_message_includes_output_rubric_and_input(self):
        prompt = build_judge_prompt(
            "qa", {"question": "What is water?"}, "Water is H2O.", "Must be correct."
        )
        user_content = prompt[1]["content"]
        assert "Water is H2O." in user_content
        assert "Must be correct." in user_content
        assert "What is water?" in user_content
        assert "qa" in user_content

    def test_system_message_asks_for_score_format(self):
        prompt = build_judge_prompt("summary", {}, "output text", "rubric text")
        assert "SCORE:" in prompt[0]["content"]

    def test_surface_specific_guidance_differs(self):
        qa_prompt = build_judge_prompt("qa", {}, "out", "rubric")
        summary_prompt = build_judge_prompt("summary", {}, "out", "rubric")
        practice_prompt = build_judge_prompt("practice", {}, "out", "rubric")
        assert qa_prompt[0]["content"] != summary_prompt[0]["content"]
        assert qa_prompt[0]["content"] != practice_prompt[0]["content"]
        assert "correctness" in qa_prompt[0]["content"].lower()
        assert "faithfulness" in summary_prompt[0]["content"].lower()
        assert "distractors" in practice_prompt[0]["content"].lower()


# ---------------------------------------------------------------------------
# parse_judge_score
# ---------------------------------------------------------------------------


class TestParseJudgeScore:
    def test_present_score_parses(self):
        assert parse_judge_score("Good answer.\nSCORE: 0.85") == pytest.approx(0.85)

    def test_present_score_case_insensitive(self):
        assert parse_judge_score("Fine.\nscore: 0.5") == pytest.approx(0.5)

    def test_absent_score_returns_none(self):
        assert parse_judge_score("This answer looks solid overall.") is None

    def test_empty_string_returns_none(self):
        assert parse_judge_score("") is None

    def test_malformed_score_returns_none(self):
        assert parse_judge_score("Reasoning.\nSCORE: not-a-number") is None

    def test_out_of_range_high_returns_none(self):
        assert parse_judge_score("Reasoning.\nSCORE: 1.50") is None

    def test_out_of_range_negative_returns_none(self):
        assert parse_judge_score("Reasoning.\nSCORE: -0.20") is None

    def test_boundary_zero_and_one_parse(self):
        assert parse_judge_score("SCORE: 0") == pytest.approx(0.0)
        assert parse_judge_score("SCORE: 1") == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# mock_judge
# ---------------------------------------------------------------------------


class TestMockJudge:
    def test_substantive_output_scores_high(self):
        prompt = build_judge_prompt(
            "qa",
            {"question": "What is photosynthesis?"},
            "Photosynthesis converts light energy into chemical energy stored in glucose.",
            "Must be correct and thorough.",
        )
        raw = mock_judge(prompt)
        score = parse_judge_score(raw)
        assert score is not None
        assert score >= 0.7

    def test_empty_output_scores_low(self):
        prompt = build_judge_prompt("qa", {"question": "x"}, "", "rubric")
        raw = mock_judge(prompt)
        score = parse_judge_score(raw)
        assert score is not None
        assert score < 0.5

    def test_is_deterministic(self):
        prompt = build_judge_prompt(
            "qa", {"q": "x"}, "A reasonably long answer here.", "r"
        )
        assert mock_judge(prompt) == mock_judge(prompt)


# ---------------------------------------------------------------------------
# run_judge
# ---------------------------------------------------------------------------


class TestRunJudge:
    def test_rubric_case_gets_applicable_result(self):
        cases = [_case("qa", rubric="Must be correct.", case_id="q1")]
        outputs = {"q1": "A correct and thorough answer about the topic."}
        results = run_judge(cases, outputs, mock_judge)

        assert "q1" in results
        result = results["q1"]
        assert isinstance(result, JudgeResult)
        assert result.applicable is True
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.passed, bool)
        assert result.reasoning

    def test_non_rubric_case_is_not_applicable(self):
        cases = [_case("qa", rubric=None, case_id="q2")]
        outputs = {"q2": "Some answer."}
        results = run_judge(cases, outputs, mock_judge)

        assert results["q2"].applicable is False

    def test_missing_output_is_not_applicable(self):
        cases = [_case("qa", rubric="Must be correct.", case_id="q3")]
        results = run_judge(cases, outputs_by_id={}, judge_fn=mock_judge)

        assert results["q3"].applicable is False

    def test_unparseable_judge_response_fails_but_applicable(self):
        cases = [_case("qa", rubric="Must be correct.", case_id="q4")]
        outputs = {"q4": "An answer."}

        def broken_judge(prompt_messages):
            return "I refuse to give a score."

        results = run_judge(cases, outputs, broken_judge)
        assert results["q4"].applicable is True
        assert results["q4"].passed is False

    def test_every_case_gets_an_entry(self):
        cases = [
            _case("qa", rubric="r1", case_id="a"),
            _case("qa", rubric=None, case_id="b"),
        ]
        outputs = {"a": "A long enough substantive answer for scoring."}
        results = run_judge(cases, outputs, mock_judge)
        assert set(results.keys()) == {"a", "b"}

    def test_golden_dataset_rubric_cases_all_judged(self):
        """Every rubric'd case in the real golden dataset produces an
        applicable JudgeResult via mock_judge; non-rubric'd cases don't."""
        cases = load_cases(EXAMPLE_DATASET)
        outputs = {
            c.id: (c.expect or {}).get("example_output", "some output text here")
            for c in cases
        }
        results = run_judge(cases, outputs, mock_judge)

        rubric_cases = [c for c in cases if c.rubric]
        non_rubric_cases = [c for c in cases if not c.rubric]
        assert len(rubric_cases) >= 5

        for case in rubric_cases:
            assert results[case.id].applicable is True
        for case in non_rubric_cases:
            assert results[case.id].applicable is False


# ---------------------------------------------------------------------------
# export/import (external subagent judge flow)
# ---------------------------------------------------------------------------


class TestExportImportJudgeBatch:
    def test_export_only_includes_rubric_cases(self):
        cases_with_outputs = [
            (_case("qa", rubric="Must be correct.", case_id="a"), "output a"),
            (_case("qa", rubric=None, case_id="b"), "output b"),
        ]
        batch = export_judge_batch(cases_with_outputs)
        assert len(batch) == 1
        assert batch[0]["id"] == "a"
        assert batch[0]["output"] == "output a"
        assert batch[0]["rubric"] == "Must be correct."
        assert "judge_prompt" in batch[0]
        assert batch[0]["surface"] == "qa"

    def test_export_batch_is_json_serializable(self):
        cases_with_outputs = [
            (_case("qa", rubric="Must be correct.", case_id="a"), "output a"),
        ]
        batch = export_judge_batch(cases_with_outputs)
        json.dumps(batch)  # must not raise

    def test_import_roundtrip(self, tmp_path):
        path = tmp_path / "judge_results.json"
        path.write_text(
            json.dumps(
                [
                    {"id": "a", "score": 0.9, "reasoning": "Great answer."},
                    {"id": "b", "score": 0.3, "reasoning": "Weak answer."},
                ]
            ),
            encoding="utf-8",
        )
        results = import_judge_results(str(path))
        assert results["a"].score == pytest.approx(0.9)
        assert results["a"].passed is True
        assert results["a"].applicable is True
        assert results["b"].passed is False


# ---------------------------------------------------------------------------
# Report integration: two separate dimensions
# ---------------------------------------------------------------------------


class TestJudgeReportIntegration:
    def test_build_judge_report_computes_mean_score_per_surface(self):
        cases = [
            _case("qa", rubric="r", case_id="a"),
            _case("qa", rubric="r", case_id="b"),
        ]
        judge_results = {
            "a": JudgeResult(score=1.0, passed=True, reasoning="ok"),
            "b": JudgeResult(score=0.5, passed=False, reasoning="meh"),
        }
        report = build_judge_report(cases, judge_results)
        assert report["qa"]["judge_mean_score"] == pytest.approx(0.75)
        assert report["qa"]["judge_applicable_count"] == 2

    def test_not_applicable_excluded_from_mean(self):
        cases = [
            _case("qa", rubric="r", case_id="a"),
            _case("qa", rubric=None, case_id="b"),
        ]
        judge_results = {
            "a": JudgeResult(score=0.5, passed=False, reasoning="meh"),
            "b": JudgeResult(
                score=1.0, passed=True, reasoning="skipped", applicable=False
            ),
        }
        report = build_judge_report(cases, judge_results)
        assert report["qa"]["judge_count"] == 2
        assert report["qa"]["judge_applicable_count"] == 1
        assert report["qa"]["judge_mean_score"] == pytest.approx(0.5)

    def test_render_markdown_with_judge_labels_both_dimensions(self):
        cases = [_case("qa", rubric="r", case_id="a")]
        judge_results = {"a": JudgeResult(score=0.8, passed=True, reasoning="ok")}
        judge_report = build_judge_report(cases, judge_results)

        det_report = {
            "qa": {
                "count": 1,
                "graded_count": 1,
                "ungraded_count": 0,
                "pass_rate": 1.0,
                "mean_score": 1.0,
            }
        }
        md = render_markdown_with_judge(det_report, judge_report)
        assert "deterministic" in md.lower()
        assert "quality" in md.lower() or "judge" in md.lower()
        assert "0.80" in md

    def test_case_can_pass_structure_but_score_low_on_quality(self):
        """Structural pass-rate and judge quality-score are independent -
        a structurally-perfect case can still score low on quality."""
        cases = [_case("qa", rubric="r", case_id="a")]
        judge_results = {"a": JudgeResult(score=0.1, passed=False, reasoning="shallow")}
        det_report = {
            "qa": {
                "count": 1,
                "graded_count": 1,
                "ungraded_count": 0,
                "pass_rate": 1.0,
                "mean_score": 1.0,
            }
        }
        judge_report = build_judge_report(cases, judge_results)
        assert det_report["qa"]["pass_rate"] == pytest.approx(1.0)
        assert judge_report["qa"]["judge_mean_score"] == pytest.approx(0.1)
