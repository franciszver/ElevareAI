"""
Eval Harness Deterministic Grader Tests (Phase E1)

Covers every E1 deterministic grader (evals/graders/deterministic.py), its
registry adapter (evals/graders/registry.py), and an end-to-end run of the
expanded example dataset through `run_cases` + `graders_by_surface`. Zero
API calls - all fixtures are inline strings/dicts or the dataset's inline
`expect.example_output`.
"""

import json

import pytest

from evals.graders import deterministic as det
from evals.graders.registry import graders_by_surface
from evals.report import build_report, render_markdown
from evals.runner import run_cases
from evals.schema import Case, load_cases

EXAMPLE_DATASET = "evals/datasets/example.yaml"

GOOD_PRACTICE_ITEM = {
    "question_text": "What is the powerhouse of the cell called in biology?",
    "choices": ["A) Nucleus", "B) Ribosome", "C) Mitochondria", "D) Golgi apparatus"],
    "correct_answer": "C",
    "answer_text": "Mitochondria",
    "explanation": "Mitochondria generate most of a cell's ATP through cellular respiration.",
}


def _case(surface: str, expect=None, input_=None) -> Case:
    return Case(id="t", surface=surface, input=input_ or {}, expect=expect or {})


# ---------------------------------------------------------------------------
# QA graders
# ---------------------------------------------------------------------------


class TestQaAnswerNonempty:
    def test_nonempty_answer_passes(self):
        result = det.qa_answer_nonempty("A real answer.\nCONFIDENCE: 0.8")
        assert result.passed is True

    def test_empty_after_stripping_confidence_fails(self):
        result = det.qa_answer_nonempty("\nCONFIDENCE: 0.8")
        assert result.passed is False

    def test_whitespace_only_fails(self):
        result = det.qa_answer_nonempty("   \n  ")
        assert result.passed is False


class TestQaAnswerConcise:
    def test_short_answer_passes(self):
        result = det.qa_answer_concise("This is a short answer.\nCONFIDENCE: 0.8")
        assert result.passed is True

    def test_400_word_answer_fails_concise(self):
        long_answer = " ".join(["word"] * 400) + "\nCONFIDENCE: 0.8"
        result = det.qa_answer_concise(long_answer)
        assert result.passed is False
        assert "400" in result.detail or "exceeds" in result.detail

    def test_boundary_at_max_words_passes(self):
        answer = " ".join(["word"] * 300)
        result = det.qa_answer_concise(answer, max_words=300)
        assert result.passed is True


class TestQaNoRawLatexDelimiters:
    def test_katex_dollar_delimiters_pass(self):
        result = det.qa_no_raw_latex_delimiters("The formula is $E=mc^2$.")
        assert result.passed is True

    def test_bare_backslash_paren_fails(self):
        result = det.qa_no_raw_latex_delimiters(r"The formula is \(E=mc^2\).")
        assert result.passed is False

    def test_bare_backslash_bracket_fails(self):
        result = det.qa_no_raw_latex_delimiters(r"\[E=mc^2\]")
        assert result.passed is False


class TestQaOutOfScopeRefuses:
    CANNED = (
        "I'm designed to help with educational topics like math, science, "
        "literature, and test prep. I can't assist with non-academic "
        "questions like weather, sports, or general information. Is there "
        "an academic topic I can help you with instead?"
    )

    def test_out_of_scope_case_with_canned_refusal_passes(self):
        result = det.qa_out_of_scope_refuses(self.CANNED, is_out_of_scope=True)
        assert result.passed is True

    def test_out_of_scope_case_with_real_answer_fails(self):
        """A real attempted answer to an out-of-scope question must FAIL -
        it should have hit the canned refusal path instead."""
        result = det.qa_out_of_scope_refuses(
            "Tomorrow's weather will be sunny with a high of 75F.\nCONFIDENCE: 0.6",
            is_out_of_scope=True,
        )
        assert result.passed is False

    def test_in_scope_case_is_not_applicable_and_passes(self):
        result = det.qa_out_of_scope_refuses(
            "Photosynthesis converts light into chemical energy.", is_out_of_scope=False
        )
        assert result.passed is True
        assert result.applicable is False
        assert "not applicable" in result.detail.lower()


# ---------------------------------------------------------------------------
# Practice graders
# ---------------------------------------------------------------------------


class TestPracticeQuestionQuality:
    def test_good_item_passes(self):
        result = det.practice_question_quality(GOOD_PRACTICE_ITEM)
        assert result.passed is True

    def test_short_question_fails(self):
        bad = {**GOOD_PRACTICE_ITEM, "question_text": "What is it?"}
        result = det.practice_question_quality(bad)
        assert result.passed is False
        assert "question_text" in result.detail

    def test_short_explanation_fails(self):
        bad = {**GOOD_PRACTICE_ITEM, "explanation": "Too short."}
        result = det.practice_question_quality(bad)
        assert result.passed is False
        assert "explanation" in result.detail

    def test_invalid_correct_answer_letter_fails(self):
        bad = {**GOOD_PRACTICE_ITEM, "correct_answer": "Z"}
        result = det.practice_question_quality(bad)
        assert result.passed is False

    def test_wrong_choice_count_fails(self):
        bad = {**GOOD_PRACTICE_ITEM, "choices": GOOD_PRACTICE_ITEM["choices"][:3]}
        result = det.practice_question_quality(bad)
        assert result.passed is False


class TestPracticeNoPlaceholderDistractors:
    def test_clean_choices_pass(self):
        result = det.practice_no_placeholder_distractors(GOOD_PRACTICE_ITEM)
        assert result.passed is True

    @pytest.mark.parametrize(
        "placeholder",
        [
            # src/services/practice/quality.py's
            # `_generate_multiple_choice_options` fallback distractors
            # (subject_label omitted -> defaults to "topic").
            "An incorrect topic alternative",
            "Another plausible but wrong topic answer",
            "A related but incorrect topic answer",
            "A related but incorrect Math answer",
        ],
    )
    def test_known_placeholder_strings_fail(self, placeholder):
        bad = {
            **GOOD_PRACTICE_ITEM,
            "choices": [
                "A) Nucleus",
                "B) Ribosome",
                f"C) {placeholder}",
                "D) Golgi apparatus",
            ],
        }
        result = det.practice_no_placeholder_distractors(bad)
        assert result.passed is False
        assert placeholder in result.detail


class TestPracticeNoRawLatex:
    def test_clean_item_passes(self):
        result = det.practice_no_raw_latex(GOOD_PRACTICE_ITEM)
        assert result.passed is True

    def test_raw_latex_in_question_fails(self):
        bad = {**GOOD_PRACTICE_ITEM, "question_text": r"Simplify \(x^2 + 2x\)."}
        result = det.practice_no_raw_latex(bad)
        assert result.passed is False

    def test_raw_latex_in_choice_fails(self):
        bad = {
            **GOOD_PRACTICE_ITEM,
            "choices": [
                r"A) \(x^2\)",
                "B) Ribosome",
                "C) Mitochondria",
                "D) Golgi apparatus",
            ],
        }
        result = det.practice_no_raw_latex(bad)
        assert result.passed is False


class TestPracticeMathAnswerCorrect:
    LINEAR_ITEM = {
        "question_text": "Solve for x: 5x + 4 = 18",
        "answer_text": "x = 2.8",
        "choices": ["A) 1.4", "B) 5.6", "C) 4.8", "D) 2.8"],
        "correct_answer": "D",
        "explanation": (
            "Step 1: Subtract 4 from both sides\n  5x = 14\nStep 2: Divide "
            "both sides by 5\n  x = 14/5 = 2.8"
        ),
        "solution": "14/5",
        "difficulty": 3,
    }

    def test_correct_labelled_answer_passes(self):
        result = det.practice_math_answer_correct(
            "linear_equation", 101, self.LINEAR_ITEM
        )
        assert result.passed is True

    def test_wrong_labelled_answer_fails(self):
        bad = {**self.LINEAR_ITEM, "correct_answer": "A"}  # A) 1.4 is not the solution
        result = det.practice_math_answer_correct("linear_equation", 101, bad)
        assert result.passed is False

    def test_unknown_topic_fails(self):
        result = det.practice_math_answer_correct(
            "geometry_proofs", 1, self.LINEAR_ITEM
        )
        assert result.passed is False
        assert "Unknown math_topic" in result.detail

    def test_quadratic_matches_regenerated_ground_truth(self):
        item = {
            "question_text": "Solve for x: x² - 6x + 5 = 0",
            "answer_text": "x = 1.0",
            "choices": ["A) 2", "B) 4", "C) 1", "D) 0.5"],
            "correct_answer": "C",
            "explanation": "Using the quadratic formula or factoring, we get x = 1 or x = 5",
            "solution": "1",
            "difficulty": 3,
        }
        result = det.practice_math_answer_correct("quadratic_equation", 202, item)
        assert result.passed is True

    def test_expression_expand_with_operation_matches_ground_truth(self):
        item = {
            "question_text": "Expand: (x + 2)*(x + 5)",
            "answer_text": "x**2 + 7*x + 10",
            "choices": [
                "A) x**2 + 7*x + 10 * 2",
                "B) x**2 + 7*x + 11",
                "C) x**2 + 7*x + 10 + 1",
                "D) x**2 + 7*x + 10",
            ],
            "correct_answer": "D",
            "explanation": "Expanding the expression: (x + 2)*(x + 5) = x**2 + 7*x + 10",
            "solution": "x**2 + 7*x + 10",
            "difficulty": 6,
        }
        result = det.practice_math_answer_correct(
            "expression_simplification", 1, item, operation="expand"
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# Summary graders
# ---------------------------------------------------------------------------


class TestSummaryHasNarrative:
    def test_dict_with_narrative_passes(self):
        result = det.summary_has_narrative({"narrative": "You covered mitosis today."})
        assert result.passed is True

    def test_dict_with_empty_narrative_fails(self):
        result = det.summary_has_narrative({"narrative": "   "})
        assert result.passed is False

    def test_raw_text_without_next_steps_marker_treated_as_narrative(self):
        result = det.summary_has_narrative("A plain AI summary paragraph.")
        assert result.passed is True

    def test_raw_text_with_capitalized_next_steps_marker_parses_narrative(self):
        # Mirrors summarizer.py's case-insensitive split; capitalization
        # must not defeat parsing.
        result = det.summary_has_narrative(
            "Great session on quadratics.\nNext steps:\n1. Practice factoring\n2. Review the formula"
        )
        assert result.passed is True


class TestSummaryHasNextSteps:
    def test_dict_with_two_steps_passes(self):
        result = det.summary_has_next_steps(
            {"next_steps": ["Review notes", "Do 5 practice problems"]}
        )
        assert result.passed is True

    def test_zero_steps_fails(self):
        result = det.summary_has_next_steps({"next_steps": []})
        assert result.passed is False

    def test_more_than_three_steps_fails(self):
        result = det.summary_has_next_steps({"next_steps": ["a", "b", "c", "d"]})
        assert result.passed is False

    def test_raw_text_with_bare_next_marker_parses_steps(self):
        # Regression test for the `re.split(...) or re.split(...)` bug:
        # re.split always returns a non-empty list, so the `or` never fell
        # through to the "next:" pattern when "next steps:" didn't match.
        result = det.summary_has_next_steps(
            "Great session.\nNext: Practice factoring, Review the formula"
        )
        assert result.passed is True


class TestSummaryTypeMatchesDuration:
    def test_brief_for_short_duration_passes(self):
        result = det.summary_type_matches_duration(
            {"summary_type": "brief"}, duration_min=8
        )
        assert result.passed is True

    def test_normal_for_boundary_duration_passes(self):
        result = det.summary_type_matches_duration(
            {"summary_type": "normal"}, duration_min=10
        )
        assert result.passed is True

    def test_mismatched_type_fails(self):
        result = det.summary_type_matches_duration(
            {"summary_type": "normal"}, duration_min=5
        )
        assert result.passed is False

    def test_missing_summary_type_is_not_applicable(self):
        """Raw text carries no summary_type field at all - the grader can't
        judge it either way, so it reports not-applicable rather than a
        genuine failure (excluded from pass-rate, not counted against it)."""
        result = det.summary_type_matches_duration("raw text only", duration_min=5)
        assert result.passed is True
        assert result.applicable is False


# ---------------------------------------------------------------------------
# Registry adapters
# ---------------------------------------------------------------------------


class TestRegistryAdapters:
    def test_qa_confidence_skipped_for_out_of_scope(self):
        (
            confidence_adapter,
            *_,
        ) = graders_by_surface["qa"]
        case = _case("qa", expect={"out_of_scope": True})
        result = confidence_adapter("no confidence line here", case)
        assert result.passed is True
        assert result.applicable is False
        assert "not applicable" in result.detail.lower()

    def test_qa_confidence_enforced_when_in_scope(self):
        confidence_adapter, *_ = graders_by_surface["qa"]
        case = _case("qa", expect={"out_of_scope": False})
        result = confidence_adapter("An answer with no confidence line.", case)
        assert result.passed is False

    def test_practice_math_not_applicable_without_seed(self):
        math_adapter = graders_by_surface["practice"][-1]
        case = _case("practice", expect={})
        result = math_adapter(json.dumps(GOOD_PRACTICE_ITEM), case)
        assert result.passed is True
        assert result.applicable is False
        assert "not applicable" in result.detail.lower()

    def test_practice_math_applies_when_seed_present(self):
        math_adapter = graders_by_surface["practice"][-1]
        case = _case("practice", expect={"math_topic": "linear_equation", "seed": 101})
        bad_item = {**TestPracticeMathAnswerCorrect.LINEAR_ITEM, "correct_answer": "A"}
        result = math_adapter(json.dumps(bad_item), case)
        assert result.passed is False

    def test_summary_type_reads_duration_from_input(self):
        *_, duration_adapter = graders_by_surface["summary"]
        case = _case("summary", input_={"duration_minutes": 5})
        result = duration_adapter(json.dumps({"summary_type": "normal"}), case)
        assert result.passed is False  # 5 min should be "brief", not "normal"


# ---------------------------------------------------------------------------
# End-to-end: real dataset through run_cases + graders_by_surface
# ---------------------------------------------------------------------------


class TestDatasetEndToEnd:
    def _example_output_generate_fn(self, case: Case) -> str:
        return case.expect["example_output"]

    def test_full_dataset_grades_green_with_no_ungraded_surfaces(self):
        cases = load_cases(EXAMPLE_DATASET)
        results = run_cases(
            cases, graders_by_surface, generate_fn=self._example_output_generate_fn
        )

        assert len(results) == len(cases)
        assert all(r.graded for r in results), [
            r.case_id for r in results if not r.graded
        ]
        assert all(r.passed for r in results), [
            (r.case_id, r.detail) for r in results if not r.passed
        ]

        report = build_report(results)
        for surface in ("qa", "practice", "summary"):
            assert surface in report
            assert report[surface]["ungraded_count"] == 0
            assert report[surface]["pass_rate"] == pytest.approx(1.0)

        md = render_markdown(report)
        assert "Ungraded cases (no grader registered): 0" in md

    def test_red_a_deliberately_bad_practice_output_fails_its_grader(self):
        """RED capability: corrupting a real dataset case's example output
        with a known-bad practice item (placeholder distractor) must make
        that case fail, proving the grader isn't a rubber stamp."""
        cases = load_cases(EXAMPLE_DATASET)
        target_id = "practice-algebra-basic-arithmetic"

        bad_output = json.dumps(
            {
                "question_text": "What is the sum of 2 and 2 in basic arithmetic?",
                "choices": [
                    "A) An incorrect alternative",
                    "B) 4",
                    "C) 5",
                    "D) 6",
                ],
                "correct_answer": "B",
                "answer_text": "4",
                "explanation": "Adding 2 and 2 together using basic addition gives a total of 4.",
            }
        )

        def generate_fn(case: Case) -> str:
            if case.id == target_id:
                return bad_output
            return case.expect["example_output"]

        results = run_cases(cases, graders_by_surface, generate_fn=generate_fn)
        target_result = next(r for r in results if r.case_id == target_id)
        assert target_result.graded is True
        assert target_result.passed is False
        assert "placeholder" in target_result.detail.lower()
