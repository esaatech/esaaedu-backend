"""Append AI practice cards onto a teacher Coach bank."""

from __future__ import annotations

import random
import uuid
from typing import Any

from django.core.exceptions import ObjectDoesNotExist

from .auto_mix import draw_by_mix, first_auto_mix, normalize_mix
from .card_metadata import (
    FALLBACK_EXPLANATION,
    build_content_catalog,
    normalize_difficulty,
    stored_source,
)
from .deck_generator import generate_deck_for_lesson
from .static_generator import card_avoid_label, dedupe_cards

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


def item_to_session_card(item) -> dict[str, Any]:
    """Map a CoachItem onto the student session card shape (images stay in prompt JSON)."""
    card = card_to_item_fields(
        {
            "question_type": item.question_type,
            "prompt": item.prompt,
            "options": item.options or [],
            "answer": item.answer,
            "hints": item.hints or [],
            "explanation": item.explanation,
            "difficulty": item.difficulty,
            "sources": item.sources or [],
        }
    )
    card["id"] = str(uuid.uuid4())
    return card


def pool_for_difficulty(items: list, difficulty_mode: str) -> list:
    if difficulty_mode == "easy":
        return [item for item in items if item.difficulty == "easy"]
    if difficulty_mode == "hard":
        return [item for item in items if item.difficulty == "hard"]
    return list(items)


def draw_cards_from_bank(
    lesson,
    *,
    difficulty_mode: str,
    card_count: int,
    exclude_prompts: list[str] | None = None,
    next_mix: dict | None = None,
) -> list[dict[str, Any]] | None:
    """
    Sample practice cards from the lesson bank.

    None = no bank / empty bank (caller should live-generate).
    [] = bank exists but nothing left after filters (caller should not live-generate).
    """
    try:
        bank = lesson.coach_bank
    except ObjectDoesNotExist:
        return None
    items = list(bank.items.all())
    if not items:
        return None
    take_n = max(1, min(int(card_count or 6), len(items)))
    if difficulty_mode == "auto":
        mix = normalize_mix(next_mix, default_n=take_n) or first_auto_mix(take_n)
        return draw_by_mix(
            items,
            mix,
            to_card=item_to_session_card,
            avoid_card=item_to_avoid_card,
            exclude_prompts=exclude_prompts,
        )
    excluded = {str(label).strip() for label in (exclude_prompts or []) if str(label).strip()}
    if excluded:
        items = [
            item
            for item in items
            if card_avoid_label(item_to_avoid_card(item)) not in excluded
        ]
    pool = pool_for_difficulty(items, difficulty_mode)
    if not pool:
        return []
    random.shuffle(pool)
    take = max(1, min(int(card_count or 6), len(pool)))
    return [item_to_session_card(item) for item in pool[:take]]


def generate_into_bank(
    bank,
    *,
    difficulty_mode: str = "auto",
    card_count: int = 10,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
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

    unique = dedupe_cards(
        list(deck.get("cards") or []),
        existing=[item_to_avoid_card(item) for item in existing],
    )
    created = []
    for card in unique:
        fields = card_to_item_fields(card)
        if not fields["prompt"]:
            continue
        item = bank.items.create(order=next_order, **fields)
        created.append(item)
        next_order += 1

    if not created:
        return {
            "success": False,
            "error": (
                "Those questions were too similar to ones already in the bank. "
                "Try generating again, or write your own."
            ),
            "error_code": "all_duplicates",
            "status_code": 400,
            "added": 0,
        }

    bank.save(update_fields=["updated_at"])
    return {
        "success": True,
        "added": len(created),
        "items": created,
        "error": "",
        "error_code": "",
        "status_code": 201,
    }
