"""
Assign a teacher's question totals across the lessons they selected.

Counts are decided here, before any model call. Each lesson that receives
questions gets its own task. Later lessons (higher order) receive extra
questions after every lesson has one. When there are fewer questions than
lessons, the later lessons get the questions.
"""
from __future__ import annotations

TYPE_ORDER = (
    "multiple_choice",
    "true_false",
    "fill_blank",
    "short_answer",
    "essay",
    "code",
)


def questions_per_lesson(lesson_count: int, total: int) -> list[int]:
    """How many questions each lesson gets. Index 0 is the earliest lesson."""
    if lesson_count <= 0 or total <= 0:
        return [0] * max(lesson_count, 0)
    counts = [0] * lesson_count
    if total >= lesson_count:
        for index in range(lesson_count):
            counts[index] = 1
        remaining = total - lesson_count
        index = lesson_count - 1
        while remaining:
            counts[index] += 1
            remaining -= 1
            index -= 1
            if index < 0:
                index = lesson_count - 1
        return counts
    for offset in range(total):
        counts[lesson_count - 1 - offset] = 1
    return counts


def interleave_types(type_totals: dict[str, int]) -> list[str]:
    """Mix question types so one lesson is not given every question of one type."""
    remaining = {key: max(0, int(type_totals.get(key) or 0)) for key in TYPE_ORDER}
    sequence: list[str] = []
    while any(remaining.values()):
        for key in TYPE_ORDER:
            if remaining[key] > 0:
                sequence.append(key)
                remaining[key] -= 1
    return sequence


def split_type_counts(lessons: list, type_totals: dict[str, int]) -> list[dict]:
    """
    ``lessons`` must already be ordered earliest to latest.

    Returns one plan per lesson that receives at least one question:
    ``{"lesson", "total", "counts"}``. Type counts across plans match
    ``type_totals``.
    """
    totals = {key: max(0, int(type_totals.get(key) or 0)) for key in TYPE_ORDER}
    total = sum(totals.values())
    per_lesson = questions_per_lesson(len(lessons), total)
    sequence = interleave_types(totals)
    cursor = 0
    plans = []
    for lesson, count in zip(lessons, per_lesson):
        if count <= 0:
            continue
        slice_types = sequence[cursor : cursor + count]
        cursor += count
        counts = {key: 0 for key in TYPE_ORDER}
        for kind in slice_types:
            counts[kind] += 1
        plans.append({"lesson": lesson, "total": count, "counts": counts})
    return plans
