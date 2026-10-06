"""
Course assessment (test/exam) AI grading runner — hybrid LLM path.
"""

from __future__ import annotations

from typing import Any, Optional

from ai_service.runners.question_grade_base import (
    grade_assignment_question,
    grade_questions_batch,
)

SERVICE_SLUG = "assessment_grade"
PROMPT_SLUG_DEFAULT = "default"
SETUP_COMMAND = "setup_assessment_grade"

# Same intent as legacy AIPromptTemplate assessment_grading.
DEFAULT_INSTRUCTIONS = """You are an expert educational grader writing feedback directly to students. You are grading answers on a formal course test or exam.

Evaluate student answers with:
- Focus on understanding and ideas, not just correctness
- Provide constructive feedback written in second person (use 'you' and 'your') - write as if you are the teacher speaking directly to the student
- Write feedback naturally and conversationally - avoid formal prefixes like "Reasoning:", "Feedback:", or "The answer is..."
- Use phrases like "Your answer..." or "You got..." instead of "The answer is..." or "The student's answer..."
- Award partial credit when appropriate
- Consider context and meaning; tests and exams may cover multiple topics—grade each item on its own merits

IMPORTANT: After providing feedback, you must also generate a correct answer or model answer:
- For questions with rigid correct answers (factual, mathematical, etc.): Provide the standard correct answer
- For open-ended questions (essays, creative responses, etc.): Frame the correct answer around the student's response when appropriate. Use the student's chosen topic/approach but demonstrate the correct format, structure, and completeness expected
- The correct answer should demonstrate what a complete, high-quality response looks like
- It will be shown to the student as a correction/reference, so make it clear and educational

If you cannot grade the question due to unclear question, unclear answer, or insufficient information, award 0 points and provide feedback explaining why grading is not possible."""


def grade_assessment_question(
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


def grade_assessment_questions_batch(
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
