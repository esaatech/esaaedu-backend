"""
Study Coach short-answer grader — fast model, one card at a time.

Uses the same grading intent as GeminiGrader (meaning over exact wording),
but a tiny structured output so Check stays snappy.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas_study_coach import StudyCardGradeOut

logger = logging.getLogger(__name__)

SERVICE_SLUG = "study_coach_grade"
PROMPT_SLUG_DEFAULT = "default"
GRADE_RUN_TIMEOUT_SECONDS = 20

# Same intent as ai.gemini_grader.GeminiGrader, trimmed for a single quiz card.
DEFAULT_INSTRUCTIONS = """You are an expert educational grader writing feedback directly to students. Your role is to evaluate student answers with:
- Focus on understanding and ideas, not just exact wording
- Credit paraphrases that show the same core idea as the expected answer
- Provide constructive feedback written in second person (use 'you' and 'your') — write as if you are the teacher speaking directly to the student
- Write feedback naturally and conversationally — avoid formal prefixes like "Reasoning:", "Feedback:", or "The answer is..."
- Use phrases like "Your answer..." or "You got..." instead of "The student's answer..."
- Keep feedback to 1–2 short sentences
- Set correct=true if the student demonstrated the core idea (about 60% understanding or better)
- Set correct=false if the idea is missing, contradictory, or too incomplete
- Do not invent a replacement model answer; the expected answer is already provided
- If the student answer is empty or cannot be graded, set correct=false and say why briefly
"""


def generate_study_coach_grade(
    *,
    question_text: str,
    student_answer: str,
    expected_answer: str = "",
    explanation: str = "",
    lesson_title: str = "",
    prompt_config=None,
) -> dict[str, Any]:
    """
    Grade one short-answer card.

    Returns:
      { success, error, error_code, result: {correct, feedback}, provider, model_id, ... }
    """
    if prompt_config is None:
        prompt_config = get_default_prompt_config(SERVICE_SLUG)

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("study_coach_grade: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_grade:resolve_model",
            endpoint="ai_service.runners.study_coach_grade",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("study_coach_grade: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_grade:resolve_model",
            endpoint="ai_service.runners.study_coach_grade",
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
        extra="single_card",
    )

    instructions = (
        getattr(prompt_config, "system_prompt", None) or DEFAULT_INSTRUCTIONS
    ).strip()
    user_prompt = _build_user_prompt(
        lesson_title=lesson_title,
        question_text=question_text,
        expected_answer=expected_answer,
        explanation=explanation,
        student_answer=student_answer,
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_grade:import",
            endpoint="ai_service.runners.study_coach_grade",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=StudyCardGradeOut,
        instructions=instructions,
        retries={"output": 1},
        model_settings=request_model_settings(temperature=settings.temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(
            agent,
            user_prompt,
            timeout_seconds=GRADE_RUN_TIMEOUT_SECONDS,
        )
        grade: StudyCardGradeOut = result.output
        payload = {
            "correct": bool(grade.correct),
            "feedback": (grade.feedback or "").strip(),
        }
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=True,
            latency_ms=latency_ms,
            extra=f"correct={payload['correct']}",
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
        logger.exception("study_coach_grade: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=f"study_coach_grade provider={settings.provider} model={settings.model_id}",
            endpoint="ai_service.runners.study_coach_grade",
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


def _build_user_prompt(
    *,
    lesson_title: str,
    question_text: str,
    expected_answer: str,
    explanation: str,
    student_answer: str,
) -> str:
    parts = []
    title = (lesson_title or "").strip()
    if title:
        parts.append(f"Lesson: {title}")
    parts.append("QUESTION:")
    parts.append((question_text or "").strip() or "(missing question)")
    expected = (expected_answer or "").strip()
    if expected:
        parts.append("EXPECTED ANSWER (credit equivalent meaning, not only exact wording):")
        parts.append(expected)
    guidance = (explanation or "").strip()
    if guidance:
        parts.append("EXPLANATION (guidance for grading):")
        parts.append(guidance)
    parts.append("STUDENT ANSWER:")
    parts.append((student_answer or "").strip() or "(empty)")
    parts.append(
        "Grade based on understanding of the concept, not just exact match. "
        "Return correct and a short feedback message to the student."
    )
    return "\n\n".join(parts)


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
