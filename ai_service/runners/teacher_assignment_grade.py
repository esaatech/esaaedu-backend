"""
Teacher assignment AI grading runner — AssignmentAIGradingView / ai_grading_helper.
"""

from __future__ import annotations

from typing import Any, Optional

from ai_service.runners.question_grade_base import (
    DEFAULT_GRADING_INSTRUCTIONS,
    grade_assignment_question,
    grade_questions_batch,
)

SERVICE_SLUG = "teacher_assignment_grade"
PROMPT_SLUG_DEFAULT = "default"
SETUP_COMMAND = "setup_teacher_assignment_grade"
DEFAULT_INSTRUCTIONS = DEFAULT_GRADING_INSTRUCTIONS


def grade_teacher_assignment_question(
    *,
    question_text: str,
    question_type: str,
    student_answer: Any,
    points_possible: int | float = 1,
    explanation: Optional[str] = None,
    rubric: Optional[str] = None,
    assignment_context: Optional[dict[str, Any]] = None,
    prompt_config=None,
) -> dict[str, Any]:
    return grade_assignment_question(
        service_slug=SERVICE_SLUG,
        setup_command=SETUP_COMMAND,
        question_text=question_text,
        question_type=question_type,
        student_answer=student_answer,
        points_possible=points_possible,
        explanation=explanation,
        rubric=rubric,
        assignment_context=assignment_context,
        prompt_config=prompt_config,
        default_instructions=DEFAULT_INSTRUCTIONS,
    )


def grade_teacher_assignment_questions_batch(
    questions: list[dict[str, Any]],
    assignment_context: Optional[dict[str, Any]] = None,
    *,
    prompt_config=None,
) -> dict[str, Any]:
    return grade_questions_batch(
        questions,
        assignment_context,
        service_slug=SERVICE_SLUG,
        setup_command=SETUP_COMMAND,
        prompt_config=prompt_config,
        default_instructions=DEFAULT_INSTRUCTIONS,
    )
