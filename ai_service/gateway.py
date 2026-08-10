"""
Pydantic AI model resolution for ai_service.

Phase 1: build a Model instance from AIPromptConfiguration or explicit overrides.
Feature runners (Phase 3+) call resolve_model() then Agent(..., model=...).
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from .config import (
    ResolvedGenerationSettings,
    deepseek_api_key,
    gemini_api_key,
    gcp_project_id,
    openai_api_key,
    resolve_generation_settings,
    use_vertex_for_gemini,
    vertex_location,
)
from .exceptions import AIServiceGatewayError
from .http_client import get_retrying_http_client

logger = logging.getLogger(__name__)

__all__ = ["AIServiceGatewayError", "resolve_model"]


def resolve_model(
    prompt_config=None,
    *,
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Tuple[Any, ResolvedGenerationSettings]:
    """
    Return (pydantic_ai Model, ResolvedGenerationSettings).

    Temperature is returned in settings for Agent ModelSettings; not all Model
    constructors accept temperature at build time.
    """
    settings = resolve_generation_settings(
        provider=provider,
        model_id=model_id,
        temperature=temperature,
        prompt_config=prompt_config,
    )
    model = _build_model(settings)
    logger.info(
        "ai_service.gateway: resolved provider=%s model_id=%s temperature=%s",
        settings.provider,
        settings.model_id,
        settings.temperature,
    )
    return model, settings


def _build_model(settings: ResolvedGenerationSettings) -> Any:
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
    except ImportError as exc:
        raise AIServiceGatewayError(
            "pydantic-ai is not installed. Add pydantic-ai to project dependencies."
        ) from exc

    http_client = get_retrying_http_client()

    if settings.provider == "openai":
        key = openai_api_key()
        if not key:
            raise AIServiceGatewayError("OPENAI_API_KEY is not configured")
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIChatModel(
            settings.model_id,
            provider=OpenAIProvider(api_key=key, http_client=http_client),
        )

    if settings.provider == "deepseek":
        key = deepseek_api_key()
        if not key:
            raise AIServiceGatewayError("DEEPSEEK_API_KEY is not configured")
        from pydantic_ai.providers.deepseek import DeepSeekProvider

        return OpenAIChatModel(
            settings.model_id,
            provider=DeepSeekProvider(api_key=key, http_client=http_client),
        )

    if settings.provider == "gemini":
        return _build_gemini_model(settings.model_id, http_client)

    raise AIServiceGatewayError(f"Unsupported provider: {settings.provider}")


def _build_gemini_model(model_id: str, http_client) -> Any:
    from pydantic_ai.models.google import GoogleModel

    if use_vertex_for_gemini():
        project = gcp_project_id()
        if not project:
            raise AIServiceGatewayError(
                "GCP_PROJECT_ID is required when AI_SERVICE_GEMINI_USE_VERTEX is enabled"
            )
        try:
            from pydantic_ai.providers.google import GoogleProvider
        except ImportError as exc:
            raise AIServiceGatewayError(
                "Google provider extras missing for pydantic-ai"
            ) from exc

        # Vertex AI via ADC / service account (same as existing GeminiService)
        provider = GoogleProvider(
            vertexai=True,
            project=project,
            location=vertex_location(),
            http_client=http_client,
        )
        return GoogleModel(model_id, provider=provider)

    key = gemini_api_key()
    if not key:
        raise AIServiceGatewayError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is required when not using Vertex"
        )
    from pydantic_ai.providers.google import GoogleProvider

    provider = GoogleProvider(api_key=key, http_client=http_client)
    return GoogleModel(model_id, provider=provider)
