"""
Session Summarizer Service
Generates AI summaries from tutoring session transcripts
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.models.session import Session as SessionModel
from src.models.summary import Summary
from src.models.user import User
from src.services.ai.openai_client import openai_client
from src.services.ai.prompts import PromptTemplates

logger = logging.getLogger(__name__)


class SessionSummarizer:
    """Service for generating session summaries"""

    def __init__(self):
        self.openai = openai_client

    async def generate_summary(
        self,
        session_id: str,
        student_id: str,
        tutor_id: str,
        transcript: Optional[str],
        session_duration_minutes: int,
        subject: str,
        topics_covered: List[str],
        db,
    ) -> Summary:
        """
        Generate AI summary from session transcript

        Returns:
            Summary model instance
        """
        # Handle missing transcript
        if not transcript or transcript.strip() == "":
            narrative = (
                f"Transcript unavailable for this {session_duration_minutes}-minute session. "
                f"Based on the session metadata, you covered {subject}. "
                f"Limited recap generated - please review your session notes for details."
            )
            next_steps = [
                "Review previous session notes and practice materials",
                "Prepare specific questions for your next tutoring session",
                "Continue working on assigned practice problems",
            ]
            summary_type = "missing_transcript"
        else:
            # Generate summary using AI
            prompt = PromptTemplates.session_summary_prompt(
                transcript=transcript,
                session_duration_minutes=session_duration_minutes,
                subject=subject,
                topics_covered=topics_covered,
            )

            try:
                ai_response = self.openai.chat_completion(prompt)

                # Parse response (simple approach - can be improved)
                # Expected format: narrative text, then "Next steps:" followed by steps
                if (
                    "next steps" in ai_response.lower()
                    or "next:" in ai_response.lower()
                ):
                    parts = ai_response.split("next steps:", 1) or ai_response.split(
                        "next:", 1
                    )
                    narrative = parts[0].strip()
                    steps_text = parts[1].strip() if len(parts) > 1 else ""
                    # Extract steps (numbered or bulleted)
                    import re

                    steps = (
                        re.findall(r"[-•*]\s*(.+?)(?=\n|$)", steps_text)
                        or re.findall(r"\d+\.\s*(.+?)(?=\n|$)", steps_text)
                        or [s.strip() for s in steps_text.split("\n") if s.strip()]
                    )
                    next_steps = (
                        steps[:3]
                        if steps
                        else ["Review session notes", "Complete practice problems"]
                    )
                else:
                    narrative = ai_response
                    next_steps = ["Review session notes", "Complete practice problems"]

                # Determine summary type
                if session_duration_minutes < 10:
                    summary_type = "brief"
                    # Enhance narrative for brief sessions
                    narrative = (
                        f"Brief {session_duration_minutes}-minute session: {narrative}"
                    )
                else:
                    summary_type = "normal"

                # Check for mixed subjects in transcript
                # Simple heuristic: if topics_covered has multiple distinct subjects
                if topics_covered and len(topics_covered) > 2:
                    # Check if topics span multiple subject categories
                    math_keywords = [
                        "algebra",
                        "geometry",
                        "calculus",
                        "math",
                        "equation",
                        "formula",
                    ]
                    science_keywords = [
                        "chemistry",
                        "physics",
                        "biology",
                        "science",
                        "reaction",
                        "molecule",
                    ]
                    has_math = any(
                        any(kw in topic.lower() for kw in math_keywords)
                        for topic in topics_covered
                    )
                    has_science = any(
                        any(kw in topic.lower() for kw in science_keywords)
                        for topic in topics_covered
                    )

                    if has_math and has_science:
                        # Mixed subjects detected - ensure narrative acknowledges this
                        if (
                            "then" not in narrative.lower()
                            and "also" not in narrative.lower()
                        ):
                            narrative = f"In this session, you covered multiple subjects. {narrative}"

            except Exception as e:
                # Fallback if AI generation fails
                logger.error(f"AI summary generation failed: {str(e)}", exc_info=True)
                narrative = (
                    f"Summary generation encountered an issue. "
                    f"Session covered {subject} for {session_duration_minutes} minutes. "
                    f"Please review your session notes for details."
                )
                next_steps = [
                    "Review session notes and materials",
                    "Prepare questions for next session",
                    "Continue with assigned practice problems",
                ]
                summary_type = "normal"

        # Create summary record
        summary = Summary(
            id=uuid.uuid4(),
            session_id=uuid.UUID(session_id),
            student_id=uuid.UUID(student_id),
            tutor_id=uuid.UUID(tutor_id),
            narrative=narrative,
            next_steps=next_steps,
            subjects_covered=topics_covered or [subject],
            summary_type=summary_type,
            overridden=False,
        )

        db.add(summary)
        db.commit()
        db.refresh(summary)

        return summary
