"""
Confidence Calculation
Multi-factor confidence scoring for Q&A answers
"""

from typing import Dict

from src.config.settings import settings
from src.services.ai.openai_client import openai_client
from src.services.ai.prompts import PromptTemplates


def calculate_confidence(
    query: str, answer: str, context: Dict = None, query_analysis: Dict = None
) -> Dict[str, any]:
    """
    Calculate confidence score using multi-factor approach

    Args:
        query: Student query
        answer: AI-generated answer
        context: Additional context
        query_analysis: Pre-analyzed query (from QueryAnalyzer)

    Returns:
        dict with 'confidence' (High/Medium/Low), 'confidence_score' (0-1), and 'factors'
    """
    factors = {}

    # Apply query analysis impact if provided
    query_impact = 1.0
    if query_analysis:
        query_impact = query_analysis.get("confidence_impact", 1.0)
        if query_analysis.get("is_out_of_scope"):
            # Out-of-scope queries should have zero confidence
            return {
                "confidence": "Low",
                "confidence_score": 0.0,
                "factors": {"out_of_scope": True},
            }

    # Factor 1: LLM Self-Assessment (40% weight)
    try:
        llm_prompt = PromptTemplates.confidence_assessment_prompt(query, answer)
        llm_response = openai_client.chat_completion(
            llm_prompt,
            temperature=0.3,  # Lower temperature for more consistent assessment
            max_tokens=400,  # Reasoning models consume budget on hidden reasoning
        )
        # Extract number from response
        import re

        llm_score_match = re.search(r"0?\.\d+|1\.0|0", llm_response.strip())
        if llm_score_match:
            factors["llm_confidence"] = float(llm_score_match.group())
        else:
            factors["llm_confidence"] = 0.5  # Default if parsing fails
    except Exception as e:
        # If LLM assessment fails, use default
        factors["llm_confidence"] = 0.5

    # Factor 2: Context Relevance (30% weight)
    context_relevance = 1.0
    if context:
        # Check if query relates to context
        query_lower = query.lower()
        context_subjects = context.get("recent_sessions", [])
        if context_subjects:
            # Simple keyword matching (can be improved)
            subject_keywords = " ".join(context_subjects).lower()
            if any(keyword in query_lower for keyword in subject_keywords.split()):
                context_relevance = 1.0
            else:
                context_relevance = 0.7  # Somewhat relevant
        else:
            context_relevance = 0.8  # No context available
    else:
        context_relevance = 0.7  # No context provided
    factors["context_relevance"] = context_relevance

    # Factor 3: Answer Quality (10% weight)
    # Simple heuristics: length, completeness indicators
    answer_length = len(answer)
    if answer_length < 50:
        answer_quality = 0.6  # Too short
    elif answer_length > 2000:
        answer_quality = 0.8  # Very long (might be too verbose)
    else:
        answer_quality = 1.0  # Good length
    factors["answer_quality"] = answer_quality

    # Factor 4: Domain Expertise (20% weight)
    # Check for uncertainty indicators in answer
    uncertainty_keywords = [
        "might",
        "possibly",
        "uncertain",
        "not sure",
        "may",
        "could be",
    ]
    answer_lower = answer.lower()
    uncertainty_count = sum(
        1 for keyword in uncertainty_keywords if keyword in answer_lower
    )

    if uncertainty_count == 0:
        domain_expertise = 1.0
    elif uncertainty_count <= 2:
        domain_expertise = 0.7
    else:
        domain_expertise = 0.5

    factors["domain_expertise"] = domain_expertise

    # Calculate weighted score
    weighted_score = (
        factors["llm_confidence"] * 0.4
        + factors["context_relevance"] * 0.3
        + factors["answer_quality"] * 0.1
        + factors["domain_expertise"] * 0.2
    )

    # Apply query analysis impact
    weighted_score = weighted_score * query_impact

    # Determine confidence level
    if weighted_score >= settings.confidence_high_threshold:
        confidence = "High"
    elif weighted_score >= settings.confidence_medium_threshold:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "confidence": confidence,
        "confidence_score": round(weighted_score, 2),
        "factors": factors,
    }
