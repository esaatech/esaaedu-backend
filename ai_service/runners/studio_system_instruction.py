"""Rewrite a Lesson Studio system instruction. Same runner for Admin playground."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas_studio import StudioSystemInstructionOut
from ai_service.studio_prompts import (
    SCRIPT_DRAFTER_SLUG,
    STUDIO_TASK_SLUGS,
    SYSTEM_INSTRUCTION_SLUG,
    VISUAL_GENERATOR_SLUG,
)

logger = logging.getLogger(__name__)

SERVICE_SLUG = SYSTEM_INSTRUCTION_SLUG
PROMPT_SLUG_DEFAULT = "default"
RUN_TIMEOUT_SECONDS = 40


def _default_instructions() -> str:
    from ai_service.studio_prompts import SYSTEM_INSTRUCTION_PROMPT

    return SYSTEM_INSTRUCTION_PROMPT


def rewrite_studio_system_instruction(
    *,
    target_service: str = SCRIPT_DRAFTER_SLUG,
    current_prompt: str = "",
    change_request: str = "",
    prompt_config=None,
) -> dict[str, Any]:
    slug = (target_service or SCRIPT_DRAFTER_SLUG).strip()
    if slug not in STUDIO_TASK_SLUGS:
        return _fail(f"Target must be {SCRIPT_DRAFTER_SLUG} or {VISUAL_GENERATOR_SLUG}.")

    current = (current_prompt or "").strip()
    if not current:
        existing = get_default_prompt_config(slug)
        current = (getattr(existing, "system_prompt", None) or "").strip()
    if not current:
        return _fail(
            f"No current instruction for {slug}. Run setup_studio_ai or paste the prompt."
        )
    request_text = (change_request or "").strip()
    if not request_text:
        return _fail("Write the change you want in the system instruction.")

    if prompt_config is None:
        prompt_config = get_default_prompt_config(SERVICE_SLUG)

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="studio_system_instruction:resolve_model",
            endpoint="ai_service.runners.studio_system_instruction",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("studio_system_instruction: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc,
            context="studio_system_instruction:resolve_model",
            endpoint="ai_service.runners.studio_system_instruction",
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
        extra=f"target={slug}",
    )

    instructions = (
        getattr(prompt_config, "system_prompt", None) or _default_instructions()
    ).strip()
    user_prompt = (
        f"Target service: {slug}\n\n"
        f"Current system instruction:\n{current}\n\n"
        f"Requested change:\n{request_text}\n\n"
        "Return the full replacement system_prompt and a one-sentence summary."
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="studio_system_instruction:import",
            endpoint="ai_service.runners.studio_system_instruction",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=StudioSystemInstructionOut,
        instructions=instructions,
        retries={"output": 1},
        model_settings=request_model_settings(temperature=settings.temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(
            agent,
            user_prompt,
            timeout_seconds=RUN_TIMEOUT_SECONDS,
        )
        out: StudioSystemInstructionOut = result.output
        payload = {
            "target_service": slug,
            "system_prompt": (out.system_prompt or "").strip(),
            "summary": (out.summary or "").strip(),
        }
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=True,
            latency_ms=latency_ms,
            extra=f"target={slug}",
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
            "raw_text": payload["summary"][:4000],
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("studio_system_instruction: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=f"studio_system_instruction provider={settings.provider} model={settings.model_id}",
            endpoint="ai_service.runners.studio_system_instruction",
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
