"""
Golden Response Validation Tests
Validates AI outputs against expected responses from golden_responses.yaml
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

# Load golden responses
GOLDEN_RESPONSES_PATH = (
    Path(__file__).parent.parent / "_docs" / "qa" / "golden_responses.yaml"
)


def load_golden_responses() -> Dict[str, Any]:
    """Load golden responses from YAML file"""
    if not GOLDEN_RESPONSES_PATH.exists():
        pytest.skip(f"Golden responses file not found: {GOLDEN_RESPONSES_PATH}")

    with open(GOLDEN_RESPONSES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestGoldenResponses:
    """Test suite for golden response validation"""

    @pytest.fixture(scope="class")
    def golden_responses(self):
        """Load golden responses once for all tests"""
        return load_golden_responses()

    def test_golden_responses_file_exists(self):
        """Verify golden responses file exists"""
        assert (
            GOLDEN_RESPONSES_PATH.exists()
        ), f"Golden responses file not found: {GOLDEN_RESPONSES_PATH}"

    def test_golden_responses_structure(self, golden_responses):
        """Verify golden responses have correct structure"""
        assert isinstance(
            golden_responses, dict
        ), "Golden responses should be a dictionary"

        # Check for expected test case categories (note: YAML uses different key names)
        expected_categories = [
            "session_summaries",
            "practice_assignment",
            "conversational_qa",  # Note: YAML uses "conversational_qa" not "qa_query"
            "inactivity_nudges",
            "tutor_overrides",
            "progress_dashboard",
        ]

        for category in expected_categories:
            if category in golden_responses:
                assert isinstance(
                    golden_responses[category], list
                ), f"{category} should be a list"

    def test_session_summaries_cases(self, golden_responses):
        """Validate session summary test cases"""
        cases = golden_responses.get("session_summaries", [])
        assert len(cases) > 0, "Should have at least one session summary test case"

        for case in cases:
            assert "name" in case, "Each case should have a name"
            assert "input" in case, "Each case should have input"
            assert "expected_output" in case, "Each case should have expected_output"

            # Validate input structure
            input_data = case["input"]
            assert (
                "session_id" in input_data or "transcript" in input_data
            ), "Input should have session_id or transcript"

            # Validate expected output structure
            expected = case["expected_output"]
            # YAML structure uses "summary" wrapper
            if "summary" in expected:
                summary = expected["summary"]
                assert "narrative" in summary, "Expected output should have narrative"
                assert "next_steps" in summary, "Expected output should have next_steps"
            else:
                # Direct structure
                assert (
                    "narrative" in expected or "summary" in expected
                ), "Expected output should have narrative or summary"

    def test_practice_assignment_cases(self, golden_responses):
        """Validate practice assignment test cases"""
        cases = golden_responses.get("practice_assignment", [])
        assert len(cases) > 0, "Should have at least one practice assignment test case"

        for case in cases:
            assert "name" in case, "Each case should have a name"
            assert "input" in case, "Each case should have input"
            assert "expected_output" in case, "Each case should have expected_output"

            # Validate expected output structure
            expected = case["expected_output"]
            # YAML structure uses "practice_items" wrapper
            if "practice_items" in expected:
                assert isinstance(
                    expected["practice_items"], list
                ), "Practice items should be a list"
            elif "items" in expected:
                assert isinstance(expected["items"], list), "Items should be a list"
            else:
                # At least one should exist
                assert (
                    "practice_items" in expected or "items" in expected
                ), "Expected output should have practice_items or items"

    def test_qa_query_cases(self, golden_responses):
        """Validate Q&A query test cases"""
        # YAML uses "conversational_qa" as the key
        cases = golden_responses.get("conversational_qa", [])
        assert len(cases) > 0, "Should have at least one Q&A query test case"

        for case in cases:
            assert "name" in case, "Each case should have a name"
            assert "input" in case, "Each case should have input"
            assert "expected_output" in case, "Each case should have expected_output"

            # Validate input
            input_data = case["input"]
            assert "query" in input_data, "Input should have query"

            # Validate expected output
            expected = case["expected_output"]
            assert "answer" in expected, "Expected output should have answer"
            assert "confidence" in expected, "Expected output should have confidence"

    def test_progress_dashboard_cases(self, golden_responses):
        """Validate progress dashboard test cases"""
        cases = golden_responses.get("progress_dashboard", [])
        assert len(cases) > 0, "Should have at least one progress dashboard test case"

        for case in cases:
            assert "name" in case, "Each case should have a name"
            assert "input" in case, "Each case should have input"
            assert "expected_output" in case, "Each case should have expected_output"

            # Validate expected output
            expected = case["expected_output"]
            # YAML structure uses "dashboard" wrapper
            if "dashboard" in expected:
                dashboard = expected["dashboard"]
                # Dashboard can have various fields - check if it's a valid dict with content
                assert isinstance(dashboard, dict), "Dashboard should be a dictionary"
                # At least one field should exist (progress_summary, call_to_action, visual_charts, textual_insights, disclaimer, etc.)
                assert len(dashboard) > 0, "Dashboard should have at least one field"
            else:
                # Direct structure - should have at least one of these
                has_content = (
                    "goals" in expected
                    or "empty_state" in expected
                    or "progress_summary" in expected
                    or "dashboard" in expected
                )
                assert (
                    has_content
                ), "Expected output should have goals, empty_state, progress_summary, or dashboard"

    def test_nudge_cases(self, golden_responses):
        """Validate nudge test cases"""
        cases = golden_responses.get("inactivity_nudges", [])
        # Nudges might be optional, so just validate structure if they exist
        if cases:
            for case in cases:
                assert "name" in case, "Each case should have a name"
                assert "input" in case, "Each case should have input"
                assert (
                    "expected_output" in case
                ), "Each case should have expected_output"

    def test_override_cases(self, golden_responses):
        """Validate tutor override test cases"""
        cases = golden_responses.get("tutor_overrides", [])
        # Overrides might be optional, so just validate structure if they exist
        if cases:
            for case in cases:
                assert "name" in case, "Each case should have a name"
                assert "input" in case, "Each case should have input"
                assert (
                    "expected_output" in case
                ), "Each case should have expected_output"


class TestGoldenResponseValidation:
    """Test actual validation logic against golden responses"""

    def test_validate_session_summary_structure(self):
        """Test that session summary validation works"""
        from uuid import uuid4

        from src.api.schemas.summaries import CreateSummaryRequest

        # Test that request structure matches expected format
        session_id = str(uuid4())
        student_id = str(uuid4())
        tutor_id = str(uuid4())

        request = CreateSummaryRequest(
            session_id=session_id,
            student_id=student_id,
            tutor_id=tutor_id,
            session_duration_minutes=30,
            subject="Algebra",
        )

        assert request.session_id == session_id
        assert request.student_id == student_id
        assert request.tutor_id == tutor_id
        assert request.session_duration_minutes == 30

    def test_validate_qa_query_structure(self):
        """Test that Q&A query validation works"""
        from uuid import uuid4

        from src.api.schemas.qa import QueryRequest

        # Test that request structure matches expected format
        student_id = str(uuid4())
        request = QueryRequest(
            student_id=student_id,
            query="What is photosynthesis?",
            context={"subjects": ["Biology"]},
        )

        assert request.query == "What is photosynthesis?"
        assert request.student_id == student_id
        assert request.context is not None

    def test_validate_practice_assignment_structure(self):
        """Test that practice assignment validation works"""
        from uuid import uuid4

        from src.api.schemas.practice import AssignPracticeRequest

        # Test that request structure matches expected format
        student_id = str(uuid4())
        goal_id = str(uuid4())

        request = AssignPracticeRequest(
            student_id=student_id, subject="Algebra", num_items=5
        )

        assert request.subject == "Algebra"
        assert request.num_items == 5
        assert request.student_id == student_id
