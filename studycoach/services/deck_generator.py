"""
Study Coach deck generation for student sessions.

Calls the shared ai_service runner (same as Admin playground).
No static fallback — callers must surface a friendly try-again on failure.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from django.utils.html import strip_tags

from ai_service.exceptions import USER_FACING_AI_SERVICE_ERROR
from ai_service.runners.study_coach_deck import generate_study_coach_deck

from .static_generator import dedupe_cards

logger = logging.getLogger(__name__)

MAX_GROUNDING_CHARS = 12000
MIN_CARD_COUNT = 3
MAX_CARD_COUNT = 20
DEFAULT_CARD_COUNT = 6
MAX_PAGE_CATALOG = 60
FALLBACK_EXPLANATION = "Review this idea in the lesson, then try a similar problem."


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


def _page_excerpt(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return ""
    if text.startswith("[") or text.startswith("{"):
        return ""
    return strip_tags(text).replace("\xa0", " ").strip()[:180]


def build_page_catalog(lesson) -> list[dict[str, Any]]:
    """Book pages for this lesson — ids the model may cite as source_page_id."""
    from courses.models import BookPage

    pages = (
        BookPage.objects.filter(book_material__lessons=lesson)
        .select_related("book_material")
        .order_by("book_material__order", "page_number")[:MAX_PAGE_CATALOG]
    )
    catalog: list[dict[str, Any]] = []
    for page in pages:
        catalog.append(
            {
                "id": str(page.id),
                "material_id": str(page.book_material_id),
                "page": int(page.page_number),
                "title": (page.title or "").strip() or f"Page {page.page_number}",
                "excerpt": _page_excerpt(page.content),
            }
        )
    return catalog


def format_page_catalog_for_prompt(catalog: list[dict[str, Any]]) -> str:
    if not catalog:
        return ""
    lines = []
    for item in catalog:
        excerpt = (item.get("excerpt") or "").strip()
        title = item.get("title") or f"Page {item.get('page')}"
        line = f"- id={item['id']} | page={item['page']} | title={title}"
        if excerpt:
            line += f" | excerpt={excerpt}"
        lines.append(line)
    return "\n".join(lines)


def resolve_card_source(
    card: dict[str, Any], catalog: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Map a model-cited page id (or unique page number) to a stored source object."""
    if not catalog:
        return None
    raw = str(card.get("source_page_id") or "").strip()
    by_id = {str(item["id"]): item for item in catalog}
    matched = by_id.get(raw)
    if not matched and raw.isdigit():
        hits = [item for item in catalog if int(item.get("page") or 0) == int(raw)]
        if len(hits) == 1:
            matched = hits[0]
    if not matched and len(catalog) == 1:
        matched = catalog[0]
    if not matched:
        return None
    return {
        "material_id": str(matched["material_id"]),
        "page": int(matched["page"]),
        "title": str(matched.get("title") or f"Page {matched['page']}"),
    }


def attach_card_sources(
    cards: list[dict[str, Any]], catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Stamp validated `source` onto cards; drop invented source_page_id values."""
    attached: list[dict[str, Any]] = []
    for card in cards:
        item = dict(card)
        explanation = str(item.get("explanation") or "").strip()
        item["explanation"] = explanation or FALLBACK_EXPLANATION
        source = resolve_card_source(item, catalog)
        item.pop("source_page_id", None)
        if source:
            item["source"] = source
        else:
            item.pop("source", None)
        attached.append(item)
    return attached


def _parse_display_json(raw: Any) -> dict[str, Any] | None:
    """Parse model-provided display_json string into a display object."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("studycoach invalid display_json=%s", text[:200])
        return None
    if not isinstance(data, dict):
        return None
    return data


def normalize_card_display(card: dict[str, Any]) -> dict[str, Any]:
    """Promote display_json → display for the frontend."""
    item = dict(card)
    existing = item.get("display")
    if isinstance(existing, dict) and existing.get("type"):
        return item

    parsed = _parse_display_json(item.get("display_json"))
    if parsed and parsed.get("type") == "column_math":
        operands = parsed.get("operands") or []
        if not isinstance(operands, list):
            operands = []
        item["display"] = {
            "type": "column_math",
            "operator": str(parsed.get("operator") or "+"),
            "operands": [str(o).strip() for o in operands if o is not None and str(o).strip()],
        }
    return item


def stamp_card_ids(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure each card has a server-assigned UUID id and normalized display."""
    stamped: list[dict[str, Any]] = []
    for card in cards:
        item = normalize_card_display(dict(card))
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
    catalog = build_page_catalog(lesson)
    count = clamp_card_count(card_count)

    raw = generate_study_coach_deck(
        lesson_title=title,
        grounding_text=grounding,
        difficulty_mode=difficulty_mode,  # type: ignore[arg-type]
        card_count=count,
        avoid_prompts=avoid_prompts or [],
        page_catalog_text=format_page_catalog_for_prompt(catalog),
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

    stamped = attach_card_sources(dedupe_cards(stamp_card_ids(cards)), catalog)
    if not stamped:
        logger.warning(
            "studycoach deck empty after dedupe lesson=%s provider=%s model=%s",
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
        "cards": stamped,
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


