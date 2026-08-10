"""
Phase 1 static quiz-card generator.

Returns the same card shape real AI will use later.
difficulty_mode: easy | hard | auto
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

DifficultyMode = Literal["easy", "hard", "auto"]


def _id() -> str:
    return str(uuid.uuid4())


def _topic_label(lesson_title: str) -> str:
    title = (lesson_title or "").strip()
    return title if title else "this lesson"


def generate_static_cards(
    *,
    lesson_title: str,
    difficulty_mode: DifficultyMode,
    count: int = 6,
) -> list[dict[str, Any]]:
    topic = _topic_label(lesson_title)

    easy_pool = [
        {
            "question_type": "multiple_choice",
            "prompt": f'What is the main focus of "{topic}"?',
            "options": [
                f"Ideas and skills from {topic}",
                "Unrelated history facts",
                "Random vocabulary only",
                "None of these",
            ],
            "answer": f"Ideas and skills from {topic}",
            "hints": [
                f'Think about what a lesson titled "{topic}" would typically teach.',
                "Eliminate options that are clearly off-topic.",
                f"The best answer connects directly to {topic}.",
            ],
            "explanation": f'Study Coach practices ideas from "{topic}".',
            "difficulty": "easy",
        },
        {
            "question_type": "true_false",
            "prompt": f'True or False: Reviewing "{topic}" can help you remember key ideas.',
            "options": ["True", "False"],
            "answer": "True",
            "hints": [
                "How does reviewing usually affect memory?",
                "Think about why teachers assign practice.",
            ],
            "explanation": "Practice and review strengthen recall.",
            "difficulty": "easy",
        },
        {
            "question_type": "multiple_choice",
            "prompt": f'Which is a good study habit for "{topic}"?',
            "options": [
                "Try a question, use a hint if stuck, then check your answer",
                "Only memorize without understanding",
                "Skip harder questions forever",
                "Never flip the card to review",
            ],
            "answer": "Try a question, use a hint if stuck, then check your answer",
            "hints": [
                "Hints guide you without giving everything away.",
                "Active practice beats passive reading alone.",
            ],
            "explanation": "Active recall with hints builds understanding.",
            "difficulty": "easy",
        },
        {
            "question_type": "short_answer",
            "prompt": f'In one or two words, what are you practicing when you study "{topic}"?',
            "answer": topic.split()[0] if topic.split() else "lesson",
            "hints": [
                f'Look at the lesson title: "{topic}".',
                "Name the subject or theme, not a full sentence.",
            ],
            "explanation": f"The theme centers on {topic}.",
            "difficulty": "easy",
        },
        {
            "question_type": "multiple_choice",
            "prompt": f'If you do not know an answer about "{topic}", what should you try first?',
            "options": [
                "Use a hint",
                "Give up immediately",
                "Guess randomly without thinking",
                "Close the app",
            ],
            "answer": "Use a hint",
            "hints": [
                "Study Coach includes Socratic hints on each card.",
                "Hints nudge you toward the idea step by step.",
            ],
            "explanation": "Hints are designed to coach, not spoil.",
            "difficulty": "easy",
        },
        {
            "question_type": "true_false",
            "prompt": f'True or False: Flipping the card shows the official answer for "{topic}".',
            "options": ["True", "False"],
            "answer": "True",
            "hints": [
                "What does flip mean on a study card?",
                "The back of the card holds the answer.",
            ],
            "explanation": "Flip reveals the answer when you are ready to check.",
            "difficulty": "easy",
        },
    ]

    hard_pool = [
        {
            "question_type": "short_answer",
            "prompt": (
                f'Explain in one short sentence why practicing questions about '
                f'"{topic}" is better than only re-reading notes.'
            ),
            "answer": "practice retrieves knowledge",
            "hints": [
                "Compare passive reading with active recall.",
                "What happens in your brain when you try to answer first?",
                "Active retrieval strengthens memory more than re-reading alone.",
            ],
            "explanation": "Active retrieval (answering) strengthens memory more than re-reading.",
            "difficulty": "hard",
        },
        {
            "question_type": "multiple_choice",
            "prompt": f'You missed a hard question about "{topic}". Best next step?',
            "options": [
                "Read the hints, rethink, then check the flip answer and try a similar idea next",
                "Ignore the miss and never revisit it",
                "Only memorize the exact wording forever",
                "Stop studying that lesson entirely",
            ],
            "answer": (
                "Read the hints, rethink, then check the flip answer and try a similar idea next"
            ),
            "hints": [
                "Mistakes are useful signals.",
                "Hints + checking the answer help you correct the model in your head.",
            ],
            "explanation": "Learn from the miss, then practice again.",
            "difficulty": "hard",
        },
        {
            "question_type": "short_answer",
            "prompt": (
                f'Name one thing a Socratic hint should do when you are stuck on "{topic}" '
                f"(not just dump the final answer)."
            ),
            "answer": "guide",
            "hints": [
                "Think of how a patient tutor asks questions.",
                "Hints should nudge reasoning, not spoil everything at once.",
            ],
            "explanation": "Socratic hints guide thinking without fully spoiling the answer.",
            "difficulty": "hard",
        },
        {
            "question_type": "true_false",
            "prompt": (
                f'True or False: In Auto mode, Study Coach can make later cards about '
                f'"{topic}" harder after you answer several correctly.'
            ),
            "options": ["True", "False"],
            "answer": "True",
            "hints": [
                "What does auto usually mean for difficulty?",
                "Progress should adapt to how you are doing.",
            ],
            "explanation": "Auto difficulty adapts based on your performance.",
            "difficulty": "hard",
        },
        {
            "question_type": "multiple_choice",
            "prompt": f'Which prompt is hardest for studying "{topic}"?',
            "options": [
                "Write a short explanation in your own words",
                "Pick True or False on a simple fact",
                "Choose from four obvious choices",
                "Skip thinking and flip immediately every time",
            ],
            "answer": "Write a short explanation in your own words",
            "hints": [
                "Which option forces you to generate the answer yourself?",
                "Generation is usually harder than recognition.",
            ],
            "explanation": "Short-answer / explain-in-your-own-words is typically harder.",
            "difficulty": "hard",
        },
        {
            "question_type": "short_answer",
            "prompt": "What is the lesson title you are practicing right now?",
            "answer": topic,
            "hints": [
                "It appears in your session setup.",
                f"It starts like: {topic[:24]}",
            ],
            "explanation": f'You selected the lesson "{topic}".',
            "difficulty": "hard",
        },
    ]

    if difficulty_mode == "easy":
        pool = easy_pool
    elif difficulty_mode == "hard":
        pool = hard_pool
    else:
        half = max(1, count // 2)
        pool = easy_pool[:half] + hard_pool[: max(1, count - half)]

    cards: list[dict[str, Any]] = []
    for i in range(count):
        template = pool[i % len(pool)]
        cards.append({"id": _id(), **template})
    return cards


def default_progress() -> dict[str, Any]:
    return {
        "current_index": 0,
        "correct_count": 0,
        "incorrect_count": 0,
        "streak": 0,
        "answers": {},
    }


def normalize_answer(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def check_card_answer(card: dict[str, Any], response: str) -> bool:
    expected = normalize_answer(str(card.get("answer", "")))
    got = normalize_answer(response)
    if not expected:
        return False
    qtype = card.get("question_type")
    if qtype in ("multiple_choice", "true_false"):
        return got == expected
    if got == expected:
        return True
    if expected in got or got in expected:
        return True
    return False
