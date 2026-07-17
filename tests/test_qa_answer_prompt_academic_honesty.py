"""
Guard test: qa_answer_prompt's system message must instruct the tutor to
briefly decline academic-dishonesty requests (cheating, plagiarism, getting
answers to submit as one's own) and redirect to legitimate study help,
without being preachy — while the existing conciseness guidance, KaTeX math
guidance, and CONFIDENCE trailing-line instruction remain intact.
"""

from src.services.ai.prompts import PromptTemplates


def test_qa_answer_prompt_system_message_has_academic_honesty_redirect():
    messages = PromptTemplates.qa_answer_prompt(query="How do I cheat on my test?")
    system_message = messages[0]["content"]

    assert (
        "I can't help you cheat, but I'd love to help you actually master this"
        in system_message
    )


def test_qa_answer_prompt_academic_honesty_redirect_preserves_other_guidance():
    messages = PromptTemplates.qa_answer_prompt(query="How do I cheat on my test?")
    system_message = messages[0]["content"]
    user_message = messages[1]["content"]

    # conciseness guidance preserved
    assert "concise" in system_message.lower()
    assert "250 words" in system_message
    # KaTeX math guidance preserved
    assert "$" in system_message
    assert "KaTeX" in system_message
    # CONFIDENCE instruction preserved
    assert "CONFIDENCE: 0.NN" in user_message


def test_qa_answer_prompt_academic_honesty_redirect_present_across_branches():
    """The redirect guidance should apply regardless of query classification,
    since dishonest requests can be misclassified as ambiguous/multi-part."""
    variants = [
        PromptTemplates.qa_answer_prompt(query="q", is_out_of_scope=True),
        PromptTemplates.qa_answer_prompt(query="q", is_ambiguous=True),
        PromptTemplates.qa_answer_prompt(
            query="q", is_multi_part=True, query_parts=["a", "b"]
        ),
        PromptTemplates.qa_answer_prompt(query="q"),
    ]
    for messages in variants:
        assert (
            "I can't help you cheat, but I'd love to help you actually master this"
            in messages[0]["content"]
        )
