"""
Golden Response Fixtures
Helper functions for loading and validating golden responses
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

GOLDEN_RESPONSES_PATH = (
    Path(__file__).parent.parent.parent / "_docs" / "qa" / "golden_responses.yaml"
)


def load_golden_responses() -> Dict[str, Any]:
    """Load golden responses from YAML file"""
    if not GOLDEN_RESPONSES_PATH.exists():
        raise FileNotFoundError(
            f"Golden responses file not found: {GOLDEN_RESPONSES_PATH}"
        )

    try:
        with open(GOLDEN_RESPONSES_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except UnicodeDecodeError:
        # Fallback: try with errors='ignore' for Windows compatibility
        with open(GOLDEN_RESPONSES_PATH, "r", encoding="utf-8", errors="ignore") as f:
            return yaml.safe_load(f)


def get_test_case(category: str, case_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific test case by category and name"""
    responses = load_golden_responses()
    cases = responses.get(category, [])

    for case in cases:
        if case.get("name") == case_name:
            return case

    return None


def get_all_cases(category: str) -> List[Dict[str, Any]]:
    """Get all test cases for a category"""
    responses = load_golden_responses()
    return responses.get(category, [])


def validate_response_structure(
    response: Dict[str, Any], expected_structure: Dict[str, Any]
) -> tuple[bool, List[str]]:
    """
    Validate that a response matches expected structure

    Returns:
        (is_valid, errors): Tuple of validation result and list of errors
    """
    errors = []

    for key, expected_type in expected_structure.items():
        if key not in response:
            errors.append(f"Missing required field: {key}")
            continue

        actual_value = response[key]
        expected_type_name = (
            expected_type.__name__
            if hasattr(expected_type, "__name__")
            else str(expected_type)
        )

        if not isinstance(actual_value, expected_type):
            errors.append(
                f"Field '{key}' should be {expected_type_name}, got {type(actual_value).__name__}"
            )

    return len(errors) == 0, errors


def compare_strings(
    actual: str, expected: str, case_sensitive: bool = False
) -> tuple[bool, str]:
    """
    Compare two strings with fuzzy matching

    Returns:
        (matches, diff_message): Tuple of match result and difference message
    """
    if not case_sensitive:
        actual = actual.lower()
        expected = expected.lower()

    if actual == expected:
        return True, ""

    # Check if actual contains expected (for partial matches)
    if expected in actual:
        return True, "Partial match (expected is substring of actual)"

    # Check if actual is substring of expected
    if actual in expected:
        return True, "Partial match (actual is substring of expected)"

    # Calculate similarity
    similarity = calculate_similarity(actual, expected)
    return False, f"Strings differ (similarity: {similarity:.2%})"


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate simple similarity between two strings"""
    if not str1 or not str2:
        return 0.0

    # Simple word-based similarity
    words1 = set(str1.lower().split())
    words2 = set(str2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    return len(intersection) / len(union) if union else 0.0


# Expected structures for validation
EXPECTED_STRUCTURES = {
    "session_summary": {
        "narrative": str,
        "next_steps": list,
        "subjects_covered": list,
        "summary_type": str,
    },
    "practice_assignment": {"items": list, "all_ai_generated": bool},
    "qa_response": {
        "answer": str,
        "confidence": str,
        "confidence_score": float,
        "escalation_suggested": bool,
    },
    "progress_dashboard": {"goals": list, "stats": dict},
}
