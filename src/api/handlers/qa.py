"""
Q&A Handler
POST /qa/query - Submit student query and get AI answer
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from starlette.concurrency import run_in_threadpool

from src.api.middleware.auth import get_current_user_optional
from src.api.schemas.qa import QAResponse, QueryRequest
from src.config.database import get_db
from src.models.goal import Goal
from src.models.qa import QAInteraction
from src.models.user import User
from src.services.ai.confidence import calculate_confidence
from src.services.ai.openai_client import openai_client
from src.services.ai.prompts import PromptTemplates
from src.services.ai.query_analyzer import QueryAnalyzer
from src.services.qa.conversation_history import ConversationHistory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["qa"])

# Matches a trailing "CONFIDENCE: ..." line (tolerant of whitespace/case).
# The value itself is validated separately so malformed values still get
# stripped from the visible answer.
_CONFIDENCE_LINE_RE = re.compile(
    r"\n?[ \t]*CONFIDENCE:[ \t]*(\S*)[ \t]*$",
    re.IGNORECASE,
)


def extract_llm_confidence(answer: str) -> Tuple[str, Optional[float]]:
    """
    Extract a trailing "CONFIDENCE: 0.NN" line from an LLM answer.

    Returns:
        (stripped_answer, confidence) - confidence is None if the line is
        absent or its value is malformed/out-of-range. The stripped_answer
        never includes the CONFIDENCE line, regardless of whether extraction
        of the value succeeded. If stripping the CONFIDENCE line would leave
        an empty answer (e.g. the whole input was just the CONFIDENCE line),
        the original unstripped text is returned instead - a visible
        confidence line is preferable to a blank answer.
    """
    match = _CONFIDENCE_LINE_RE.search(answer)
    if not match:
        return answer, None

    stripped_answer = answer[: match.start()].rstrip()
    if not stripped_answer:
        stripped_answer = answer

    try:
        confidence = float(match.group(1))
    except ValueError:
        return stripped_answer, None

    if not (0.0 <= confidence <= 1.0):
        return stripped_answer, None

    return stripped_answer, confidence


@router.post("/query", response_model=dict)
async def submit_query(
    request: QueryRequest,
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Submit a student query and get AI-generated answer with confidence

    Called by React frontend
    """
    # Get student from database
    student = db.query(User).filter(User.id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Validate goal_id if provided and check question limit
    goal_id_uuid = None
    if request.goal_id:
        try:
            goal_id_uuid = uuid.UUID(request.goal_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid goal_id format")

        # Verify goal exists and belongs to the student
        goal = (
            db.query(Goal)
            .filter(Goal.id == goal_id_uuid, Goal.student_id == request.student_id)
            .first()
        )
        if not goal:
            raise HTTPException(
                status_code=404, detail="Goal not found or does not belong to student"
            )

        # Check question limit: 20 questions per user per goal per day
        # Count only questions from today (UTC)
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        question_count = (
            db.query(QAInteraction)
            .filter(
                QAInteraction.student_id == request.student_id,
                QAInteraction.goal_id == goal_id_uuid,
                QAInteraction.created_at >= today_start,
            )
            .count()
        )

        if question_count >= 20:
            raise HTTPException(
                status_code=429,
                detail=f"Daily question limit reached. You have reached the maximum of 20 questions for this goal today. The limit will reset tomorrow. Please contact your tutor for additional assistance.",
            )

    # Check if disclaimer has been shown
    disclaimer_shown = student.disclaimer_shown

    # Get conversation history for context
    conversation_history = ConversationHistory(db)
    history_context = conversation_history.get_conversation_context(
        student_id=request.student_id, current_query=request.query
    )

    # Check if this is a follow-up question
    is_follow_up = conversation_history.is_follow_up_question(
        student_id=request.student_id, current_query=request.query
    )

    # Merge conversation history into context
    context = request.context or {}
    if history_context.get("recent_interactions"):
        context["conversation_history"] = history_context["recent_interactions"][
            :3
        ]  # Last 3 interactions
        context["topics_discussed"] = history_context.get("topics_discussed", [])

    # Analyze query for edge cases
    analyzer = QueryAnalyzer()
    query_analysis = analyzer.analyze_query(request.query, context)

    # Enhance analysis with follow-up detection
    if is_follow_up:
        query_analysis["is_follow_up"] = True
        if not query_analysis.get("is_ambiguous"):
            # Follow-ups might need special handling
            query_analysis["confidence_impact"] = (
                query_analysis.get("confidence_impact", 1.0) * 0.9
            )

    logger.info(
        f"Query analysis for student {request.student_id}: "
        f"ambiguous={query_analysis['is_ambiguous']}, "
        f"multi_part={query_analysis['is_multi_part']}, "
        f"out_of_scope={query_analysis['is_out_of_scope']}"
    )

    # Handle out-of-scope queries immediately
    if query_analysis["is_out_of_scope"]:
        answer = (
            "I'm designed to help with educational topics like math, science, literature, and test prep. "
            "I can't assist with non-academic questions like weather, sports, or general information. "
            "Is there an academic topic I can help you with instead?"
        )
        confidence_result = {
            "confidence": "Low",
            "confidence_score": 0.0,
            "factors": {"out_of_scope": True},
        }
        escalation = None
        clarification_requested = False
        out_of_scope = True
    else:
        # Generate answer using AI with edge case handling and conversation history
        # Include conversation history in prompt context
        conversation_context_str = ""
        if context.get("conversation_history"):
            conversation_context_str = "\n\nRecent conversation:\n"
            for i, hist in enumerate(context["conversation_history"][:3], 1):
                conversation_context_str += f"{i}. Q: {hist['query'][:100]}...\n   A: {hist['answer'][:150]}...\n"

        prompt = PromptTemplates.qa_answer_prompt(
            query=request.query,
            context=context,
            recent_sessions=context.get("recent_sessions"),
            current_practice=context.get("current_practice"),
            is_ambiguous=query_analysis["is_ambiguous"],
            is_multi_part=query_analysis["is_multi_part"],
            is_out_of_scope=query_analysis["is_out_of_scope"],
            query_parts=query_analysis.get("parts"),
        )

        # Enhance prompt with conversation history if available
        if conversation_context_str and len(prompt) > 0:
            # Add conversation context to system message or first user message
            if prompt[0].get("role") == "system":
                prompt[0]["content"] += conversation_context_str
            elif len(prompt) > 1 and prompt[1].get("role") == "user":
                prompt[1]["content"] = (
                    conversation_context_str
                    + "\n\nCurrent question: "
                    + prompt[1]["content"]
                )

        try:
            answer = await run_in_threadpool(openai_client.chat_completion, prompt)
        except Exception as e:
            logger.error(f"Failed to generate answer: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to generate answer: {str(e)}"
            )

        # Extract the model's self-assessed confidence (trailing "CONFIDENCE:
        # 0.NN" line) so a separate confidence-assessment API call isn't
        # needed. Falls back to None (legacy behavior) if the model omits it.
        answer, llm_confidence = extract_llm_confidence(answer)

        # Calculate confidence with query analysis. calculate_confidence still
        # falls back to a synchronous chat_completion call when llm_confidence
        # is None (e.g. the model omitted the CONFIDENCE line), so offload it
        # the same way to avoid blocking the event loop.
        confidence_result = await run_in_threadpool(
            calculate_confidence,
            query=request.query,
            answer=answer,
            context=context,
            query_analysis=query_analysis,
            llm_confidence=llm_confidence,
        )

        # Determine escalation - enhanced logic
        escalation = None
        if confidence_result["confidence"] == "Low":
            escalation = {
                "suggested": True,
                "reason": "Low confidence answer - advanced topic requiring expert guidance",
                "message": "I recommend discussing this with your tutor for a more detailed explanation.",
            }
        elif query_analysis["is_ambiguous"]:
            # For ambiguous queries, suggest clarification
            escalation = {
                "suggested": False,
                "clarification_needed": True,
                "suggestions": query_analysis.get("suggestions", []),
            }

        # Check for clarification requests and out-of-scope in answer
        clarification_requested = (
            query_analysis["is_ambiguous"]
            or "clarif" in answer.lower()
            or "more context" in answer.lower()
            or "which" in answer.lower()
            and "?" in answer
        )
        out_of_scope = (
            query_analysis["is_out_of_scope"]
            or "can't help" in answer.lower()
            or "out of scope" in answer.lower()
            or "not designed" in answer.lower()
            or "outside" in answer.lower()
        )

    # Store interaction
    interaction = QAInteraction(
        id=uuid.uuid4(),
        student_id=uuid.UUID(request.student_id),
        goal_id=goal_id_uuid,
        query=request.query,
        answer=answer,
        confidence=confidence_result["confidence"],
        confidence_score=confidence_result["confidence_score"],
        context_subjects=context.get("recent_sessions", []),
        clarification_requested=clarification_requested,
        out_of_scope=out_of_scope,
        tutor_escalation_suggested=(confidence_result["confidence"] == "Low"),
        disclaimer_shown=disclaimer_shown,
    )

    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    # Gamification removed - no longer awarding XP
    xp_result = None

    # Build response with edge case metadata
    response_data = {
        "interaction_id": str(interaction.id),
        "query": request.query,
        "answer": answer,
        "confidence": confidence_result["confidence"],
        "confidence_score": float(confidence_result["confidence_score"]),
        "disclaimer_shown": disclaimer_shown,
        "escalation": escalation,
        "metadata": {
            "clarification_requested": clarification_requested,
            "out_of_scope": out_of_scope,
            "is_ambiguous": query_analysis["is_ambiguous"],
            "is_multi_part": query_analysis["is_multi_part"],
            "is_follow_up": query_analysis.get("is_follow_up", False),
            "query_parts": query_analysis.get("parts")
            if query_analysis["is_multi_part"]
            else None,
            "conversation_context_used": len(
                history_context.get("recent_interactions", [])
            )
            > 0,
        },
    }

    # Gamification removed - no longer included in response

    # Add clarification suggestions if ambiguous
    if query_analysis["is_ambiguous"] and query_analysis.get("suggestions"):
        response_data["clarification_suggestions"] = query_analysis["suggestions"]

    return {"success": True, "data": response_data}
