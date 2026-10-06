"""
Shared teacher AI grading entry point.

Keeps assignment grading on one code path. Uses AI Service
`teacher_assignment_grade` (model switchable in Admin).

Legacy constants ASSIGNMENT_GRADING_TEMPLATE / ASSESSMENT_GRADING_TEMPLATE are
kept for callers; assessment hybrid grading uses assessment_grade separately.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ASSIGNMENT_GRADING_TEMPLATE = "assignment_grading"
ASSESSMENT_GRADING_TEMPLATE = "assessment_grading"

_ALLOWED_TEMPLATES = frozenset({ASSIGNMENT_GRADING_TEMPLATE, ASSESSMENT_GRADING_TEMPLATE})


def run_teacher_ai_grading_batch(
    questions_data: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]],
    prompt_template_name: str,
) -> Dict[str, Any]:
    """
    Run AI batch grading for teacher assignment flows. Does not persist.

    Args:
        questions_data: Same shape as AssignmentAIGradingView body "questions".
        context: Optional context dict (lesson/assignment metadata).
        prompt_template_name: Historical AIPromptTemplate name. Assignment
            grading uses teacher_assignment_grade. Assessment template name
            routes to assessment_grade for any legacy callers.

    Returns:
        Dict with keys grades, total_score, total_possible.
    """
    if prompt_template_name not in _ALLOWED_TEMPLATES:
        logger.warning(
            "Unknown prompt_template_name=%r; using %s",
            prompt_template_name,
            ASSIGNMENT_GRADING_TEMPLATE,
        )
        prompt_template_name = ASSIGNMENT_GRADING_TEMPLATE

    if prompt_template_name == ASSESSMENT_GRADING_TEMPLATE:
        from ai_service.runners.assessment_grade import grade_assessment_questions_batch

        result = grade_assessment_questions_batch(
            questions_data,
            context,
        )
    else:
        from ai_service.runners.teacher_assignment_grade import (
            grade_teacher_assignment_questions_batch,
        )

        result = grade_teacher_assignment_questions_batch(
            questions_data,
            context,
        )

    if not result.get("success"):
        message = result.get("error") or "AI grading failed"
        error_code = result.get("error_code") or "generation_failed"
        logger.error(
            "Teacher AI grading failed template=%s error_code=%s message=%s",
            prompt_template_name,
            error_code,
            message,
        )
        raise RuntimeError(f"{error_code}: {message}")

    logger.info(
        "Teacher AI grading ok template=%s provider=%s model=%s grades=%s",
        prompt_template_name,
        result.get("provider"),
        result.get("model_id"),
        len(result.get("grades") or []),
    )
    return {
        "grades": result.get("grades") or [],
        "total_score": result.get("total_score") or 0,
        "total_possible": result.get("total_possible") or 0,
    }
