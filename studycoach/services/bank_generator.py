"""Append AI practice cards onto a teacher Coach bank."""

from __future__ import annotations

from typing import Any

from .card_metadata import (
    FALLBACK_EXPLANATION,
    build_content_catalog,
    normalize_difficulty,
    stored_source,
)
from .deck_generator import generate_deck_for_lesson
from .static_generator import card_avoid_label

MAX_BANK_ITEMS = 100
MAX_GENERATE_PER_REQUEST = 20


def filter_catalog(
    catalog: list[dict[str, Any]], source_ids: list[str] | None
) -> list[dict[str, Any]]:
    if not source_ids:
        return catalog
    wanted = {str(v).strip() for v in source_ids if str(v).strip()}
    if not wanted:
        return catalog
    return [item for item in catalog if str(item.get("id")) in wanted]


def resolve_sources_from_ids(
    source_ids: list[str] | None, catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not source_ids:
        return []
    by_id = {str(item["id"]): item for item in catalog}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in source_ids:
        key = str(raw or "").strip()
        if not key or key in seen:
            continue
        item = by_id.get(key)
        if not item:
            continue
        seen.add(key)
        out.append(stored_source(item))
    return out


def item_to_avoid_card(item) -> dict[str, Any]:
    return {
        "prompt": item.prompt,
        "display": None,
        "display_json": None,
    }


def card_to_item_fields(card: dict[str, Any]) -> dict[str, Any]:
    qtype = str(card.get("question_type") or "short_answer").strip()
    if qtype not in ("multiple_choice", "true_false", "short_answer"):
        qtype = "short_answer"
    options = card.get("options") if isinstance(card.get("options"), list) else []
    hints = card.get("hints") if isinstance(card.get("hints"), list) else []
    sources = card.get("sources") if isinstance(card.get("sources"), list) else []
    return {
        "question_type": qtype,
        "prompt": str(card.get("prompt") or "").strip(),
        "options": [str(o) for o in options if str(o).strip()],
        "answer": str(card.get("answer") or "").strip(),
        "hints": [str(h).strip() for h in hints if str(h).strip()],
        "explanation": str(card.get("explanation") or "").strip() or FALLBACK_EXPLANATION,
        "difficulty": normalize_difficulty(card.get("difficulty")),
        "sources": sources,
    }


def generate_into_bank(
    bank,
    *,
    difficulty_mode: str = "auto",
    card_count: int = 10,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    from .models import CoachItem

    current = bank.items.count()
    room = max(0, MAX_BANK_ITEMS - current)
    requested = max(3, min(int(card_count or 10), MAX_GENERATE_PER_REQUEST, room))
    if room <= 0:
        return {
            "success": False,
            "error": "This lesson already has 100 practice questions.",
            "error_code": "bank_full",
            "status_code": 400,
            "added": 0,
        }
    if requested < 3:
        return {
            "success": False,
            "error": "Add at least 3 questions at a time.",
            "error_code": "too_few",
            "status_code": 400,
            "added": 0,
        }

    catalog = filter_catalog(build_content_catalog(bank.lesson), source_ids)
    existing = list(bank.items.order_by("order"))
    avoid = [card_avoid_label(item_to_avoid_card(item)) for item in existing]
    next_order = (existing[-1].order + 1) if existing else 1

    deck = generate_deck_for_lesson(
        lesson=bank.lesson,
        difficulty_mode=difficulty_mode,
        card_count=requested,
        avoid_prompts=avoid,
        catalog=catalog,
    )
    if not deck.get("success"):
        return {
            "success": False,
            "error": deck.get("error"),
            "error_code": deck.get("error_code") or "generation_failed",
            "status_code": deck.get("status_code") or 503,
            "added": 0,
        }

    created = []
    for card in deck.get("cards") or []:
        fields = card_to_item_fields(card)
        if not fields["prompt"]:
            continue
        item = CoachItem.objects.create(bank=bank, order=next_order, **fields)
        created.append(item)
        next_order += 1
        avoid.append(card_avoid_label({"prompt": fields["prompt"]}))

    bank.save(update_fields=["updated_at"])
    return {
        "success": True,
        "added": len(created),
        "items": created,
        "error": "",
        "error_code": "",
        "status_code": 201,
    }
