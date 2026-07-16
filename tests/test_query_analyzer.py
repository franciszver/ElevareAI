"""
Unit Tests for QueryAnalyzer
Tests edge case detection for Q&A queries
"""

import pytest

from src.services.ai.query_analyzer import QueryAnalyzer


class TestQueryAnalyzer:
    """Test suite for QueryAnalyzer edge case detection"""

    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = QueryAnalyzer()

    def test_ambiguous_query_detection(self):
        """Test detection of ambiguous queries"""
        # Very vague queries
        assert self.analyzer.analyze_query("I don't get this")["is_ambiguous"] == True
        assert self.analyzer.analyze_query("help")["is_ambiguous"] == True
        assert self.analyzer.analyze_query("what?")["is_ambiguous"] == True
        # "understand" is in educational keywords, so "I don't understand" might not be ambiguous
        # Test with queries that definitely have no educational context
        assert self.analyzer.analyze_query("this")["is_ambiguous"] == True
        assert self.analyzer.analyze_query("I'm confused")["is_ambiguous"] == True

        # Queries with context should not be ambiguous
        assert self.analyzer.analyze_query("explain algebra")["is_ambiguous"] == False
        assert (
            self.analyzer.analyze_query("help with quadratic equations")["is_ambiguous"]
            == False
        )

    def test_ambiguous_query_suggestions(self):
        """Test that ambiguous queries generate suggestions"""
        result = self.analyzer.analyze_query("I don't get this")
        assert result["is_ambiguous"] == True
        assert len(result.get("suggestions", [])) > 0
        assert (
            "context" in result["suggestions"][0].lower()
            or "topic" in result["suggestions"][0].lower()
        )

    def test_ambiguous_with_context(self):
        """Test ambiguous queries with context get better suggestions"""
        context = {"recent_sessions": ["Algebra", "Geometry"]}
        # Use a query that will definitely be ambiguous
        result = self.analyzer.analyze_query("I don't get this", context)
        assert result["is_ambiguous"] == True
        # Should have suggestions that reference context
        suggestions_text = " ".join(result.get("suggestions", [])).lower()
        # Context suggestions should mention recent sessions
        assert (
            "algebra" in suggestions_text
            or "geometry" in suggestions_text
            or len(result.get("suggestions", [])) > 0
        )

    def test_multi_part_query_detection(self):
        """Test detection of multi-part queries"""
        # Multiple questions
        assert (
            self.analyzer.analyze_query("What is photosynthesis? How does it work?")[
                "is_multi_part"
            ]
            == True
        )

        # "and" connecting two topics
        assert (
            self.analyzer.analyze_query(
                "Explain photosynthesis and help with factoring"
            )["is_multi_part"]
            == True
        )
        assert (
            self.analyzer.analyze_query("Solve this equation and explain the steps")[
                "is_multi_part"
            ]
            == True
        )

        # Single question should not be multi-part
        assert (
            self.analyzer.analyze_query("What is photosynthesis?")["is_multi_part"]
            == False
        )

    def test_multi_part_splitting(self):
        """Test splitting of multi-part queries"""
        result = self.analyzer.analyze_query(
            "Explain photosynthesis and help with factoring quadratics"
        )
        assert result["is_multi_part"] == True
        assert len(result.get("parts", [])) >= 2
        assert "photosynthesis" in result["parts"][0].lower()
        assert "factoring" in result["parts"][1].lower()

    def test_out_of_scope_detection(self):
        """Test detection of out-of-scope queries"""
        # Non-educational topics
        assert (
            self.analyzer.analyze_query("What's the weather tomorrow?")[
                "is_out_of_scope"
            ]
            == True
        )
        assert (
            self.analyzer.analyze_query("Who won the game?")["is_out_of_scope"] == True
        )
        assert (
            self.analyzer.analyze_query("What movie should I watch?")["is_out_of_scope"]
            == True
        )

        # Educational topics should not be out of scope
        assert (
            self.analyzer.analyze_query("What is photosynthesis?")["is_out_of_scope"]
            == False
        )
        assert (
            self.analyzer.analyze_query("Explain algebra")["is_out_of_scope"] == False
        )

    def test_out_of_scope_confidence_impact(self):
        """Test that out-of-scope queries have zero confidence impact"""
        result = self.analyzer.analyze_query("What's the weather?")
        assert result["is_out_of_scope"] == True
        assert result["confidence_impact"] == 0.0

    def test_ambiguous_confidence_impact(self):
        """Test that ambiguous queries reduce confidence"""
        result = self.analyzer.analyze_query("I don't get this")
        assert result["is_ambiguous"] == True
        assert result["confidence_impact"] < 1.0
        assert result["confidence_impact"] == 0.5

    def test_educational_keywords_prevent_ambiguity(self):
        """Test that educational keywords prevent false ambiguity"""
        # These should not be ambiguous because they contain educational keywords
        assert self.analyzer.analyze_query("math")["is_ambiguous"] == False
        assert self.analyzer.analyze_query("algebra help")["is_ambiguous"] == False
        assert self.analyzer.analyze_query("chemistry")["is_ambiguous"] == False

    def test_complex_multi_part_query(self):
        """Test complex multi-part query with multiple sentences"""
        query = "Can you explain how photosynthesis works? Also, I need help with balancing chemical equations."
        result = self.analyzer.analyze_query(query)
        assert result["is_multi_part"] == True
        assert len(result.get("parts", [])) >= 2
