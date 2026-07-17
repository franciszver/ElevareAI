"""
Tests for the merged QA answer + confidence self-assessment flow.

Previously each /qa/query request cost two LLM calls: one to generate the
answer, one for a separate confidence self-assessment. The model now emits
a trailing "CONFIDENCE: 0.NN" line as part of the answer itself, which
qa.extract_llm_confidence() strips off and calculate_confidence() consumes
directly - cutting the per-query call count in half.
"""

from src.api.handlers.qa import extract_llm_confidence
from src.services.ai.confidence import calculate_confidence


class TestExtractLlmConfidence:
    def test_present_extracts_and_strips(self):
        answer, confidence = extract_llm_confidence(
            "The mitochondria is the powerhouse of the cell.\nCONFIDENCE: 0.87"
        )
        assert answer == "The mitochondria is the powerhouse of the cell."
        assert confidence == 0.87

    def test_present_case_and_whitespace_tolerant(self):
        answer, confidence = extract_llm_confidence(
            "Some answer text.\n   confidence:   0.5   "
        )
        assert answer == "Some answer text."
        assert confidence == 0.5

    def test_absent_returns_none_and_answer_unchanged(self):
        text = "An answer with no trailing confidence marker."
        answer, confidence = extract_llm_confidence(text)
        assert answer == text
        assert confidence is None

    def test_malformed_value_strips_line_but_confidence_none(self):
        answer, confidence = extract_llm_confidence(
            "An answer here.\nCONFIDENCE: not-a-number"
        )
        assert answer == "An answer here."
        assert confidence is None

    def test_out_of_range_value_strips_line_but_confidence_none(self):
        answer, confidence = extract_llm_confidence("An answer here.\nCONFIDENCE: 1.50")
        assert answer == "An answer here."
        assert confidence is None

    def test_boundary_values_are_valid(self):
        _, low = extract_llm_confidence("Answer.\nCONFIDENCE: 0.00")
        _, high = extract_llm_confidence("Answer.\nCONFIDENCE: 1.0")
        assert low == 0.0
        assert high == 1.0


class TestCalculateConfidenceWithProvidedLlmScore:
    def test_provided_value_skips_network_call(self, monkeypatch):
        from src.services.ai.openai_client import openai_client

        call_count = {"n": 0}

        def fail_if_called(*args, **kwargs):
            call_count["n"] += 1
            return "0.5"

        monkeypatch.setattr(openai_client, "chat_completion", fail_if_called)

        result = calculate_confidence(
            query="What is the Pythagorean theorem?",
            answer="a^2 + b^2 = c^2 for right triangles.",
            llm_confidence=0.9,
        )

        assert call_count["n"] == 0
        assert result["factors"]["llm_confidence"] == 0.9
        assert isinstance(result["confidence_score"], float)

    def test_legacy_path_unchanged_when_no_llm_confidence(self, monkeypatch):
        from src.services.ai.openai_client import openai_client

        call_count = {"n": 0}

        def fake_chat_completion(*args, **kwargs):
            call_count["n"] += 1
            return "0.65"

        monkeypatch.setattr(openai_client, "chat_completion", fake_chat_completion)

        result = calculate_confidence(
            query="What is the Pythagorean theorem?",
            answer="a^2 + b^2 = c^2 for right triangles.",
        )

        assert call_count["n"] == 1
        assert result["factors"]["llm_confidence"] == 0.65


class TestMergedFlowEndToEnd:
    def test_qa_answer_with_confidence_line_flows_through_single_call(self, mock_ai):
        """Simulates the qa.py handler flow: one chat_completion call produces
        the answer + trailing confidence line (via the shared mock_ai fixture,
        same canned response the QA handler consumes), which is then extracted
        and fed into calculate_confidence with zero additional network calls.
        """
        call_count = {"n": 0}
        real_chat_completion = mock_ai.chat_completion

        def counting_chat_completion(*args, **kwargs):
            call_count["n"] += 1
            return real_chat_completion(*args, **kwargs)

        mock_ai.chat_completion = counting_chat_completion

        raw_answer = mock_ai.chat_completion(
            [{"role": "user", "content": "What is photosynthesis?"}]
        )
        answer, llm_confidence = extract_llm_confidence(raw_answer)

        assert llm_confidence == 0.85
        assert "CONFIDENCE" not in answer

        result = calculate_confidence(
            query="What is photosynthesis?",
            answer=answer,
            llm_confidence=llm_confidence,
        )

        # Exactly one LLM call total for the whole answer+confidence flow.
        assert call_count["n"] == 1
        assert result["factors"]["llm_confidence"] == 0.85
