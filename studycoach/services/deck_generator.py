"""
Study Coach deck generation for student sessions.

Calls the shared ai_service runner (same as Admin playground).
No static fallback — callers must surface a friendly try-again on failure.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.utils.html import strip_tags

from ai_service.exceptions import USER_FACING_AI_SERVICE_ERROR
from ai_service.runners.study_coach_deck import generate_study_coach_deck

logger = logging.getLogger(__name__)

MAX_GROUNDING_CHARS = 12000
MIN_CARD_COUNT = 3
MAX_CARD_COUNT = 20
DEFAULT_CARD_COUNT = 6


def clamp_card_count(value: int | None, *, default: int = DEFAULT_CARD_COUNT) -> int:
    try:
        n = int(value if value is not None else default)
    except (TypeError, ValueError):
        n = default
    return max(MIN_CARD_COUNT, min(n, MAX_CARD_COUNT))


def build_lesson_grounding(lesson) -> str:
    """
    Extract lesson description for grounding (HTML stripped).

    Empty string means title-only grounding_mode from the runner.
    """
    raw = (getattr(lesson, "description", None) or "").strip()
    if not raw:
        return ""

    text = strip_tags(raw).replace("\xa0", " ").strip()
    if not text:
        return ""

    return text[:MAX_GROUNDING_CHARS]


def stamp_card_ids(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure each card has a server-assigned UUID id."""
    stamped: list[dict[str, Any]] = []
    for card in cards:
        item = dict(card)
        item["id"] = str(uuid.uuid4())
        stamped.append(item)
    return stamped


def generate_deck_for_lesson(
    *,
    lesson,
    difficulty_mode: str = "easy",
    card_count: int = DEFAULT_CARD_COUNT,
    avoid_prompts: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build grounding from lesson and run study_coach_deck.

    Returns:
      On success: {
        success: True,
        cards: [...with ids...],
        grounding_mode: "grounded"|"title",
        provider, model_id, ...
      }
      On failure: {
        success: False,
        error: USER_FACING_AI_SERVICE_ERROR,
        error_code: str,
        status_code: int,
        grounding_mode: ...,
      }
    """
    title = (getattr(lesson, "title", None) or "").strip() or "Untitled lesson"
    grounding = build_lesson_grounding(lesson)
    count = clamp_card_count(card_count)

    raw = generate_study_coach_deck(
        lesson_title=title,
        grounding_text=grounding,
        difficulty_mode=difficulty_mode,  # type: ignore[arg-type]
        card_count=count,
        avoid_prompts=avoid_prompts or [],
    )

    if not raw.get("success"):
        error_code = (raw.get("error_code") or "generation_failed") or "generation_failed"
        status_code = _status_for_error_code(error_code)
        logger.warning(
            "studycoach deck failed lesson=%s error_code=%s provider=%s model=%s detail=%s",
            getattr(lesson, "id", None),
            error_code,
            raw.get("provider"),
            raw.get("model_id"),
            (raw.get("error") or "")[:300],
        )
        return {
            "success": False,
            "error": USER_FACING_AI_SERVICE_ERROR,
            "error_code": error_code,
            "status_code": status_code,
            "grounding_mode": raw.get("grounding_mode") or ("grounded" if grounding else "title"),
            "provider": raw.get("provider") or "",
            "model_id": raw.get("model_id") or "",
        }

    result = raw.get("result") or {}
    cards = result.get("cards") if isinstance(result, dict) else None
    if not isinstance(cards, list) or not cards:
        logger.warning(
            "studycoach deck empty cards lesson=%s provider=%s model=%s",
            getattr(lesson, "id", None),
            raw.get("provider"),
            raw.get("model_id"),
        )
        return {
            "success": False,
            "error": USER_FACING_AI_SERVICE_ERROR,
            "error_code": "generation_failed",
            "status_code": 503,
            "grounding_mode": raw.get("grounding_mode") or ("grounded" if grounding else "title"),
            "provider": raw.get("provider") or "",
            "model_id": raw.get("model_id") or "",
        }

    return {
        "success": True,
        "cards": stamp_card_ids(cards),
        "grounding_mode": raw.get("grounding_mode") or ("grounded" if grounding else "title"),
        "provider": raw.get("provider") or "",
        "model_id": raw.get("model_id") or "",
        "temperature": raw.get("temperature"),
        "instruction_slug": raw.get("instruction_slug") or "",
        "error": "",
        "error_code": "",
        "status_code": 201,
    }


def _status_for_error_code(error_code: str) -> int:
    if error_code == "rate_limited":
        return 429
    if error_code in ("ai_not_configured", "service_unavailable", "permission_denied"):
        return 503
    return 503


