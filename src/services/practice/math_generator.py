"""
Math Practice Generator
Uses SymPy for reliable mathematical problem generation and validation
"""

import random
import re
from typing import Dict, List, Optional, Tuple

from sympy import (
    Eq,
    Integer,
    Rational,
    Symbol,
    diff,
    expand,
    factor,
    integrate,
    latex,
    simplify,
    solve,
    symbols,
    sympify,
)
from sympy.parsing.sympy_parser import parse_expr


def _real_roots(roots):
    """Filter sympy roots to real ones. solve() defaults to the complex
    domain, so a negative discriminant still returns complex roots rather
    than an empty list."""
    return [r for r in roots if r.is_real]


class MathGenerator:
    """Generate and validate math practice problems using SymPy"""

    def __init__(self):
        self.x, self.y, self.z = symbols("x y z")

    def generate_linear_equation(
        self, difficulty: int = 5, variable: str = "x"
    ) -> Dict:
        """
        Generate a linear equation problem

        Args:
            difficulty: 1-10 difficulty level
            variable: Variable name (default 'x')

        Returns:
            Dict with question_text, answer_text, choices, correct_answer, explanation
        """
        var = symbols(variable)

        # Generate coefficients based on difficulty
        if difficulty <= 3:
            a = random.randint(1, 5)
            b = random.randint(1, 10)
            c = random.randint(1, 20)
        elif difficulty <= 6:
            a = random.randint(2, 10)
            b = random.randint(-10, 10)
            c = random.randint(-20, 20)
        else:
            a = random.randint(5, 15)
            b = random.randint(-15, 15)
            c = random.randint(-30, 30)

        # Create equation: ax + b = c
        equation = Eq(a * var + b, c)
        solutions = solve(equation, var)
        if not solutions:
            # Fallback: create simpler equation
            a, b, c = 2, 1, 5
            equation = Eq(a * var + b, c)
            solutions = solve(equation, var)
        solution = solutions[0] if solutions else Integer(0)

        # Format question
        if b >= 0:
            question = f"Solve for {variable}: {a}{variable} + {b} = {c}"
        else:
            question = f"Solve for {variable}: {a}{variable} - {abs(b)} = {c}"

        # Generate multiple choice options
        correct_value = float(solution.evalf())
        choices, correct_letter = self._generate_math_choices(correct_value, difficulty)

        # Generate explanation
        steps = []
        steps.append(f"Step 1: Subtract {b} from both sides")
        steps.append(f"  {a}{variable} = {c - b}")
        steps.append(f"Step 2: Divide both sides by {a}")
        steps.append(f"  {variable} = {c - b}/{a} = {correct_value}")

        explanation = "\n".join(steps)

        return {
            "question_text": question,
            "answer_text": f"{variable} = {correct_value}",
            "choices": choices,
            "correct_answer": correct_letter,
            "explanation": explanation,
            "solution": str(solution),
            "difficulty": difficulty,
        }

    def generate_quadratic_equation(
        self, difficulty: int = 5, variable: str = "x"
    ) -> Dict:
        """
        Generate a quadratic equation problem

        Args:
            difficulty: 1-10 difficulty level
            variable: Variable name (default 'x')

        Returns:
            Dict with question_text, answer_text, choices, correct_answer, explanation
        """
        var = symbols(variable)

        # Generate simple quadratic: x^2 + bx + c = 0
        if difficulty <= 4:
            # Factorable quadratics
            root1 = random.randint(-5, 5)
            root2 = random.randint(-5, 5)
            b = -(root1 + root2)
            c = root1 * root2
            a = 1
        elif difficulty <= 7:
            # Slightly more complex
            root1 = random.randint(-8, 8)
            root2 = random.randint(-8, 8)
            b = -(root1 + root2)
            c = root1 * root2
            a = random.choice([1, 2])
        else:
            # General quadratics
            a = random.randint(1, 5)
            b = random.randint(-10, 10)
            c = random.randint(-20, 20)
            roots = _real_roots(solve(Eq(a * var**2 + b * var + c, 0), var))
            if len(roots) == 0:
                # No real roots, try again with simpler
                return self.generate_quadratic_equation(difficulty - 2, variable)
            root1 = roots[0]
            root2 = roots[1] if len(roots) > 1 else root1

        # Format question
        if a == 1:
            eq_str = f"{variable}²"
        else:
            eq_str = f"{a}{variable}²"

        if b > 0:
            eq_str += f" + {b}{variable}"
        elif b < 0:
            eq_str += f" - {abs(b)}{variable}"

        if c > 0:
            eq_str += f" + {c}"
        elif c < 0:
            eq_str += f" - {abs(c)}"

        question = f"Solve for {variable}: {eq_str} = 0"

        # Get solutions
        equation = Eq(a * var**2 + b * var + c, 0)
        # Filter to real roots so we never try to float() a complex number
        # below.
        solutions = _real_roots(solve(equation, var))
        if len(solutions) == 0:
            return self.generate_quadratic_equation(max(1, difficulty - 2), variable)

        # For multiple choice, use one solution
        correct_value = float(solutions[0].evalf())

        # Generate choices
        choices, correct_letter = self._generate_math_choices(
            correct_value, difficulty, is_quadratic=True
        )

        # Generate explanation
        if len(solutions) == 2:
            explanation = f"Using the quadratic formula or factoring, we get {variable} = {solutions[0]} or {variable} = {solutions[1]}"
        else:
            explanation = (
                f"Solving the quadratic equation, we get {variable} = {solutions[0]}"
            )

        return {
            "question_text": question,
            "answer_text": f"{variable} = {correct_value}",
            "choices": choices,
            "correct_answer": correct_letter,
            "explanation": explanation,
            "solution": str(solutions[0]) if solutions else "No real solution",
            "difficulty": difficulty,
        }

    def generate_expression_simplification(
        self, difficulty: int = 5, operation: str = "simplify"
    ) -> Dict:
        """
        Generate an expression simplification problem

        Args:
            difficulty: 1-10 difficulty level
            operation: 'simplify', 'expand', 'factor'

        Returns:
            Dict with question_text, answer_text, choices, correct_answer, explanation
        """
        var = symbols("x")

        if difficulty <= 3:
            # Simple: 2x + 3x
            expr = (random.randint(1, 5) * var) + (random.randint(1, 5) * var)
        elif difficulty <= 6:
            # Medium: (x + 2)(x + 3) or 2x^2 + 4x
            if operation == "expand":
                a = random.randint(1, 5)
                b = random.randint(1, 5)
                expr = (var + a) * (var + b)
            elif operation == "factor":
                a = random.randint(1, 5)
                b = random.randint(1, 5)
                expr = var**2 + (a + b) * var + (a * b)
            else:
                expr = random.randint(2, 5) * var**2 + random.randint(2, 10) * var
        else:
            # Complex
            if operation == "expand":
                a = random.randint(1, 5)
                b = random.randint(1, 5)
                c = random.randint(1, 3)
                expr = c * (var + a) * (var + b)
            else:
                expr = (
                    random.randint(2, 8) * var**2
                    + random.randint(5, 15) * var
                    + random.randint(1, 10)
                )

        # Simplify/expand/factor
        if operation == "expand":
            simplified = expand(expr)
            op_name = "Expand"
        elif operation == "factor":
            simplified = factor(expr)
            op_name = "Factor"
        else:
            simplified = simplify(expr)
            op_name = "Simplify"

        question = f"{op_name}: {self._format_expression(expr)}"

        # Generate choices
        correct_value = str(simplified)
        choices, correct_letter = self._generate_expression_choices(
            correct_value, expr, operation
        )

        explanation = f"{op_name}ing the expression: {self._format_expression(expr)} = {correct_value}"

        return {
            "question_text": question,
            "answer_text": correct_value,
            "choices": choices,
            "correct_answer": correct_letter,
            "explanation": explanation,
            "solution": str(simplified),
            "difficulty": difficulty,
        }

    def validate_answer(
        self, question: str, student_answer: str, correct_answer: str
    ) -> Dict:
        """
        Validate a student's math answer using SymPy

        Args:
            question: The math question
            student_answer: Student's answer
            correct_answer: Expected correct answer

        Returns:
            Dict with is_correct, error_message, steps
        """
        try:
            # Try to parse both answers as expressions
            student_expr = self._parse_answer(student_answer)
            correct_expr = self._parse_answer(correct_answer)

            # Check if they're mathematically equivalent
            diff = simplify(student_expr - correct_expr)
            is_correct = diff == 0

            return {
                "is_correct": is_correct,
                "error_message": None if is_correct else "Answer does not match",
                "steps": [],
            }
        except Exception as e:
            return {
                "is_correct": False,
                "error_message": f"Could not parse answer: {str(e)}",
                "steps": [],
            }

    def _generate_math_choices(
        self, correct_value: float, difficulty: int, is_quadratic: bool = False
    ) -> Tuple[List[str], str]:
        """Generate multiple choice options for numeric answers"""
        choices = []

        # Candidate distractors, ordered closest-common-mistake first so
        # that when several collide (e.g. correct_value == 0) we still
        # prefer plausible near misses over far-off values.
        candidates = [
            correct_value + 1,  # off-by-one
            correct_value - 1,
            correct_value + 2,  # off-by-two
            correct_value - 2,
            -correct_value,  # sign error
        ]
        if correct_value != 0:
            candidates.append(correct_value * 2)  # wrong operation: doubled
            candidates.append(correct_value / 2)  # wrong operation: halved

        seen = {round(correct_value, 4)}
        distractors = []
        for candidate in candidates:
            rounded = round(candidate, 4)
            if rounded in seen:
                continue
            seen.add(rounded)
            distractors.append(candidate)
            if len(distractors) == 3:
                break

        # Top up: if collapsing duplicates left us short of 3 distinct
        # distractors, synthesize additional near-miss offsets until we
        # have exactly 3 (guarantees 4 distinct choices overall).
        extra = 3
        while len(distractors) < 3:
            candidate = correct_value + extra if extra % 2 else correct_value - extra
            rounded = round(candidate, 4)
            if rounded not in seen:
                seen.add(rounded)
                distractors.append(candidate)
            extra += 1

        # Format choices
        all_options = [correct_value] + distractors
        random.shuffle(all_options)

        correct_index = all_options.index(correct_value)
        correct_letter = chr(65 + correct_index)  # A, B, C, or D

        for i, option in enumerate(all_options):
            letter = chr(65 + i)
            # Format number nicely
            if option == int(option):
                formatted = str(int(option))
            else:
                formatted = f"{option:.2f}".rstrip("0").rstrip(".")
            choices.append(f"{letter}) {formatted}")

        return choices, correct_letter

    def _generate_expression_choices(
        self, correct_value: str, original_expr, operation: str
    ) -> Tuple[List[str], str]:
        """Generate multiple choice options for expression answers"""
        choices = []

        # Candidate distractors modeling common algebra mistakes, ordered
        # most-plausible first.
        candidates = []
        try:
            if operation == "expand":
                expanded = expand(original_expr)
                # Common mistake: sign error on a cross term when FOILing
                candidates.append(str(expanded + 1))
                candidates.append(str(expanded - 1))
            elif operation == "factor":
                # Common mistake: forgot to factor / left as original expression
                candidates.append(str(original_expr))
                # Common mistake: sign error in a factored term
                candidates.append(str(factor(original_expr) + 1))
            else:
                simplified = simplify(original_expr)
                # Common mistake: sign error
                candidates.append(str(-simplified))
                # Common mistake: off-by-one constant term
                candidates.append(str(simplified + 1))
        except Exception:
            pass

        # Fallback common-mistake perturbations of the answer text itself
        candidates.append(f"{correct_value} + 1")
        candidates.append(f"{correct_value} - 1")
        candidates.append(f"{correct_value} * 2")

        seen = {correct_value}
        distractors = []
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            distractors.append(candidate)
            if len(distractors) == 3:
                break

        # Top up: guarantee exactly 3 distinct distractors even if the
        # candidates above collapsed via dedup (e.g. correct_value + 1
        # coincides with another candidate string).
        extra = 2
        while len(distractors) < 3:
            candidate = f"{correct_value} + {extra}"
            if candidate not in seen:
                seen.add(candidate)
                distractors.append(candidate)
            extra += 1

        all_options = [correct_value] + distractors
        random.shuffle(all_options)

        correct_index = all_options.index(correct_value)
        correct_letter = chr(65 + correct_index)

        for i, option in enumerate(all_options):
            letter = chr(65 + i)
            choices.append(f"{letter}) {option}")

        return choices, correct_letter

    def _parse_answer(self, answer: str):
        """Parse a student's answer into a SymPy expression"""
        # Remove common formatting
        answer = answer.strip()
        answer = re.sub(r"[xX]\s*=\s*", "", answer)  # Remove "x = "
        answer = re.sub(r"^\s*=\s*", "", answer)  # Remove leading "="

        try:
            return sympify(answer)
        except:
            # Try parsing as expression
            return parse_expr(answer)

    def _format_expression(self, expr) -> str:
        """Format a SymPy expression as a readable string"""
        expr_str = str(expr)
        # Replace ** with ^ for readability
        expr_str = expr_str.replace("**", "^")
        # Replace * with nothing for multiplication (2*x -> 2x)
        expr_str = re.sub(r"(\d+)\*([a-z])", r"\1\2", expr_str)
        return expr_str
