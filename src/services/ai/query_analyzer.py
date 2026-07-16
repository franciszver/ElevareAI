"""
Query Analysis Service
Detects ambiguous, multi-part, and out-of-scope queries
"""

import re
from typing import Dict, List, Tuple


class QueryAnalyzer:
    """Analyzes student queries to detect edge cases"""

    # Patterns that indicate ambiguity
    AMBIGUOUS_PATTERNS = [
        r"\b(this|that|it)\b",  # Vague references
        r"\b(don\'?t get|don\'?t understand|confused|unclear)\b",  # Confusion without context
        r"^\s*(what|how|why)\s*\?*\s*$",  # Single word questions
        r"^\s*(help|explain)\s*$",  # Just "help" or "explain"
    ]

    # Patterns that indicate multiple questions
    MULTI_PART_INDICATORS = [
        r"\b(and|also|plus|additionally|furthermore)\b.*\?",  # "and" followed by question
        r"\?\s*[A-Z]",  # Multiple question marks or sentences after question
        r"explain\s+\w+.*(and|also).*explain",  # Multiple "explain" statements
    ]

    # Patterns that indicate out-of-scope
    OUT_OF_SCOPE_PATTERNS = [
        r"\b(weather|temperature|forecast)\b",
        r"\b(sports|game|score|team)\b",
        r"\b(movie|film|actor|celebrity)\b",
        r"\b(cooking|recipe|food)\b",
        r"\b(travel|vacation|hotel|flight)\b",
        r"\b(shopping|buy|purchase|price)\b",
    ]

    # Educational keywords (to help detect if query is educational)
    EDUCATIONAL_KEYWORDS = [
        "math",
        "algebra",
        "geometry",
        "calculus",
        "physics",
        "chemistry",
        "biology",
        "science",
        "history",
        "english",
        "literature",
        "essay",
        "writing",
        "reading",
        "problem",
        "equation",
        "formula",
        "theorem",
        "concept",
        "theory",
        "practice",
        "homework",
        "assignment",
        "study",
        "learn",
        "understand",
        "explain",
        "solve",
        "sat",
        "ap",
        "test",
        "exam",
        "quiz",
        "review",
        "study guide",
    ]

    def analyze_query(self, query: str, context: Dict = None) -> Dict:
        """
        Analyze query for edge cases

        Returns:
            dict with 'is_ambiguous', 'is_multi_part', 'is_out_of_scope',
            'parts' (if multi-part), 'suggestions' (if ambiguous)
        """
        query_lower = query.lower().strip()

        result = {
            "is_ambiguous": False,
            "is_multi_part": False,
            "is_out_of_scope": False,
            "parts": [],
            "suggestions": [],
            "confidence_impact": 1.0,
        }

        # Check for ambiguity
        result["is_ambiguous"] = self._is_ambiguous(query_lower)
        if result["is_ambiguous"]:
            result["suggestions"] = self._generate_ambiguity_suggestions(query, context)
            result["confidence_impact"] = 0.5  # Reduce confidence for ambiguous queries

        # Check for multi-part
        result["is_multi_part"] = self._is_multi_part(query)
        if result["is_multi_part"]:
            result["parts"] = self._split_multi_part(query)

        # Check for out-of-scope
        result["is_out_of_scope"] = self._is_out_of_scope(query_lower)
        if result["is_out_of_scope"]:
            result["confidence_impact"] = 0.0  # Zero confidence for out-of-scope

        return result

    def _is_ambiguous(self, query: str) -> bool:
        """Check if query is ambiguous"""
        # Very short queries are likely ambiguous
        if len(query.split()) <= 3:
            # Unless they contain educational keywords
            has_educational = any(
                keyword in query for keyword in self.EDUCATIONAL_KEYWORDS
            )
            if not has_educational:
                return True

        # Check against ambiguous patterns
        for pattern in self.AMBIGUOUS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                # Check if it has context (recent sessions, etc.)
                if not self._has_context(query):
                    return True

        return False

    def _has_context(self, query: str) -> bool:
        """Check if query has enough context"""
        # If query mentions specific subjects, topics, or concepts, it has context
        educational_mentions = sum(
            1 for keyword in self.EDUCATIONAL_KEYWORDS if keyword in query
        )
        return educational_mentions >= 1

    def _is_multi_part(self, query: str) -> bool:
        """Check if query contains multiple questions"""
        # Count question marks
        question_count = query.count("?")
        if question_count > 1:
            return True

        # Check for multi-part indicators
        for pattern in self.MULTI_PART_INDICATORS:
            if re.search(pattern, query, re.IGNORECASE | re.DOTALL):
                return True

        # Check for "and" or "also" connecting two educational topics
        if re.search(r"\b(and|also)\b", query, re.IGNORECASE):
            # Split by "and" or "also" and check if both parts are substantial
            parts = re.split(r"\b(and|also)\b", query, flags=re.IGNORECASE)
            if len(parts) >= 3:
                # Check if parts before and after connector are substantial
                before = parts[0].strip()
                after = parts[-1].strip()
                # Both parts should have at least 2 words and be educational
                before_words = len(before.split())
                after_words = len(after.split())
                if before_words >= 2 and after_words >= 2:
                    # Check if both parts contain educational keywords or action words
                    action_words = [
                        "explain",
                        "help",
                        "show",
                        "solve",
                        "understand",
                        "learn",
                    ]
                    has_action = any(
                        word in before.lower() or word in after.lower()
                        for word in action_words
                    )
                    has_educational = any(
                        kw in before.lower() or kw in after.lower()
                        for kw in self.EDUCATIONAL_KEYWORDS
                    )
                    if has_action or has_educational:
                        return True

        # Check for multiple sentences that could be questions
        sentences = re.split(r"[.!?]\s+", query)
        if len(sentences) > 1:
            # Check if multiple sentences are questions or requests
            question_sentences = [
                s
                for s in sentences
                if "?" in s
                or any(
                    word in s.lower()
                    for word in ["explain", "help", "how", "what", "why"]
                )
            ]
            if len(question_sentences) > 1:
                return True

        return False

    def _split_multi_part(self, query: str) -> List[str]:
        """Split multi-part query into individual questions"""
        parts = []

        # Split by question marks first
        if query.count("?") > 1:
            parts = [p.strip() + "?" for p in query.split("?") if p.strip()]
        # Split by "and" or "also"
        elif re.search(r"\b(and|also)\b", query, re.IGNORECASE):
            split_parts = re.split(r"\b(and|also)\b", query, flags=re.IGNORECASE)
            # Take first part and last part (skip the connector)
            if len(split_parts) >= 3:
                parts = [split_parts[0].strip(), split_parts[-1].strip()]
        else:
            # Try to split by sentence boundaries
            sentences = re.split(r"[.!?]\s+", query)
            if len(sentences) > 1:
                parts = [
                    s.strip() for s in sentences if s.strip() and len(s.split()) >= 3
                ]

        # If we couldn't split meaningfully, return original as single part
        if not parts or len(parts) < 2:
            return [query]

        return parts

    def _is_out_of_scope(self, query: str) -> bool:
        """Check if query is out of educational scope"""
        # Check against out-of-scope patterns
        for pattern in self.OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                # But check if it's actually educational (e.g., "weather patterns in science")
                if not any(keyword in query for keyword in self.EDUCATIONAL_KEYWORDS):
                    return True

        return False

    def _generate_ambiguity_suggestions(
        self, query: str, context: Dict = None
    ) -> List[str]:
        """Generate suggestions for clarifying ambiguous queries"""
        suggestions = []

        # If we have context (recent sessions), suggest those topics
        if context:
            recent_sessions = context.get("recent_sessions", [])
            if recent_sessions:
                suggestions.append(f"Are you asking about {recent_sessions[0]}?")
                if len(recent_sessions) > 1:
                    suggestions.append(f"Or perhaps {recent_sessions[1]}?")

        # Generic suggestions
        if not suggestions:
            suggestions = [
                "Could you provide more context? What subject or topic are you asking about?",
                "Which specific concept would you like help with?",
                "Are you asking about a recent session topic or practice problem?",
            ]

        return suggestions
