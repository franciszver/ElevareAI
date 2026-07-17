"""
Prompt Templates
Structured prompts for different AI tasks
"""

from typing import Dict, List, Optional


class PromptTemplates:
    """Centralized prompt templates for AI tasks"""

    @staticmethod
    def session_summary_prompt(
        transcript: str,
        session_duration_minutes: int,
        subject: str,
        topics_covered: List[str],
        student_name: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Generate prompt for session summary

        Returns:
            List of messages for chat completion
        """
        topics_str = ", ".join(topics_covered) if topics_covered else subject

        return [
            {
                "role": "system",
                "content": """You are an AI assistant that creates helpful, encouraging summaries of tutoring sessions. 
Your summaries should:
1. Be written in a warm, supportive tone
2. Highlight what the student learned/accomplished
3. Provide 2-3 specific, actionable next steps
4. Be concise but informative
5. If the session was brief or transcript is missing, acknowledge it gracefully

Format your response as a narrative summary followed by clear next steps.""",
            },
            {
                "role": "user",
                "content": f"""Create a summary for a {session_duration_minutes}-minute tutoring session.

Subject: {subject}
Topics covered: {topics_str}
{"Student name: " + student_name if student_name else ""}

Transcript:
{transcript}

Generate a narrative summary and 2-3 actionable next steps.""",
            },
        ]

    @staticmethod
    def practice_generation_prompt(
        subject: str,
        topic: str,
        difficulty_level: int,
        goal_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Generate prompt for AI practice item generation
        """
        goal_context = f" aligned with {', '.join(goal_tags)}" if goal_tags else ""

        return [
            {
                "role": "system",
                "content": """You are an AI assistant that creates educational multiple-choice practice problems. 
Your problems should:
1. Be appropriate for the specified difficulty level (1-10 scale)
2. Be clear and unambiguous
3. Include exactly 4 answer choices (A, B, C, D)
4. Have one clearly correct answer
5. Include 3 plausible distractors (wrong answers)
6. Include a brief explanation of why the correct answer is right
7. Be educational and help students learn
8. Match the subject and topic exactly

Format your response as JSON with:
- question_text: The question
- choices: Array of 4 options ["A) option1", "B) option2", "C) option3", "D) option4"]
- correct_answer: The letter of the correct answer (A, B, C, or D)
- answer_text: The full text of the correct answer choice
- explanation: Brief explanation of why the correct answer is right

Your response must be a single valid JSON object. Do NOT use LaTeX delimiters like \\( \\) or \\[ \\] and do NOT include unescaped backslashes inside JSON strings. Write math in plain text (e.g. x^2 - 5x + 6 = 0).""",
            },
            {
                "role": "user",
                "content": f"""Create a multiple-choice practice problem for:
Subject: {subject}
Topic: {topic}
Difficulty Level: {difficulty_level}/10
Goal Context: {goal_context if goal_tags else 'General practice'}

Provide a JSON response with:
- question_text: The question
- choices: Array of exactly 4 answer choices
- correct_answer: The letter (A, B, C, or D) of the correct answer
- answer_text: The full text of the correct answer
- explanation: Brief explanation""",
            },
        ]

    @staticmethod
    def qa_answer_prompt(
        query: str,
        context: Optional[Dict] = None,
        recent_sessions: Optional[List[str]] = None,
        current_practice: Optional[str] = None,
        is_ambiguous: bool = False,
        is_multi_part: bool = False,
        is_out_of_scope: bool = False,
        query_parts: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Generate prompt for Q&A answer with edge case handling
        """
        context_parts = []
        if recent_sessions:
            context_parts.append(f"Recent sessions: {', '.join(recent_sessions)}")
        if current_practice:
            context_parts.append(f"Current practice: {current_practice}")

        context_str = (
            "\n".join(context_parts)
            if context_parts
            else "No specific context available."
        )

        # Build system message based on query type
        if is_out_of_scope:
            system_message = """You are an AI study companion helping students with educational topics. 
The student's query appears to be outside the scope of educational assistance. 
Politely redirect them to educational topics and explain that you're designed to help with academic subjects."""
        elif is_ambiguous:
            system_message = """You are an AI study companion helping students between tutoring sessions. 
The student's query is ambiguous and lacks context. Ask for clarification by:
1. Suggesting likely topics based on their recent sessions
2. Asking which specific concept they need help with
3. Being encouraging and helpful"""
        elif is_multi_part:
            system_message = """You are an AI study companion helping students between tutoring sessions. 
The student's query contains multiple questions. Answer each part clearly and separately.
Format your response with clear sections for each question."""
        else:
            system_message = """You are an AI study companion helping students between tutoring sessions. 
Your role is to:
1. Provide clear, educational answers
2. Explain concepts in a way appropriate for students
3. If you're unsure or the topic is advanced, acknowledge limitations
4. Suggest consulting with their tutor for complex topics
5. Be encouraging and supportive"""

        # Build user message
        if is_multi_part and query_parts:
            query_text = "The student asked multiple questions:\n"
            for i, part in enumerate(query_parts, 1):
                query_text += f"{i}. {part}\n"
        else:
            query_text = f"Student query: {query}"

        return [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": f"""{query_text}

Context:
{context_str}

Provide a helpful answer. If the query is ambiguous, ask for clarification.
If you're not confident, acknowledge it and suggest consulting their tutor.

After your answer, on a new final line, self-assess your confidence in the answer using EXACTLY this format (a number between 0.00 and 1.00, two decimal places):
CONFIDENCE: 0.NN""",
            },
        ]

    @staticmethod
    def confidence_assessment_prompt(query: str, answer: str) -> List[Dict[str, str]]:
        """
        Prompt for LLM self-assessment of confidence
        """
        return [
            {
                "role": "system",
                "content": """You are evaluating the confidence level of an AI-generated educational answer. 
Rate your confidence on a scale of 0.0 to 1.0 considering:
- Completeness of information
- Accuracy and correctness
- Alignment with educational standards
- Potential for misunderstanding
- Need for human verification

Respond with ONLY a number between 0.0 and 1.0 (e.g., 0.85).""",
            },
            {
                "role": "user",
                "content": f"""Query: {query}

Answer: {answer}

Rate your confidence in this answer (0.0 to 1.0):""",
            },
        ]
