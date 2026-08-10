"""
Study Coach deck runner — shared by Admin playground and (Phase 4) studycoach views.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.schemas_study_coach import DifficultyMode, StudyDeckOut

logger = logging.getLogger(__name__)

SERVICE_SLUG = "study_coach_deck"

DEFAULT_INSTRUCTIONS = """You generate Quizlet-style study quiz cards for students.

Rules:
- Return ONLY structured data matching the schema (cards array).
- Each card must include ordered Socratic hints that guide thinking without dumping the final answer in hint 1.
- Hints should be progressive: first nudge, later more specific.
- For multiple_choice / true_false, include options and set answer to exactly one option string.
- For short_answer, answer is the expected brief response; hints still must not fully spoil it in the first hint.
- Match difficulty_mode:
  - easy: mostly multiple_choice / true_false, clearer first hints
  - hard: mostly short_answer, tougher prompts, vaguer early hints
  - auto: mix — start easier, later cards harder
- If lesson grounding text is provided, questions MUST be answerable from that material.
- If only a lesson title is provided, invent fair practice grounded in that title/topic and stay educational.
- Do not include card ids; the server assigns them.
"""


def generate_study_coach_deck(
    *,
    lesson_title: str,
    grounding_text: str = "",
    difficulty_mode: DifficultyMode = "easy",
    card_count: int = 6,
    prompt_config=None,
) -> dict[str, Any]:
    """
    Generate a study quiz deck.

    Returns:
      { success, error, result: {cards: [...]}, provider, model_id, temperature,
        instruction_slug, raw_text, grounding_mode }
    """
    title = (lesson_title or "").strip() or "Untitled lesson"
    grounding = (grounding_text or "").strip()
    mode: DifficultyMode = difficulty_mode if difficulty_mode in ("easy", "hard", "auto") else "easy"
    count = max(3, min(int(card_count or 6), 12))

    if prompt_config is None:
        prompt_config = get_default_prompt_config(SERVICE_SLUG)

    grounding_mode = "grounded" if grounding else "title"

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("study_coach_deck: resolve_model failed: %s", exc)
        return _fail(str(exc), prompt_config=prompt_config, grounding_mode=grounding_mode)
    except Exception as exc:
        logger.exception("study_coach_deck: unexpected resolve failure")
        return _fail(
            f"Failed to resolve model: {exc}",
            prompt_config=prompt_config,
            grounding_mode=grounding_mode,
        )

    instructions = (
        getattr(prompt_config, "system_prompt", None) or DEFAULT_INSTRUCTIONS
    ).strip()

    user_prompt = _build_user_prompt(
        title=title,
        grounding=grounding,
        mode=mode,
        count=count,
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        return _fail(
            f"pydantic-ai is not installed: {exc}",
            prompt_config=prompt_config,
            settings=settings,
            grounding_mode=grounding_mode,
        )

    agent_kwargs: dict[str, Any] = {
        "output_type": StudyDeckOut,
        "instructions": instructions,
        "retries": {"output": 2},
    }
    try:
        from pydantic_ai.settings import ModelSettings

        agent_kwargs["model_settings"] = ModelSettings(temperature=settings.temperature)
    except Exception:
        agent_kwargs["model_settings"] = {"temperature": settings.temperature}

    agent = Agent(model, **agent_kwargs)

    try:
        result = agent.run_sync(user_prompt)
        deck: StudyDeckOut = result.output
        cards = [c.model_dump() for c in deck.cards]
        return {
            "success": True,
            "error": "",
            "result": {"cards": cards},
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": settings.temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": str({"cards": cards})[:20000],
            "grounding_mode": grounding_mode,
        }
    except Exception as exc:
        logger.exception("study_coach_deck: agent run failed")
        return _fail(
            str(exc),
            prompt_config=prompt_config,
            settings=settings,
            grounding_mode=grounding_mode,
            raw_text=str(exc),
        )


def _build_user_prompt(*, title: str, grounding: str, mode: DifficultyMode, count: int) -> str:
    parts = [
        f"Lesson title: {title}",
        f"Difficulty mode: {mode}",
        f"Generate exactly {count} quiz cards.",
    ]
    if grounding:
        parts.append("Lesson grounding material (use ONLY this content for answers):")
        parts.append(grounding[:12000])
    else:
        parts.append(
            "No lesson body provided. Generate fair practice from the lesson title alone."
        )
    return "\n\n".join(parts)


def _fail(
    error: str,
    *,
    prompt_config=None,
    settings=None,
    grounding_mode: str = "title",
    raw_text: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "result": None,
        "provider": getattr(settings, "provider", "") if settings else "",
        "model_id": getattr(settings, "model_id", "") if settings else "",
        "temperature": getattr(settings, "temperature", None) if settings else None,
        "instruction_slug": getattr(prompt_config, "slug", "") or "",
        "raw_text": raw_text,
        "grounding_mode": grounding_mode,
    }
