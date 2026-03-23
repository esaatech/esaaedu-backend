"""
Shared teacher AI grading entry point.

Keeps assignment and course-assessment (test/exam) flows on one code path so
prompt/template or grader changes stay in sync.

Uses AIPromptTemplate names:
- assignment_grading  — lesson assignments
- assessment_grading — course-level tests and exams
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
    Run Gemini batch grading for teacher flows. Does not persist to the database.

    Args:
        questions_data: Same shape as AssignmentAIGradingView body "questions".
        context: Optional context dict (lesson/assignment or course/assessment metadata).
        prompt_template_name: AIPromptTemplate.name, e.g. assignment_grading or assessment_grading.

    Returns:
        Dict with keys grades, total_score, total_possible (from GeminiGrader).
    """
    if prompt_template_name not in _ALLOWED_TEMPLATES:
        logger.warning(
            "Unknown prompt_template_name=%r; using %s",
            prompt_template_name,
            ASSIGNMENT_GRADING_TEMPLATE,
        )
        prompt_template_name = ASSIGNMENT_GRADING_TEMPLATE

    from ai.gemini_grader import GeminiGrader

    grader = GeminiGrader(prompt_template_name=prompt_template_name)
    return grader.grade_questions_batch(
        questions=questions_data,
        assignment_context=context,
    )
