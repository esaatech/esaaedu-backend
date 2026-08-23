"""
Phase 1 static quiz-card generator.

Returns the same card shape real AI will use later.
difficulty_mode: easy | hard | auto
"""

from __future__ import annotations

import json
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
        "graded": False,
    }


def normalize_answer(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def normalize_numeric_answer(value: str) -> str | None:
    """
    Normalize number-like answers so commas / spaces don't fail grading.

    "4,287", "4287", "4 287" → "4287"
    Returns None if the value is not a simple number.
    """
    text = (value or "").strip().lower().replace("−", "-").replace("–", "-")
    # Drop thousand separators and spaces; keep a single decimal point / leading minus.
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
    if cleaned.count(".") > 1:
        return None
    if cleaned.count("-") > 1 or ("-" in cleaned and not cleaned.startswith("-")):
        return None
    if cleaned in ("", "-", ".", "-."):
        return None
    # Must contain at least one digit
    if not any(ch.isdigit() for ch in cleaned):
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if number.is_integer():
        return str(int(number))
    return str(number)


def check_card_answer(card: dict[str, Any], response: str) -> bool:
    expected_raw = str(card.get("answer", ""))
    got_raw = response
    expected = normalize_answer(expected_raw)
    got = normalize_answer(got_raw)
    if not expected:
        return False

    # Numeric answers: ignore commas / spacing ("6,555" == "6555")
    expected_num = normalize_numeric_answer(expected_raw)
    got_num = normalize_numeric_answer(got_raw)
    if expected_num is not None and got_num is not None:
        return expected_num == got_num

    qtype = card.get("question_type")
    if qtype in ("multiple_choice", "true_false"):
        return got == expected
    if got == expected:
        return True
    if expected in got or got in expected:
        return True
    return False


def _collapse_ws(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _collect_blocknote_text(node: Any, texts: list[str], urls: list[str]) -> None:
    if isinstance(node, dict):
        text = node.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)
        if node.get("type") == "image":
            props = node.get("props") if isinstance(node.get("props"), dict) else {}
            url = str(props.get("url") or "").strip()
            if url:
                urls.append(url)
            caption = props.get("caption")
            if isinstance(caption, str) and caption.strip():
                texts.append(caption)
        for key, value in node.items():
            if key in ("text", "props"):
                continue
            _collect_blocknote_text(value, texts, urls)
    elif isinstance(node, list):
        for item in node:
            _collect_blocknote_text(item, texts, urls)


def prompt_plain_text(prompt: str) -> str:
    """Plain, normalized question text (BlockNote JSON → visible text)."""
    raw = str(prompt or "").strip()
    if not raw:
        return ""
    if raw.startswith("[") or raw.startswith("{"):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if parsed is not None:
            texts: list[str] = []
            urls: list[str] = []
            _collect_blocknote_text(parsed, texts, urls)
            if texts:
                raw = " ".join(texts)
            elif urls:
                raw = " ".join(urls)
    return _collapse_ws(raw)


def _column_math_display(card: dict[str, Any]) -> dict[str, Any] | None:
    display = card.get("display")
    if isinstance(display, dict) and display.get("type") == "column_math":
        return display
    raw = card.get("display_json")
    if isinstance(raw, dict) and raw.get("type") == "column_math":
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(parsed, dict) and parsed.get("type") == "column_math":
            return parsed
    return None


def card_avoid_label(card: dict[str, Any]) -> str:
    """
    Fingerprint for dedupe / avoid lists.

    Uses visible prompt text (not BlockNote JSON), lowercased with collapsed
    whitespace. Column-math cards often share the same prompt
    ("Add these numbers."), so we include the operands/operator.
    """
    prompt = prompt_plain_text(str(card.get("prompt") or ""))
    math = _column_math_display(card)
    if math:
        operator = _collapse_ws(str(math.get("operator") or ""))
        operands = math.get("operands") or []
        if isinstance(operands, list) and operands:
            joined = " ".join(
                prompt_plain_text(str(o)) for o in operands if str(o).strip()
            )
            return f"{prompt} | {operator} {joined}".strip(" |")
    display_json = str(card.get("display_json") or "").strip()
    if display_json and not math:
        return f"{prompt} | {_collapse_ws(display_json[:160])}".strip(" |")
    return prompt


def dedupe_cards(
    cards: list[dict[str, Any]],
    *,
    existing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Drop cards that collide with existing fingerprints (or earlier in the batch)."""
    seen: set[str] = set()
    for card in existing or []:
        label = card_avoid_label(card).lower()
        if label:
            seen.add(label)

    unique: list[dict[str, Any]] = []
    for card in cards:
        label = card_avoid_label(card).lower()
        if label and label in seen:
            continue
        if label:
            seen.add(label)
        unique.append(card)
    return unique
