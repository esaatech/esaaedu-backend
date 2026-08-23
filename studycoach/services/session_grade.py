"""Grade a finished Study Coach session, then ask the coach for next-step feedback."""

from __future__ import annotations

from typing import Any

from ai_service.runners.study_coach_feedback import generate_study_coach_feedback

from .auto_mix import band_scores, fallback_next, infer_rung, normalize_mix
from .card_metadata import build_content_catalog, format_content_catalog_for_prompt
from .grading import grade_study_card
from .lesson_memory import (
    apply_coach_result,
    get_or_create_memory,
    hydrate_study_sources,
    memory_prompt_text,
)
from .static_generator import default_progress, prompt_plain_text


def _card_line(card: dict[str, Any], entry: dict[str, Any]) -> str:
    sources = card.get("sources") if isinstance(card.get("sources"), list) else []
    ids = [str(s.get("id")) for s in sources if isinstance(s, dict) and s.get("id")]
    titles = [str(s.get("title") or "") for s in sources if isinstance(s, dict)]
    prompt = prompt_plain_text(str(card.get("prompt") or ""))[:160]
    correct = "yes" if entry.get("correct") else "no"
    return (
        f"- difficulty={card.get('difficulty') or 'easy'} type={card.get('question_type')} "
        f"correct={correct} sources={','.join(ids) or '(none)'} "
        f"titles={'; '.join(t for t in titles if t) or '(none)'} prompt={prompt}"
    )


def grade_and_coach_session(session) -> dict[str, Any]:
    progress = dict(session.progress or default_progress())
    answers = dict(progress.get("answers") or {})
    cards = list(session.cards or [])

    if not progress.get("graded"):
        correct_count = 0
        incorrect_count = 0
        for card in cards:
            cid = str(card.get("id") or "")
            if not cid:
                continue
            entry = dict(answers.get(cid) or {})
            response_text = str(entry.get("response") or "")
            correct, grade_meta = grade_study_card(
                card,
                response_text,
                lesson=session.lesson,
                fallback_on_ai_error=True,
            )
            entry["response"] = response_text
            entry["correct"] = correct
            entry["skipped"] = not response_text.strip()
            entry["graded"] = True
            entry.update(grade_meta)
            answers[cid] = entry
            if correct:
                correct_count += 1
            else:
                incorrect_count += 1
        progress["answers"] = answers
        progress["correct_count"] = correct_count
        progress["incorrect_count"] = incorrect_count
        progress["graded"] = True
        progress["current_index"] = len(cards)
        progress["streak"] = 0
        session.progress = progress
        session.status = "completed"
        session.save(update_fields=["progress", "status", "updated_at"])

    scores = band_scores(cards, answers)
    memory = get_or_create_memory(session.student, session.lesson)
    catalog = build_content_catalog(session.lesson)
    n = max(3, len(cards) or 6)
    scores_text = " ".join(
        f"{band}={scores[band]['correct']}/{scores[band]['total']}"
        for band in ("easy", "intermediate", "hard")
    )
    cards_text = "\n".join(_card_line(card, answers.get(str(card.get("id") or "")) or {}) for card in cards)

    headline = ""
    message = ""
    action = "practice"
    next_mix = None
    study_ids: list[str] = []
    used_ai = False

    if session.difficulty_mode == "auto":
        raw = generate_study_coach_feedback(
            lesson_title=(getattr(session.lesson, "title", None) or "").strip(),
            catalog_text=format_content_catalog_for_prompt(catalog),
            cards_text=cards_text,
            band_scores_text=scores_text,
            memory_text=memory_prompt_text(memory),
            card_count=n,
        )
        if raw.get("success") and isinstance(raw.get("result"), dict):
            result = raw["result"]
            mix = normalize_mix(result.get("next_mix"))
            action = result.get("action") or "practice"
            if action not in ("practice", "study_then_retake", "mastered"):
                action = "practice"
            headline = str(result.get("headline") or "").strip()
            message = str(result.get("message") or "").strip()
            study_ids = [str(v).strip() for v in (result.get("study_source_ids") or []) if str(v).strip()]
            if mix:
                next_mix = mix
                used_ai = True
            elif action in ("mastered", "study_then_retake"):
                used_ai = True
                next_mix = mix or normalize_mix(memory.next_mix)

    if not used_ai:
        action, rung, next_mix = fallback_next(
            cards=cards,
            answers=answers,
            rung=memory.auto_rung or "mix_easy",
            card_count=n,
        )
        if not headline:
            if action == "mastered":
                headline = "You have got this lesson."
                message = "You answered the hard questions well. Come back anytime to review."
            elif rung == "mix_climb":
                headline = "Nice work on the easy questions."
                message = "Next quiz we will go more intermediate."
            elif rung == "all_hard":
                headline = "You are ready for a harder set."
                message = "Next quiz will be all hard questions from this lesson."
            else:
                headline = "Keep practicing."
                message = "We will mix easy, intermediate, and hard again so you can build confidence."
        auto_rung = rung
    else:
        auto_rung = infer_rung(next_mix, action)
        if not headline:
            headline = "Session complete"
        if not message:
            message = "Here is what to do next."

    if session.difficulty_mode != "auto":
        action = "practice"
        next_mix = None
        study_ids = []
        auto_rung = memory.auto_rung or "mix_easy"
        if not headline:
            headline = "Session complete"
            correct = int(progress.get("correct_count") or 0)
            total = max(1, len(cards))
            message = f"You got {correct} of {total} correct."

    if action == "study_then_retake" and not study_ids and next_mix:
        study_ids = list(next_mix.get("source_ids") or [])
    study_sources = hydrate_study_sources(study_ids, catalog)
    if next_mix:
        allowed = {str(item.get("id")) for item in catalog}
        next_mix["source_ids"] = [
            sid for sid in (next_mix.get("source_ids") or []) if sid in allowed
        ]

    if session.difficulty_mode == "auto":
        apply_coach_result(
            memory,
            action=action,
            next_mix=next_mix,
            study_sources=study_sources,
            headline=headline,
            message=message,
            band_scores=scores,
            session=session,
            auto_rung=auto_rung,
        )
    else:
        memory.last_feedback = {"headline": headline, "message": message}
        memory.last_band_scores = scores
        memory.last_session = session
        memory.save(update_fields=["last_feedback", "last_band_scores", "last_session", "updated_at"])

    return {
        "session": session,
        "feedback": {
            "headline": headline,
            "message": message,
            "action": action,
            "next_mix": next_mix,
            "study_sources": study_sources,
            "mastered": action == "mastered",
        },
        "memory": memory,
    }
