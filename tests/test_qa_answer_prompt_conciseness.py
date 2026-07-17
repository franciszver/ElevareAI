"""
Guard test: qa_answer_prompt's system message must instruct concise answers
(latency hardening for the "Explore Deeper" QA flow) that use proper LaTeX
math wrapped in $ delimiters (since the UI renders KaTeX), while the
CONFIDENCE trailing-line instruction in the user message must remain intact.
"""

from src.services.ai.prompts import PromptTemplates


def test_qa_answer_prompt_system_message_has_concise_guidance():
    messages = PromptTemplates.qa_answer_prompt(query="Explain the Krebs cycle")
    system_message = messages[0]["content"]

    assert "concise" in system_message.lower()
    assert "250 words" in system_message
    assert "$" in system_message
    assert "KaTeX" in system_message


def test_qa_answer_prompt_preserves_confidence_instruction():
    messages = PromptTemplates.qa_answer_prompt(query="Explain the Krebs cycle")
    user_message = messages[1]["content"]

    assert "CONFIDENCE: 0.NN" in user_message


def test_qa_answer_prompt_concise_guidance_present_across_branches():
    """All qa_answer_prompt system-message variants should carry the guidance,
    since ambiguous/multi-part/out-of-scope answers can run long too."""
    variants = [
        PromptTemplates.qa_answer_prompt(query="q", is_out_of_scope=True),
        PromptTemplates.qa_answer_prompt(query="q", is_ambiguous=True),
        PromptTemplates.qa_answer_prompt(
            query="q", is_multi_part=True, query_parts=["a", "b"]
        ),
        PromptTemplates.qa_answer_prompt(query="q"),
    ]
    for messages in variants:
        assert "concise" in messages[0]["content"].lower()
