"""
Practice utility functions
"""
import random
from typing import List, Tuple


def generate_choices_from_answer(answer_text: str) -> Tuple[List[str], str]:
    """Generate 4 multiple choice options from an answer

    Returns:
        tuple: (choices list, correct_answer_letter)
    """
    # Create distractors
    distractors = [
        "A related but incorrect option",
        "Another plausible but wrong answer",
        "An incorrect alternative",
    ]

    # Combine correct answer with distractors and shuffle
    all_options = [answer_text] + distractors
    random.shuffle(all_options)

    # Format as A, B, C, D
    letters = ["A", "B", "C", "D"]
    choices = [f"{letter}) {option}" for letter, option in zip(letters, all_options)]

    # Find which letter has the correct answer
    correct_letter = None
    for i, option in enumerate(all_options):
        if option == answer_text:
            correct_letter = letters[i]
            break

    return choices, correct_letter or "A"
