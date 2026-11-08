"""Run one Studio beat picture. Same Studio path Approve uses."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

from ai_service.prompt_utils import get_default_prompt_config
from ai_service.studio_prompts import VISUAL_GENERATOR_SLUG
from ai_service.studio_settings import (
    settings_patch_for_prompt,
    studio_base_url,
    studio_settings_token,
)

logger = logging.getLogger(__name__)

RUN_TIMEOUT_SECONDS = 180


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def _fail(error: str, *, prompt_config=None, patch: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "result": None,
        "provider": (patch or {}).get("provider") or "",
        "model_id": (patch or {}).get("model_id") or "",
        "temperature": (patch or {}).get("temperature"),
        "instruction_slug": getattr(prompt_config, "slug", "") or "",
        "raw_text": "",
    }


def generate_studio_visual(
    *,
    spoken_line: str = "",
    on_screen: str = "",
    kind: str = "",
    generate_audio: str | bool = False,
    prompt_config=None,
    **_kwargs,
) -> dict[str, Any]:
    text = (spoken_line or "").strip()
    visual = (on_screen or "").strip()
    beat_kind = (kind or "").strip().lower()
    if beat_kind not in {"intro", "wording", "concept"}:
        beat_kind = "concept"
    if not text:
        return _fail("Spoken line is required.")
    if not visual:
        return _fail("On screen is required.")

    if prompt_config is None:
        prompt_config = get_default_prompt_config(VISUAL_GENERATOR_SLUG)
    service_slug = getattr(getattr(prompt_config, "service", None), "slug", "") or ""
    if prompt_config is None:
        return _fail("No Studio Visual Generator prompt. Run setup_studio_ai or pick one.")
    if service_slug and service_slug != VISUAL_GENERATOR_SLUG:
        return _fail("Pick a Studio Visual Generator prompt configuration.")

    patch = settings_patch_for_prompt(prompt_config)
    base = studio_base_url()
    if not base:
        return _fail(
            "LESSON_STUDIO_URL is not set.",
            prompt_config=prompt_config,
            patch=patch,
        )

    payload = {
        "id": f"pg{uuid4().hex[:10]}",
        "text": text,
        "visual": visual,
        "kind": beat_kind,
        "generate_audio": _truthy(generate_audio),
        "visual_generator": patch,
    }
    url = f"{base}/v1/visuals"
    headers = {"Content-Type": "application/json"}
    token = studio_settings_token()
    if token:
        headers["X-Settings-Token"] = token
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=RUN_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            raw = exc.read().decode("utf-8")
            parsed = json.loads(raw)
            detail = str(parsed.get("error") or raw)[:400]
        except Exception:
            detail = str(exc)
        logger.warning("studio_visual: HTTP %s %s", exc.code, detail)
        return _fail(
            detail or f"Studio returned HTTP {exc.code}.",
            prompt_config=prompt_config,
            patch=patch,
        )
    except Exception as exc:
        logger.warning("studio_visual: %s", exc.__class__.__name__)
        return _fail(
            f"Could not reach Studio: {exc.__class__.__name__}",
            prompt_config=prompt_config,
            patch=patch,
        )

    html = body.get("html") or ""
    result = {
        "kind": beat_kind,
        "component": body.get("component"),
        "settings": body.get("settings") or {},
        "duration": body.get("duration"),
        "generate_audio": payload["generate_audio"],
        "html": html,
    }
    return {
        "success": True,
        "error": "",
        "result": result,
        "provider": patch.get("provider") or "",
        "model_id": patch.get("model_id") or "",
        "temperature": patch.get("temperature"),
        "instruction_slug": getattr(prompt_config, "slug", "") or "",
        "raw_text": json.dumps(
            {key: value for key, value in result.items() if key != "html"},
            indent=2,
        ),
    }
