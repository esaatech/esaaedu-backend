"""Push Admin Studio prompts and models to lesson-studio PUT /v1/settings."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from decouple import config

from ai_service.config import resolve_generation_settings
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.studio_prompts import STUDIO_SECTION_BY_SLUG, STUDIO_TASK_SLUGS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StudioPushResult:
    ok: bool
    skipped: bool
    error: str = ""
    status_code: int = 0


def studio_base_url() -> str:
    return config("LESSON_STUDIO_URL", default="").strip().rstrip("/")


def studio_settings_token() -> str:
    return config("LESSON_STUDIO_SETTINGS_TOKEN", default="").strip()


def is_studio_push_configured() -> bool:
    return bool(studio_base_url() and studio_settings_token())


def settings_patch_for_prompt(prompt_config) -> dict[str, Any]:
    """One Studio task section: provider, model, temperature, system_prompt."""
    resolved = resolve_generation_settings(prompt_config=prompt_config)
    prompt = (getattr(prompt_config, "system_prompt", None) or "").strip()
    return {
        "provider": resolved.provider,
        "model_id": resolved.model_id,
        "temperature": resolved.temperature,
        "system_prompt": prompt,
    }


def build_studio_settings_patch() -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for slug, section in STUDIO_SECTION_BY_SLUG.items():
        prompt = get_default_prompt_config(slug)
        if prompt is None:
            continue
        patch[section] = settings_patch_for_prompt(prompt)
    return patch


def apply_rewritten_prompt(service_slug: str, system_prompt: str) -> Optional[str]:
    """Write a rewritten instruction onto the target Studio service default prompt."""
    if service_slug not in STUDIO_TASK_SLUGS:
        return f"Unknown Studio service: {service_slug}"
    text = (system_prompt or "").strip()
    if len(text) < 20:
        return "The rewritten instruction is empty."
    prompt = get_default_prompt_config(service_slug)
    if prompt is None:
        return f"No default prompt for {service_slug}. Run setup_studio_ai."
    prompt.system_prompt = text
    prompt.save(update_fields=["system_prompt", "updated_at"])
    return None


def push_studio_settings() -> StudioPushResult:
    """Send the default script and visual prompts to Studio. No-op if env is empty."""
    if not is_studio_push_configured():
        return StudioPushResult(
            ok=True,
            skipped=True,
            error="LESSON_STUDIO_URL or LESSON_STUDIO_SETTINGS_TOKEN is not set.",
        )
    patch = build_studio_settings_patch()
    if not patch:
        return StudioPushResult(
            ok=False,
            skipped=False,
            error="No Studio prompt rows. Run python manage.py setup_studio_ai.",
        )
    url = f"{studio_base_url()}/v1/settings"
    body = json.dumps(patch).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Content-Type": "application/json",
            "X-Settings-Token": studio_settings_token(),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = getattr(response, "status", 200)
            if 200 <= int(status) < 300:
                logger.info("studio_settings: pushed %s to %s", ",".join(patch), url)
                return StudioPushResult(ok=True, skipped=False, status_code=int(status))
            return StudioPushResult(
                ok=False,
                skipped=False,
                status_code=int(status),
                error=f"Studio returned HTTP {status}.",
            )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:400]
        except Exception:
            detail = str(exc)
        logger.warning("studio_settings: push failed HTTP %s %s", exc.code, detail)
        return StudioPushResult(
            ok=False,
            skipped=False,
            status_code=int(exc.code),
            error=detail or f"Studio returned HTTP {exc.code}.",
        )
    except Exception as exc:
        logger.warning("studio_settings: push failed %s", exc.__class__.__name__)
        return StudioPushResult(
            ok=False,
            skipped=False,
            error=f"Could not reach Studio: {exc.__class__.__name__}",
        )
