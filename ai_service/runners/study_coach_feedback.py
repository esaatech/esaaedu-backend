"""
Study Coach session feedback — after Grade, one coaching turn.

Picks the next mix / study task from results. Does not grade individual cards.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas_study_coach import StudyCoachFeedbackOut

logger = logging.getLogger(__name__)

SERVICE_SLUG = "study_coach_feedback"
PROMPT_SLUG_DEFAULT = "default"
FEEDBACK_RUN_TIMEOUT_SECONDS = 40

DEFAULT_INSTRUCTIONS = """You are Study Coach, a patient practice tutor speaking directly to the student.

You see one finished practice quiz: each card's difficulty, whether they got it right, and which lesson page/video/PDF UUIDs it is tagged to. You also see the lesson content catalog (those UUIDs) and their previous coach memory.

Your job:
- Write a short headline and a warm 1–3 sentence message (second person: you/your).
- Decide the NEXT practice mix. The first quiz of a lesson was already a 5 easy / 3 intermediate / 2 hard split (scaled to card count). After that, YOU choose.
- Diagnose weak TOPICS from missed cards' source ids, not only easy/intermediate/hard.
- Example: they missed subtraction pages but did well on addition → action=practice, next_mix mostly easy, source_ids = those subtraction page UUIDs.
- If previous memory already drilled that topic (same source ids / study action) and they still missed it → action=study_then_retake, study_source_ids = those catalog UUIDs, tell them to go read the pages before another quiz.
- If they mastered the hard cards → action=mastered.
- NEVER invent UUIDs. Only copy ids from the catalog or card sources we sent.
- Do not tell them to generate a new live quiz. The app will draw the next mix from the practice bank.
- Keep next_mix counts as non-negative integers that sum to about the same size as this quiz (or slightly fewer). order is easy_first, hard_first, or shuffled.
"""


def generate_study_coach_feedback(
    *,
    lesson_title: str = "",
    catalog_text: str = "",
    cards_text: str = "",
    band_scores_text: str = "",
    memory_text: str = "",
    card_count: int = 6,
    prompt_config=None,
) -> dict[str, Any]:
    if prompt_config is None:
        prompt_config = get_default_prompt_config(SERVICE_SLUG)

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("study_coach_feedback: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_feedback:resolve_model",
            endpoint="ai_service.runners.study_coach_feedback",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("study_coach_feedback: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_feedback:resolve_model",
            endpoint="ai_service.runners.study_coach_feedback",
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
        extra="session_feedback",
    )

    instructions = (
        getattr(prompt_config, "system_prompt", None) or DEFAULT_INSTRUCTIONS
    ).strip()
    user_prompt = _build_user_prompt(
        lesson_title=lesson_title,
        catalog_text=catalog_text,
        cards_text=cards_text,
        band_scores_text=band_scores_text,
        memory_text=memory_text,
        card_count=card_count,
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_feedback:import",
            endpoint="ai_service.runners.study_coach_feedback",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=StudyCoachFeedbackOut,
        instructions=instructions,
        retries={"output": 1},
        model_settings=request_model_settings(temperature=settings.temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(
            agent,
            user_prompt,
            timeout_seconds=FEEDBACK_RUN_TIMEOUT_SECONDS,
        )
        out: StudyCoachFeedbackOut = result.output
        mix = None
        if out.next_mix is not None:
            mix = out.next_mix.model_dump()
        payload = {
            "headline": (out.headline or "").strip(),
            "message": (out.message or "").strip(),
            "action": out.action,
            "next_mix": mix,
            "study_source_ids": list(out.study_source_ids or []),
        }
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=True,
            latency_ms=latency_ms,
            extra=f"action={payload['action']}",
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
        logger.exception("study_coach_feedback: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=f"study_coach_feedback provider={settings.provider} model={settings.model_id}",
            endpoint="ai_service.runners.study_coach_feedback",
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
    catalog_text: str,
    cards_text: str,
    band_scores_text: str,
    memory_text: str,
    card_count: int,
) -> str:
    parts = [
        f"Lesson: {(lesson_title or '').strip() or 'Untitled lesson'}",
        f"This quiz had about {max(1, int(card_count or 6))} cards. Aim the next mix at a similar size.",
    ]
    if memory_text.strip():
        parts.append("Previous coach memory for this lesson:")
        parts.append(memory_text.strip())
    else:
        parts.append("No previous coach memory — this was their first Auto mix (5/3/2 style).")
    if band_scores_text.strip():
        parts.append("Scores by difficulty:")
        parts.append(band_scores_text.strip())
    if catalog_text.strip():
        parts.append(
            "Lesson content catalog. You may only copy these ids into next_mix.source_ids "
            "or study_source_ids:"
        )
        parts.append(catalog_text.strip()[:8000])
    parts.append("Quiz cards (correct true/false, difficulty, source ids):")
    parts.append((cards_text or "").strip() or "(none)")
    parts.append(
        "Return headline, message, action, next_mix, and study_source_ids when they should reread."
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
