"""Auto mix counts, bank draw by band, and score-ladder fallback."""

from __future__ import annotations

import random
from typing import Any

from .static_generator import card_avoid_label

FIRST_WEIGHTS = (5, 3, 2)
CLIMB_WEIGHTS = (2, 5, 3)
BANDS = ("easy", "intermediate", "hard")
ORDERS = ("easy_first", "hard_first", "shuffled")


def allocate_counts(n: int, weights: tuple[int, int, int] = FIRST_WEIGHTS) -> dict[str, int]:
    n = max(0, int(n or 0))
    if n <= 0:
        return {band: 0 for band in BANDS}
    total_w = sum(weights) or 1
    raw = [n * w / total_w for w in weights]
    counts = [int(x) for x in raw]
    remainder = n - sum(counts)
    order = sorted(range(3), key=lambda i: (-(raw[i] - counts[i]), i))
    for i in range(remainder):
        counts[order[i % 3]] += 1
    return {BANDS[i]: counts[i] for i in range(3)}


def first_auto_mix(n: int) -> dict[str, Any]:
    counts = allocate_counts(n, FIRST_WEIGHTS)
    counts["order"] = "easy_first"
    counts["source_ids"] = []
    return counts


def climb_mix(n: int) -> dict[str, Any]:
    counts = allocate_counts(n, CLIMB_WEIGHTS)
    counts["order"] = "easy_first"
    counts["source_ids"] = []
    return counts


def all_hard_mix(n: int) -> dict[str, Any]:
    return {"easy": 0, "intermediate": 0, "hard": max(0, int(n or 0)), "order": "shuffled", "source_ids": []}


def normalize_mix(raw: Any, *, default_n: int = 6) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    easy = max(0, int(raw.get("easy") or 0))
    intermediate = max(0, int(raw.get("intermediate") or 0))
    hard = max(0, int(raw.get("hard") or 0))
    if easy + intermediate + hard <= 0:
        return None
    order = str(raw.get("order") or "easy_first").strip()
    if order not in ORDERS:
        order = "easy_first"
    source_ids = []
    seen: set[str] = set()
    for item in raw.get("source_ids") or []:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        source_ids.append(key)
    return {
        "easy": easy,
        "intermediate": intermediate,
        "hard": hard,
        "order": order,
        "source_ids": source_ids,
    }


def mix_from_rung(rung: str, n: int) -> dict[str, Any]:
    if rung == "mix_climb":
        return climb_mix(n)
    if rung == "all_hard":
        return all_hard_mix(n)
    return first_auto_mix(n)


def infer_rung(mix: dict[str, Any] | None, action: str = "") -> str:
    if action == "mastered":
        return "mastered"
    if not mix:
        return "mix_easy"
    easy = int(mix.get("easy") or 0)
    intermediate = int(mix.get("intermediate") or 0)
    hard = int(mix.get("hard") or 0)
    if hard > 0 and easy == 0 and intermediate == 0:
        return "all_hard"
    if intermediate >= easy and intermediate >= hard and intermediate > 0:
        return "mix_climb"
    return "mix_easy"


def item_source_ids(item) -> set[str]:
    sources = getattr(item, "sources", None) or []
    ids: set[str] = set()
    if isinstance(sources, list):
        for raw in sources:
            if isinstance(raw, dict):
                key = str(raw.get("id") or "").strip()
                if key:
                    ids.add(key)
    return ids


def filter_items_by_sources(items: list, source_ids: list[str] | None) -> list:
    wanted = {str(v).strip() for v in (source_ids or []) if str(v).strip()}
    if not wanted:
        return list(items)
    return [item for item in items if item_source_ids(item) & wanted]


def exclude_seen(items: list, exclude_prompts: list[str] | None, avoid_card) -> list:
    excluded = {str(label).strip() for label in (exclude_prompts or []) if str(label).strip()}
    if not excluded:
        return list(items)
    return [
        item
        for item in items
        if card_avoid_label(avoid_card(item)) not in excluded
    ]


def draw_by_mix(
    items: list,
    mix: dict[str, Any],
    *,
    to_card,
    avoid_card,
    exclude_prompts: list[str] | None = None,
) -> list[dict[str, Any]]:
    pool = exclude_seen(items, exclude_prompts, avoid_card)
    pool = filter_items_by_sources(pool, mix.get("source_ids") or [])
    by_band: dict[str, list] = {band: [] for band in BANDS}
    for item in pool:
        band = str(getattr(item, "difficulty", "") or "easy")
        if band not in by_band:
            band = "easy"
        by_band[band].append(item)
    taken: dict[str, list] = {}
    for band in BANDS:
        bucket = list(by_band[band])
        random.shuffle(bucket)
        want = max(0, int(mix.get(band) or 0))
        taken[band] = bucket[:want]
    order = str(mix.get("order") or "easy_first")
    if order == "hard_first":
        seq = taken["hard"] + taken["intermediate"] + taken["easy"]
    elif order == "shuffled":
        seq = taken["easy"] + taken["intermediate"] + taken["hard"]
        random.shuffle(seq)
    else:
        seq = taken["easy"] + taken["intermediate"] + taken["hard"]
    return [to_card(item) for item in seq]


def band_scores(cards: list[dict[str, Any]], answers: dict[str, Any]) -> dict[str, dict[str, int]]:
    scores = {band: {"correct": 0, "total": 0} for band in BANDS}
    for card in cards:
        band = str(card.get("difficulty") or "easy")
        if band not in scores:
            band = "easy"
        cid = str(card.get("id") or "")
        entry = answers.get(cid) or {}
        scores[band]["total"] += 1
        if entry.get("correct"):
            scores[band]["correct"] += 1
    return scores


def fallback_next(
    *,
    cards: list[dict[str, Any]],
    answers: dict[str, Any],
    rung: str,
    card_count: int,
) -> tuple[str, str, dict[str, Any]]:
    """
    Returns (action, next_rung, next_mix).
    Rung-up requires 100% on the focus band.
    """
    n = max(3, int(card_count or len(cards) or 6))
    scores = band_scores(cards, answers)
    current = rung if rung in ("mix_easy", "mix_climb", "all_hard", "mastered") else "mix_easy"

    def perfect(band: str) -> bool:
        total = scores[band]["total"]
        return total > 0 and scores[band]["correct"] == total

    if current == "mastered":
        return "mastered", "mastered", all_hard_mix(n)
    if current == "mix_easy":
        if perfect("easy"):
            return "practice", "mix_climb", climb_mix(n)
        return "practice", "mix_easy", first_auto_mix(n)
    if current == "mix_climb":
        if perfect("intermediate"):
            return "practice", "all_hard", all_hard_mix(n)
        return "practice", "mix_climb", climb_mix(n)
    if perfect("hard"):
        return "mastered", "mastered", all_hard_mix(n)
    return "practice", "all_hard", all_hard_mix(n)
