"""Runtime settings for the ai_service Pydantic AI gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from decouple import config
from django.conf import settings


@dataclass(frozen=True)
class ResolvedGenerationSettings:
    provider: str  # gemini | openai | deepseek
    model_id: str
    temperature: float


def _default_provider() -> str:
    return config("AI_SERVICE_DEFAULT_PROVIDER", default="gemini").strip().lower()


def _default_model_for_provider(provider: str) -> str:
    if provider == "openai":
        return config("AI_SERVICE_OPENAI_MODEL", default="gpt-4o-mini").strip()
    if provider == "deepseek":
        return config("AI_SERVICE_DEEPSEEK_MODEL", default="deepseek-chat").strip()
    # Prefer existing Vertex default when set
    return (
        config("AI_SERVICE_GEMINI_MODEL", default="").strip()
        or getattr(settings, "GEMINI_MODEL", None)
        or config("GEMINI_MODEL", default="gemini-2.5-flash").strip()
    )


def _default_temperature() -> float:
    return config("AI_SERVICE_DEFAULT_TEMPERATURE", default=0.4, cast=float)


def openai_api_key() -> str:
    return config("OPENAI_API_KEY", default="").strip()


def deepseek_api_key() -> str:
    return config("DEEPSEEK_API_KEY", default="").strip()


def gemini_api_key() -> str:
    """Optional Gemini Developer API key (google-gla). Vertex uses ADC instead."""
    return (
        config("GEMINI_API_KEY", default="").strip()
        or config("GOOGLE_API_KEY", default="").strip()
    )


def gcp_project_id() -> str:
    return (
        config("GCP_PROJECT_ID", default="").strip()
        or getattr(settings, "GCP_PROJECT_ID", "")
        or ""
    )


def vertex_location() -> str:
    return (
        config("VERTEX_AI_LOCATION", default="").strip()
        or getattr(settings, "VERTEX_AI_LOCATION", None)
        or "us-central1"
    )


def use_vertex_for_gemini() -> bool:
    """Prefer Vertex when a GCP project is configured (matches existing backend)."""
    flag = config("AI_SERVICE_GEMINI_USE_VERTEX", default="").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    return bool(gcp_project_id())


def http_retry_attempts() -> int:
    return config("AI_SERVICE_HTTP_RETRY_ATTEMPTS", default=4, cast=int)


def resolve_generation_settings(
    *,
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
    prompt_config=None,
) -> ResolvedGenerationSettings:
    """
    Resolve provider/model/temperature.

    Priority for provider/model:
      explicit kwargs → prompt_config.ai_model → env defaults
    Priority for temperature:
      explicit → prompt_config.temperature → ai_model.default_temperature → env
    """
    cfg_provider = None
    cfg_model_id = None
    cfg_temp = None
    model_default_temp = None

    if prompt_config is not None:
        ai_model = getattr(prompt_config, "ai_model", None)
        if ai_model is not None:
            cfg_provider = ai_model.provider
            cfg_model_id = ai_model.model_id
            if ai_model.default_temperature is not None:
                model_default_temp = float(ai_model.default_temperature)
        if getattr(prompt_config, "temperature", None) is not None:
            cfg_temp = float(prompt_config.temperature)

    resolved_provider = (provider or cfg_provider or _default_provider()).lower()
    if resolved_provider not in ("gemini", "openai", "deepseek"):
        raise ValueError(f"Unsupported AI provider: {resolved_provider}")

    resolved_model = model_id or cfg_model_id or _default_model_for_provider(resolved_provider)
    if not resolved_model:
        raise ValueError(f"No model_id configured for provider={resolved_provider}")

    if temperature is not None:
        resolved_temp = float(temperature)
    elif cfg_temp is not None:
        resolved_temp = cfg_temp
    elif model_default_temp is not None:
        resolved_temp = model_default_temp
    else:
        resolved_temp = _default_temperature()

    return ResolvedGenerationSettings(
        provider=resolved_provider,
        model_id=resolved_model,
        temperature=resolved_temp,
    )
