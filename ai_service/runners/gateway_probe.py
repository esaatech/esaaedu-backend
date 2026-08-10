"""
Gateway probe runner — used by Admin playground (Phase 2).

Product feature runners (Phase 3+) should follow the same return shape:
  { success, error?, ...payload, provider, model_id, temperature, instruction_slug }
"""

from __future__ import annotations

import logging
from typing import Any

from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.schemas import GatewayProbeResult

logger = logging.getLogger(__name__)


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
        return {
            "success": False,
            "error": str(exc),
            "result": None,
            "provider": "",
            "model_id": "",
            "temperature": None,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": None,
        }
    except Exception as exc:
        logger.exception("gateway_probe: unexpected resolve failure")
        return {
            "success": False,
            "error": f"Failed to resolve model: {exc}",
            "result": None,
            "provider": "",
            "model_id": "",
            "temperature": None,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": None,
        }

    instructions = (
        getattr(prompt_config, "system_prompt", None)
        or "You are a connectivity probe. Return structured JSON matching the schema."
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        return {
            "success": False,
            "error": f"pydantic-ai is not installed: {exc}",
            "result": None,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": None,
        }

    agent_kwargs: dict[str, Any] = {
        "output_type": GatewayProbeResult,
        "instructions": instructions,
        "retries": {"output": 2},
    }
    try:
        from pydantic_ai.settings import ModelSettings

        agent_kwargs["model_settings"] = ModelSettings(temperature=settings.temperature)
    except Exception:
        agent_kwargs["model_settings"] = {"temperature": settings.temperature}

    agent = Agent(model, **agent_kwargs)

    try:
        result = agent.run_sync(message)
        payload = result.output.model_dump()
        return {
            "success": True,
            "error": "",
            "result": payload,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": str(payload),
        }
    except Exception as exc:
        logger.exception("gateway_probe: agent run failed")
        return {
            "success": False,
            "error": str(exc),
            "result": None,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": str(exc),
        }
