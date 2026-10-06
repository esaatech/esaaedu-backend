"""
TutorX assignment grading runner — shared by Admin playground and TutorX auto-grade.

One question per model call (same shape as GeminiGrader.grade_question).
Uses AI Service catalog: AIService slug tutorx_assignment_grade + default prompt.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.exceptions import AIServiceError, configuration_error
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas_tutorx_grade import TutorXQuestionGradeOut

logger = logging.getLogger(__name__)

SERVICE_SLUG = "tutorx_assignment_grade"
PROMPT_SLUG_DEFAULT = "default"

# One essay can take a while; Cloud Tasks still owns the full-run deadline.
QUESTION_RUN_TIMEOUT_SECONDS = 300
BATCH_THROTTLE_MIN_QUESTIONS = 4
BATCH_THROTTLE_DELAY_SEC = 0.75

# Same intent as ai.gemini_grader.GeminiGrader fallback system instruction.
DEFAULT_INSTRUCTIONS = """You are an expert educational grader writing feedback directly to students. Your role is to evaluate student answers with:
- Focus on understanding and ideas, not just correctness
- Provide constructive feedback written in second person (use 'you' and 'your') - write as if you are the teacher speaking directly to the student
- Write feedback naturally and conversationally - avoid formal prefixes like "Reasoning:", "Feedback:", or "The answer is..."
- Use phrases like "Your answer..." or "You got..." instead of "The answer is..." or "The student's answer..."
- Award partial credit when appropriate
- Consider context and meaning

IMPORTANT: After providing feedback, you must also generate a correct answer or model answer:
- For questions with rigid correct answers (factual, mathematical, etc.): Provide the standard correct answer
- For open-ended questions (essays, creative responses, etc.): Frame the correct answer around the student's response when appropriate. Use the student's chosen topic/approach but demonstrate the correct format, structure, and completeness expected
- The correct answer should demonstrate what a complete, high-quality response looks like
- It will be shown to the student as a correction/reference, so make it clear and educational

If you cannot grade the question due to unclear question, unclear answer, or insufficient information, award 0 points and provide feedback explaining why grading is not possible."""


def require_default_prompt_config(service_slug: str = SERVICE_SLUG):
    """
    Load the active default prompt for this service.

    Missing setup is a configuration error (Slack + clear message). There is no
    silent fallback to GeminiGrader.
    """
    prompt_config = get_default_prompt_config(service_slug)
    if prompt_config is not None:
        return prompt_config
    raise configuration_error(
        "No default AI prompt for tutorx_assignment_grade. "
        "Run: python manage.py setup_ai_models && "
        "python manage.py setup_tutorx_assignment_grade"
    )


def grade_tutorx_assignment_question(
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
    """
    Grade one TutorX AI question.

    Returns:
      { success, error, error_code, result: {points_earned, feedback, correct_answer, confidence},
        provider, model_id, temperature, instruction_slug, raw_text, latency_ms }
    """
    try:
        if prompt_config is None:
            prompt_config = require_default_prompt_config()
    except AIServiceError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="tutorx_assignment_grade:missing_default_prompt",
            endpoint="ai_service.runners.tutorx_assignment_grade",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=None,
            error_code=ai_exc.error_code,
        )

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("tutorx_assignment_grade: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc,
            context="tutorx_assignment_grade:resolve_model",
            endpoint="ai_service.runners.tutorx_assignment_grade",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("tutorx_assignment_grade: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc,
            context="tutorx_assignment_grade:resolve_model",
            endpoint="ai_service.runners.tutorx_assignment_grade",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )

    log_run_model(
        service=SERVICE_SLUG,
        provider=settings.provider,
        model_id=settings.model_id,
        temperature=settings.temperature,
        extra=f"question_type={question_type or 'unknown'}",
    )

    instructions = (
        getattr(prompt_config, "system_prompt", None) or DEFAULT_INSTRUCTIONS
    ).strip()
    instructions = _add_question_type_instructions(instructions, question_type or "")

    points = float(points_possible or 0)
    user_prompt = _build_user_prompt(
        question_text=question_text,
        question_type=question_type or "",
        student_answer=student_answer,
        points_possible=points,
        explanation=explanation,
        rubric=rubric,
        assignment_context=assignment_context,
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="tutorx_assignment_grade:import",
            endpoint="ai_service.runners.tutorx_assignment_grade",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=TutorXQuestionGradeOut,
        instructions=instructions,
        retries={"output": 1},
        model_settings=request_model_settings(temperature=settings.temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(
            agent,
            user_prompt,
            timeout_seconds=QUESTION_RUN_TIMEOUT_SECONDS,
        )
        grade: TutorXQuestionGradeOut = result.output
        payload = _normalize_grade(grade, points_possible=points)
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=True,
            latency_ms=latency_ms,
            extra=f"points={payload['points_earned']}/{points}",
        )
        return {
            "success": True,
            "error": "",
            "error_code": "",
            "result": payload,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": str(payload)[:4000],
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("tutorx_assignment_grade: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=(
                f"tutorx_assignment_grade provider={settings.provider} "
                f"model={settings.model_id}"
            ),
            endpoint="ai_service.runners.tutorx_assignment_grade",
        )
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=False,
            latency_ms=latency_ms,
            extra=f"error_code={ai_exc.error_code}",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            raw_text=str(exc),
            error_code=ai_exc.error_code,
        )


def grade_tutorx_questions_batch(
    questions: list[dict[str, Any]],
    assignment_context: Optional[dict[str, Any]] = None,
    *,
    prompt_config=None,
) -> dict[str, Any]:
    """
    Grade many TutorX AI questions (one model call each).

    Same return shape as GeminiGrader.grade_questions_batch:
      { grades, total_score, total_possible, provider, model_id, error, error_code }

    Raises nothing; callers map error_code to TutorX permanent/retryable errors.
    Configuration / rate-limit / unavailable failures abort the batch (success=False).
    Soft per-question failures continue with 0 points for that item.
    """
    try:
        if prompt_config is None:
            prompt_config = require_default_prompt_config()
    except AIServiceError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="tutorx_assignment_grade:batch_missing_default_prompt",
            endpoint="ai_service.runners.tutorx_assignment_grade",
        )
        return {
            "success": False,
            "error": ai_exc.log_message,
            "error_code": ai_exc.error_code,
            "grades": [],
            "total_score": 0,
            "total_possible": 0,
            "provider": "",
            "model_id": "",
        }

    grades: list[dict[str, Any]] = []
    total_score = 0.0
    total_possible = 0.0
    provider = ""
    model_id = ""
    should_throttle = len(questions) >= BATCH_THROTTLE_MIN_QUESTIONS

    for idx, question_data in enumerate(questions):
        question_id = question_data.get("question_id")
        if not question_id:
            logger.warning("tutorx_assignment_grade: question missing question_id, skipping")
            continue

        points_possible = float(question_data.get("points_possible") or 0)
        run = grade_tutorx_assignment_question(
            question_text=question_data.get("question_text", ""),
            question_type=question_data.get("question_type", ""),
            student_answer=question_data.get("student_answer", ""),
            points_possible=points_possible,
            explanation=question_data.get("explanation"),
            rubric=question_data.get("rubric"),
            assignment_context=assignment_context,
            prompt_config=prompt_config,
        )
        provider = run.get("provider") or provider
        model_id = run.get("model_id") or model_id

        if not run.get("success"):
            # Never write gateway/model errors into student feedback. Abort so
            # Cloud Tasks can retry (or mark grading_failed on the last attempt).
            error_code = run.get("error_code") or "generation_failed"
            return {
                "success": False,
                "error": run.get("error") or "Grading failed",
                "error_code": error_code,
                "grades": grades,
                "total_score": total_score,
                "total_possible": total_possible,
                "provider": provider,
                "model_id": model_id,
            }
        else:
            payload = run.get("result") or {}
            grade_result = {
                "question_id": str(question_id),
                "points_earned": payload.get("points_earned", 0),
                "points_possible": points_possible,
                "feedback": payload.get("feedback") or "",
                "correct_answer": payload.get("correct_answer") or "",
                "confidence": payload.get("confidence", 0.8),
            }

        grades.append(grade_result)
        total_score += float(grade_result.get("points_earned") or 0)
        total_possible += points_possible

        if should_throttle and idx < len(questions) - 1 and not grade_result.get("error"):
            time.sleep(BATCH_THROTTLE_DELAY_SEC)

    return {
        "success": True,
        "error": "",
        "error_code": "",
        "grades": grades,
        "total_score": total_score,
        "total_possible": total_possible,
        "provider": provider,
        "model_id": model_id,
    }


def _normalize_grade(grade: TutorXQuestionGradeOut, *, points_possible: float) -> dict[str, Any]:
    points_earned = float(grade.points_earned or 0)
    if points_earned < 0:
        points_earned = 0.0
    if points_possible > 0 and points_earned > points_possible:
        points_earned = points_possible

    feedback = grade.feedback or ""
    if feedback.startswith("Reasoning:"):
        feedback = feedback.replace("Reasoning:", "", 1).strip()
    if feedback.startswith("Feedback:"):
        feedback = feedback.replace("Feedback:", "", 1).strip()

    confidence = float(grade.confidence if grade.confidence is not None else 0.8)
    if confidence < 0:
        confidence = 0.0
    if confidence > 1:
        confidence = 1.0

    return {
        "points_earned": points_earned,
        "feedback": feedback,
        "correct_answer": grade.correct_answer or "",
        "confidence": confidence,
    }


def _build_user_prompt(
    *,
    question_text: str,
    question_type: str,
    student_answer: Any,
    points_possible: float,
    explanation: Optional[str],
    rubric: Optional[str],
    assignment_context: Optional[dict[str, Any]],
) -> str:
    parts: list[str] = []

    if assignment_context:
        parts.append("ASSIGNMENT CONTEXT:")
        if assignment_context.get("course_title"):
            parts.append(f"Course: {assignment_context['course_title']}")
        if assignment_context.get("assignment_title"):
            parts.append(f"Assignment: {assignment_context['assignment_title']}")
        if assignment_context.get("assignment_description"):
            parts.append(
                f"Assignment description: {assignment_context['assignment_description']}"
            )
        if assignment_context.get("lesson_title"):
            parts.append(f"Lesson: {assignment_context['lesson_title']}")
        if assignment_context.get("lesson_description"):
            parts.append(f"Lesson description: {assignment_context['lesson_description']}")
        if assignment_context.get("passage_text"):
            parts.append(f"Passage: {assignment_context['passage_text']}")
        if assignment_context.get("lesson_content"):
            parts.append(f"Lesson Content: {assignment_context['lesson_content']}")
        parts.append("")

    parts.append("QUESTION:")
    parts.append((question_text or "").strip() or "(missing question)")
    parts.append("")

    if question_type == "essay" and rubric:
        parts.append("RUBRIC:")
        parts.append(str(rubric).strip())
        parts.append("")

    if explanation:
        parts.append("EXPLANATION (guidance for grading):")
        parts.append(str(explanation).strip())
        parts.append("")

    parts.append("STUDENT ANSWER:")
    if isinstance(student_answer, dict):
        parts.append(json.dumps(student_answer, indent=2))
    else:
        parts.append(str(student_answer).strip() or "(empty)")
    parts.append("")

    parts.append("GRADING INSTRUCTIONS:")
    parts.append(f"- Points possible: {points_possible}")
    parts.append("- Grade based on understanding of the concept, not just exact match")
    parts.append(
        "- Provide constructive feedback written in second person (use 'you' and 'your'), "
        "as if you are the teacher directly addressing the student"
    )
    parts.append(
        "- Write feedback naturally and conversationally - do not use prefixes like "
        "'Reasoning:' or 'Feedback:'"
    )
    parts.append("- Generate a correct answer or model answer:")
    parts.append(
        "  * For questions with rigid correct answers: provide the standard correct answer"
    )
    parts.append(
        "  * For open-ended questions: frame around the student's topic when appropriate, "
        "but demonstrate proper format and completeness"
    )
    parts.append(
        "- If question/answer is unclear or information is insufficient, award 0 points "
        "and explain why"
    )
    if question_type == "fill_blank":
        parts.append(
            "- Consider partial credit for close answers that show understanding"
        )
    parts.append("")
    parts.append(
        "Please grade this answer and provide points_earned, feedback, and correct_answer."
    )
    return "\n".join(parts)


def _add_question_type_instructions(base_instruction: str, question_type: str) -> str:
    if question_type == "essay":
        return (
            base_instruction
            + "\nFor essay questions:\n"
            + "- Evaluate the student's understanding of the concept\n"
            + "- Check for complete sentences and proper grammar\n"
            + "- Award points based on how well they demonstrate understanding\n"
            + "- Provide specific feedback on what they did well and what needs improvement\n"
            + "- When generating correct_answer, frame it around the student's topic/approach "
            "when appropriate, but demonstrate proper format and completeness\n"
        )
    if question_type == "fill_blank":
        return (
            base_instruction
            + "\nFor fill-in-the-blank questions:\n"
            + "- Award partial credit for close answers that show understanding\n"
            + "- Consider variations in wording that convey the same idea\n"
            + "- Focus on whether the student understands the concept\n"
        )
    if question_type == "code":
        return (
            base_instruction
            + "\nFor programming / code questions:\n"
            + "- Evaluate correctness of logic and whether the code would solve the stated problem\n"
            + "- Mention syntax or API issues briefly when relevant\n"
            + "- Do not claim you executed the code unless output was provided; infer from the source\n"
            + "- Award partial credit for partially correct solutions\n"
            + "- In correct_answer, give a concise model solution or the key fix needed\n"
        )
    if question_type in ("multiple_choice", "true_false", "ordering", "matching"):
        return (
            base_instruction
            + "\nFor this structured question type:\n"
            + "- Be precise; treat points_possible as the maximum score\n"
            + "- If the prompt includes the official correct answer or key, align your score with it\n"
        )
    return base_instruction


def _fail(
    error: str,
    *,
    prompt_config=None,
    settings=None,
    raw_text: Optional[str] = None,
    error_code: str = "",
) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "error_code": error_code,
        "result": None,
        "provider": getattr(settings, "provider", "") if settings else "",
        "model_id": getattr(settings, "model_id", "") if settings else "",
        "temperature": getattr(settings, "temperature", None) if settings else None,
        "instruction_slug": getattr(prompt_config, "slug", "") or "",
        "raw_text": raw_text,
    }
