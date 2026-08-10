"""
Gateway probe runner — used by Admin playground (Phase 2).

Product feature runners (Phase 3+) should follow the same return shape:
  { success, error?, ...payload, provider, model_id, temperature, instruction_slug }
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas import GatewayProbeResult

logger = logging.getLogger(__name__)

SERVICE_SLUG = "gateway_probe"


def run_gateway_probe(
    user_message: str,
    *,
    prompt_config=None,
) -> dict[str, Any]:
    """
    Resolve model from prompt_config (or env defaults) and run a tiny structured probe.

    Returns a JSON-serializable dict for Admin AJAX + persistence.
    """
    message = (user_message or "").strip() or "Reply briefly confirming the gateway works."

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("gateway_probe: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc,
            context="gateway_probe:resolve_model",
            endpoint="ai_service.runners.gateway_probe",
        )
        return {
            "success": False,
            "error": ai_exc.log_message,
            "error_code": ai_exc.error_code,
            "result": None,
            "provider": "",
            "model_id": "",
            "temperature": None,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": None,
        }
    except Exception as exc:
        logger.exception("gateway_probe: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc,
            context="gateway_probe:resolve_model",
            endpoint="ai_service.runners.gateway_probe",
        )
        return {
            "success": False,
            "error": ai_exc.log_message,
            "error_code": ai_exc.error_code,
            "result": None,
            "provider": "",
            "model_id": "",
            "temperature": None,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": None,
        }

    log_run_model(
        service=SERVICE_SLUG,
        provider=settings.provider,
        model_id=settings.model_id,
        temperature=settings.temperature,
    )

    instructions = (
        getattr(prompt_config, "system_prompt", None)
        or "You are a connectivity probe. Return structured JSON matching the schema."
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="gateway_probe:import",
            endpoint="ai_service.runners.gateway_probe",
        )
        return {
            "success": False,
            "error": ai_exc.log_message,
            "error_code": ai_exc.error_code,
            "result": None,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": None,
        }

    agent = Agent(
        model,
        output_type=GatewayProbeResult,
        instructions=instructions,
        retries={"output": 2},
        model_settings=request_model_settings(temperature=settings.temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(agent, message)
        payload = result.output.model_dump()
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=True,
            latency_ms=latency_ms,
        )
        return {
            "success": True,
            "error": "",
            "result": payload,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": str(payload),
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("gateway_probe: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=f"gateway_probe provider={settings.provider} model={settings.model_id}",
            endpoint="ai_service.runners.gateway_probe",
        )
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=False,
            latency_ms=latency_ms,
            extra=f"error_code={ai_exc.error_code}",
        )
        return {
            "success": False,
            "error": ai_exc.log_message,
            "error_code": ai_exc.error_code,
            "result": None,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": str(exc),
            "latency_ms": latency_ms,
        }
