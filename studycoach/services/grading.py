"""
Grade a Study Coach card response.

Multiple choice / true-false / numeric short answers use the answer key.
Open short-answer replies use the study_coach_grade AI Service (fast model).
"""

from __future__ import annotations

import logging
from typing import Any

from ai_service.exceptions import USER_FACING_AI_SERVICE_ERROR
from ai_service.runners.study_coach_grade import generate_study_coach_grade

from .static_generator import check_card_answer, normalize_numeric_answer

logger = logging.getLogger(__name__)


class StudyCoachGradeError(Exception):
    """AI grading failed; do not persist the attempt."""

    def __init__(
        self,
        message: str = USER_FACING_AI_SERVICE_ERROR,
        error_code: str = "generation_failed",
    ):
        self.error_code = error_code
        super().__init__(message)


def _needs_ai_grade(card: dict[str, Any], response: str) -> bool:
    if card.get("question_type") != "short_answer":
        return False
    if not str(response or "").strip():
        return False
    if normalize_numeric_answer(str(card.get("answer") or "")) is not None:
        return False
    return True


def grade_study_card(
    card: dict[str, Any],
    response: str,
    *,
    lesson=None,
) -> tuple[bool, dict[str, Any]]:
    """
    Returns (correct, meta).

    meta.graded_by is "skipped" | "key" | "ai".
    Raises StudyCoachGradeError if AI grading cannot complete.
    """
    skipped = not str(response or "").strip()
    if skipped:
        return False, {"graded_by": "skipped"}

    key_correct = check_card_answer(card, response)
    if key_correct or not _needs_ai_grade(card, response):
        return key_correct, {"graded_by": "key"}

    raw = generate_study_coach_grade(
        question_text=str(card.get("prompt") or ""),
        student_answer=response,
        expected_answer=str(card.get("answer") or ""),
        explanation=str(card.get("explanation") or ""),
        lesson_title=(getattr(lesson, "title", None) or "").strip(),
    )
    if not raw.get("success"):
        logger.warning(
            "studycoach AI grade failed card=%s error_code=%s detail=%s",
            card.get("id"),
            raw.get("error_code"),
            (raw.get("error") or "")[:300],
        )
        raise StudyCoachGradeError(error_code=raw.get("error_code") or "generation_failed")

    result = raw.get("result") or {}
    correct = bool(result.get("correct"))
    return correct, {
        "graded_by": "ai",
        "feedback": (result.get("feedback") or "").strip(),
        "provider": raw.get("provider") or "",
        "model_id": raw.get("model_id") or "",
    }
