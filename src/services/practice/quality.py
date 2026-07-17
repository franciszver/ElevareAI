"""
Practice Item Quality Service
Quality validation and improvement for generated practice items
"""

import json
import random
import re
from typing import Dict, List, Optional

from src.services.ai.openai_client import openai_client
from src.services.ai.prompts import PromptTemplates


class PracticeQualityService:
    """Service for validating and improving practice item quality"""

    def __init__(self):
        self.openai = openai_client

    def validate_practice_item(self, item: Dict) -> Dict:
        """
        Validate practice item quality

        Args:
            item: Practice item dict with question_text, answer_text, explanation, choices, correct_answer

        Returns:
            Validation result with quality_score and issues
        """
        issues = []
        quality_score = 1.0

        # Check question quality
        question = item.get("question_text", "").strip()
        if not question:
            issues.append("Missing question text")
            quality_score -= 0.5
        elif len(question) < 20:
            issues.append("Question too short (minimum 20 characters)")
            quality_score -= 0.2
        elif len(question) > 500:
            issues.append("Question too long (maximum 500 characters)")
            quality_score -= 0.1

        # Check multiple choice format
        choices = item.get("choices", [])
        if not choices or not isinstance(choices, list):
            issues.append("Missing multiple choice options")
            quality_score -= 0.3
        elif len(choices) < 4:
            issues.append(f"Not enough choices (expected 4, got {len(choices)})")
            quality_score -= 0.2
        elif len(choices) > 4:
            issues.append(f"Too many choices (expected 4, got {len(choices)})")
            quality_score -= 0.1

        # Check correct answer
        correct_answer = item.get("correct_answer", "").strip().upper()
        if not correct_answer or correct_answer not in ["A", "B", "C", "D"]:
            issues.append("Missing or invalid correct_answer (must be A, B, C, or D)")
            quality_score -= 0.3

        # Check answer quality
        answer = item.get("answer_text", "").strip()
        if not answer:
            issues.append("Missing answer text")
            quality_score -= 0.3
        elif len(answer) < 5:
            issues.append("Answer too short")
            quality_score -= 0.2

        # Check explanation quality
        explanation = item.get("explanation", "").strip()
        if not explanation:
            issues.append("Missing explanation")
            quality_score -= 0.2
        elif len(explanation) < 30:
            issues.append("Explanation too short (minimum 30 characters)")
            quality_score -= 0.1

        # Check for common issues
        if (
            "?" not in question
            and "what" not in question.lower()
            and "how" not in question.lower()
        ):
            issues.append("Question may not be properly formatted")
            quality_score -= 0.1

        quality_score = max(0.0, quality_score)

        return {
            "quality_score": round(quality_score, 2),
            "is_valid": quality_score >= 0.7,
            "issues": issues,
        }

    def improve_practice_item(
        self, item: Dict, subject: str, topic: str, difficulty_level: int
    ) -> Dict:
        """
        Improve practice item quality using AI

        Args:
            item: Practice item to improve
            subject: Subject name
            topic: Topic name
            difficulty_level: Difficulty level

        Returns:
            Improved practice item
        """
        validation = self.validate_practice_item(item)

        if validation["is_valid"]:
            return item

        # Use AI to improve the item
        improvement_prompt = [
            {
                "role": "system",
                "content": f"You are an expert educational content creator. Improve the following practice question for {subject} - {topic} (Difficulty: {difficulty_level}/10).",
            },
            {
                "role": "user",
                "content": f"""Current practice item:
Question: {item.get('question_text', '')}
Answer: {item.get('answer_text', '')}
Explanation: {item.get('explanation', '')}
Choices: {item.get('choices', [])}
Correct answer: {item.get('correct_answer', '')}

Issues found: {', '.join(validation['issues'])}

Please provide an improved version in JSON format:
{{
  "question_text": "...",
  "answer_text": "...",
  "explanation": "...",
  "choices": ["A) option1", "B) option2", "C) option3", "D) option4"],
  "correct_answer": "A"
}}

Include exactly 4 answer choices with one clearly correct answer. Your response must be a single valid JSON object. Do NOT use LaTeX delimiters like \\( \\) or \\[ \\] and do NOT include unescaped backslashes inside JSON strings. Write math in plain text (e.g. x^2 - 5x + 6 = 0).""",
            },
        ]

        try:
            ai_response = self.openai.chat_completion(
                improvement_prompt, response_format={"type": "json_object"}
            )

            # Try to parse JSON response
            json_match = re.search(
                r'\{[^{}]*"question_text"[^{}]*\}', ai_response, re.DOTALL
            )
            if json_match:
                improved = json.loads(json_match.group())
                # Merge onto the original item so fields the model omits
                # (e.g. choices/correct_answer) aren't silently dropped.
                return {**item, **improved}

            # Fallback: parse similar to generator
            improved = self._parse_improved_response(ai_response, item)
            return {**item, **improved}

        except Exception as e:
            # Return original if improvement fails
            return item

    def _parse_improved_response(self, response: str, original: Dict) -> Dict:
        """Parse improved response from AI"""
        # Try to extract sections
        question_match = re.search(
            r"(?:question|q):\s*(.+?)(?:\n|answer|$)",
            response,
            re.IGNORECASE | re.DOTALL,
        )
        answer_match = re.search(
            r"(?:answer|a):\s*(.+?)(?:\n|explanation|$)",
            response,
            re.IGNORECASE | re.DOTALL,
        )
        explanation_match = re.search(
            r"(?:explanation|explain):\s*(.+?)$", response, re.IGNORECASE | re.DOTALL
        )

        return {
            "question_text": question_match.group(1).strip()
            if question_match
            else original.get("question_text", ""),
            "answer_text": answer_match.group(1).strip()
            if answer_match
            else original.get("answer_text", ""),
            "explanation": explanation_match.group(1).strip()
            if explanation_match
            else original.get("explanation", ""),
        }

    def generate_with_context(
        self,
        subject: str,
        topic: str,
        difficulty_level: int,
        student_history: Optional[List[Dict]] = None,
        goal_tags: Optional[List[str]] = None,
    ) -> Dict:
        """
        Generate practice item with student context

        Args:
            subject: Subject name
            topic: Topic name
            difficulty_level: Difficulty level
            student_history: List of previous practice attempts
            goal_tags: Goal tags for alignment

        Returns:
            Generated practice item
        """
        # Build context string
        context_str = ""
        if student_history:
            recent_attempts = student_history[:5]  # Last 5 attempts
            context_str = "\n\nStudent's recent practice history:\n"
            for attempt in recent_attempts:
                context_str += f"- {attempt.get('topic', 'Unknown')}: {'Correct' if attempt.get('correct') else 'Incorrect'}\n"

        # Enhanced prompt with context
        prompt = PromptTemplates.practice_generation_prompt(
            subject=subject,
            topic=topic,
            difficulty_level=difficulty_level,
            goal_tags=goal_tags,
        )

        # Add context to prompt
        if context_str and len(prompt) > 0:
            if prompt[0].get("role") == "system":
                prompt[0]["content"] += context_str

        try:
            ai_response = self.openai.chat_completion(
                prompt, response_format={"type": "json_object"}
            )

            # Try JSON parsing first
            json_match = re.search(
                r'\{[^{}]*(?:"question_text"|"choices")[^{}]*\}', ai_response, re.DOTALL
            )
            if json_match:
                try:
                    item = json.loads(json_match.group())
                    # Ensure multiple choice format
                    if "choices" not in item or not isinstance(
                        item.get("choices"), list
                    ):
                        # Generate choices if missing
                        item = self._add_multiple_choice_format(item, subject=subject)
                    # Validate and improve if needed
                    validation = self.validate_practice_item(item)
                    if not validation["is_valid"]:
                        item = self.improve_practice_item(
                            item, subject, topic, difficulty_level
                        )
                    return item
                except json.JSONDecodeError:
                    pass

            # Fallback to text parsing with multiple choice generation
            return self._parse_text_response(ai_response, subject=subject)

        except Exception as e:
            # Return multiple choice format even for errors
            error_answer = "Answer generation failed. Please consult your tutor."
            choices, correct_answer = self._generate_multiple_choice_options(
                error_answer, subject=subject
            )
            return {
                "question_text": f"Practice question for {subject} - {topic} (Difficulty: {difficulty_level})",
                "answer_text": error_answer,
                "choices": choices,
                "correct_answer": correct_answer,
                "explanation": f"AI generation encountered an error: {str(e)}",
            }

    def _parse_text_response(self, response: str, subject: str = "") -> Dict:
        """Parse text response into practice item with multiple choice format"""
        question_text = ""
        answer_text = ""
        explanation = ""
        choices = []
        correct_answer = None

        # Try to find multiple choice format (A), B), C), D))
        choice_pattern = r"([A-D])[\)\.]\s*([^\n]+)"
        found_choices = re.findall(choice_pattern, response, re.IGNORECASE)

        if len(found_choices) >= 4:
            # Found multiple choice format
            choices = [
                f"{letter.upper()}) {text.strip()}"
                for letter, text in found_choices[:4]
            ]
            # Try to find which is correct
            correct_match = re.search(
                r"(?:correct|answer|right).*?([A-D])", response, re.IGNORECASE
            )
            if correct_match:
                correct_answer = correct_match.group(1).upper()
                # Extract the correct answer text
                for letter, text in found_choices:
                    if letter.upper() == correct_answer:
                        answer_text = text.strip()
                        break
        else:
            # Generate choices from answer
            answer_text = self._extract_answer(response)
            if answer_text:
                # Generate 3 distractors and format as multiple choice
                choices, correct_answer = self._generate_multiple_choice_options(
                    answer_text, response, subject=subject
                )
                # Extract answer text from the correct choice
                for choice in choices:
                    if choice.startswith(f"{correct_answer})"):
                        answer_text = choice.replace(f"{correct_answer}) ", "")
                        break

        # Extract question
        question_match = re.search(
            r"(?:question|q)[:\s]+([^\n]+(?:\n(?!\s*[A-D][\)\.])[^\n]+)*)",
            response,
            re.IGNORECASE,
        )
        if question_match:
            question_text = question_match.group(1).strip()
        else:
            # Fallback: everything before first choice or answer
            parts = re.split(
                r"(?:answer|choices?|a\)|b\)|c\)|d\)):",
                response,
                flags=re.IGNORECASE,
                maxsplit=1,
            )
            question_text = parts[0].replace("Question:", "").replace("Q:", "").strip()

        # Extract explanation
        explanation_match = re.search(
            r"(?:explanation|explain|why)[:\s]+([^\n]+(?:\n[^\n]+)*)",
            response,
            re.IGNORECASE,
        )
        if explanation_match:
            explanation = explanation_match.group(1).strip()
        else:
            explanation = "See your tutor for explanation."

        # Ensure we have 4 choices
        if len(choices) < 4:
            choices, correct_answer = self._generate_multiple_choice_options(
                answer_text or "See explanation", response, subject=subject
            )
            # Extract answer text from the correct choice
            for choice in choices:
                if choice.startswith(f"{correct_answer})"):
                    answer_text = choice.replace(f"{correct_answer}) ", "")
                    break

        return {
            "question_text": question_text or response[:200],
            "choices": choices[:4],
            "correct_answer": correct_answer or "A",
            "answer_text": answer_text or choices[0].replace("A) ", "")
            if choices
            else "See explanation",
            "explanation": explanation or response,
        }

    def _extract_answer(self, response: str) -> str:
        """Extract answer from response"""
        answer_match = re.search(
            r"(?:answer|correct|right)[:\s]+([^\n]+)", response, re.IGNORECASE
        )
        if answer_match:
            return answer_match.group(1).strip()
        return ""

    def _extract_numeric_answer(self, answer: str) -> Optional[tuple]:
        """If `answer` is essentially a number (optionally with a leading
        "<var> = " prefix, e.g. "x = 5" or "12"), return (prefix, value).
        Otherwise return None."""
        match = re.fullmatch(
            r"\s*(?P<prefix>[A-Za-z]\w*\s*=\s*)?(?P<num>-?\d+(?:\.\d+)?)\s*",
            answer,
        )
        if not match:
            return None
        prefix = match.group("prefix") or ""
        return prefix, float(match.group("num"))

    def _format_numeric(self, value: float) -> str:
        """Format a numeric distractor value, matching integer/decimal style"""
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _generate_numeric_distractors(self, prefix: str, value: float) -> List[str]:
        """Generate 3 plausible numeric distractors via common-mistake
        perturbations (sign flip, off-by-common-error offsets, factor of two)"""
        candidates = [-value, value * 2]
        if value != 0:
            candidates.append(value / 2)
        candidates.extend([value + 1, value - 1, value + 2, value - 3])

        seen = {round(value, 4)}
        distractors = []
        for candidate in candidates:
            rounded = round(candidate, 4)
            if rounded in seen:
                continue
            seen.add(rounded)
            distractors.append(f"{prefix}{self._format_numeric(candidate)}")
            if len(distractors) == 3:
                break

        return distractors

    def _generate_multiple_choice_options(
        self, correct_answer: str, context: str = "", subject: str = ""
    ) -> List[str]:
        """Generate 4 multiple choice options with correct answer randomly placed"""
        numeric = self._extract_numeric_answer(correct_answer)
        if numeric:
            prefix, value = numeric
            distractors = self._generate_numeric_distractors(prefix, value)
        else:
            distractors = []

        # Last resort: generic (but subject-flavored) placeholders, only used
        # when we can't synthesize plausible distractors any other way.
        if len(distractors) < 3:
            subject_label = subject.strip() if subject else "topic"
            fallback_distractors = [
                f"A related but incorrect {subject_label} answer",
                f"Another plausible but wrong {subject_label} answer",
                f"An incorrect {subject_label} alternative",
            ]
            for fallback in fallback_distractors:
                if len(distractors) == 3:
                    break
                if fallback not in distractors:
                    distractors.append(fallback)

        # Combine correct answer with distractors
        all_options = [correct_answer] + distractors
        random.shuffle(all_options)

        # Format as A, B, C, D
        letters = ["A", "B", "C", "D"]
        options = [
            f"{letter}) {option}" for letter, option in zip(letters, all_options)
        ]

        # Find which letter has the correct answer
        correct_letter = None
        for i, option in enumerate(all_options):
            if option == correct_answer:
                correct_letter = letters[i]
                break

        return options, correct_letter or "A"

    def _add_multiple_choice_format(self, item: Dict, subject: str = "") -> Dict:
        """Add multiple choice format to item if missing"""
        if "choices" not in item or not isinstance(item.get("choices"), list):
            answer = item.get("answer_text", "See explanation")
            choices, correct_letter = self._generate_multiple_choice_options(
                answer, subject=subject
            )
            item["choices"] = choices
            item["correct_answer"] = correct_letter
            # Update answer_text to match the correct choice
            for choice in choices:
                if choice.startswith(f"{correct_letter})"):
                    item["answer_text"] = choice.replace(f"{correct_letter}) ", "")
                    break
        return item
