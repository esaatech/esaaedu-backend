"""Per-student lesson memory for Auto mix and study gate."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from ..models import CoachLessonMemory
from .auto_mix import infer_rung, normalize_mix
from .card_metadata import stored_source


def get_memory(student, lesson) -> CoachLessonMemory | None:
    return CoachLessonMemory.objects.filter(student=student, lesson=lesson).first()


def get_or_create_memory(student, lesson) -> CoachLessonMemory:
    memory, _created = CoachLessonMemory.objects.get_or_create(
        student=student,
        lesson=lesson,
    )
    return memory


def study_gate_blocks(memory: CoachLessonMemory | None) -> bool:
    if not memory:
        return False
    return memory.action == "study_then_retake" and memory.study_cleared_at is None


def clear_study_gate(memory: CoachLessonMemory) -> CoachLessonMemory:
    memory.study_cleared_at = timezone.now()
    memory.save(update_fields=["study_cleared_at", "updated_at"])
    return memory


def hydrate_study_sources(raw_ids: list[str] | None, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .card_metadata import resolve_catalog_item

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_ids or []:
        item = resolve_catalog_item(str(raw), catalog)
        if not item:
            continue
        key = str(item.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(stored_source(item))
    return out


def apply_coach_result(
    memory: CoachLessonMemory,
    *,
    action: str,
    next_mix: dict[str, Any] | None,
    study_sources: list[dict[str, Any]],
    headline: str,
    message: str,
    band_scores: dict[str, Any],
    session,
    auto_rung: str | None = None,
) -> CoachLessonMemory:
    mix = normalize_mix(next_mix)
    memory.action = action if action in ("practice", "study_then_retake", "mastered") else "practice"
    memory.next_mix = mix or {}
    memory.study_sources = study_sources
    memory.last_feedback = {"headline": headline, "message": message}
    memory.last_band_scores = band_scores
    memory.last_session = session
    memory.auto_rung = auto_rung or infer_rung(mix, memory.action)
    if memory.action == "study_then_retake":
        memory.study_cleared_at = None
    memory.save()
    return memory


def memory_prompt_text(memory: CoachLessonMemory | None) -> str:
    if not memory:
        return ""
    mix = memory.next_mix or {}
    source_ids = mix.get("source_ids") or [s.get("id") for s in (memory.study_sources or []) if isinstance(s, dict)]
    lines = [
        f"action={memory.action}",
        f"auto_rung={memory.auto_rung}",
        f"next_mix easy={mix.get('easy')} intermediate={mix.get('intermediate')} hard={mix.get('hard')} order={mix.get('order')}",
        f"source_ids={', '.join(str(s) for s in source_ids if s) or '(none)'}",
        f"study_cleared={'yes' if memory.study_cleared_at else 'no'}",
    ]
    return "\n".join(lines)
