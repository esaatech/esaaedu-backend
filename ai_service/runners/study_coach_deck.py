"""
Study Coach deck runner — shared by Admin playground and studycoach views.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas_study_coach import DifficultyMode, StudyDeckOut

logger = logging.getLogger(__name__)

SERVICE_SLUG = "study_coach_deck"
PROMPT_SLUG_V1 = "default"
PROMPT_SLUG_MATH_DISPLAY = "math_display"

DEFAULT_INSTRUCTIONS_V1 = """You generate Quizlet-style study quiz cards for students.

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
- If lesson description is provided, questions MUST be answerable from that material.
- If only a lesson title is provided, invent fair practice grounded in that title/topic and stay educational.
- Do not include card ids; the server assigns them.
"""

MATH_DISPLAY_INSTRUCTIONS = """You generate Quizlet-style study quiz cards for students.

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
- If lesson description is provided, questions MUST be answerable from that material.
- If only a lesson title is provided, invent fair practice grounded in that title/topic and stay educational.
- Do not include card ids; the server assigns them.
- Do not return HTML, Markdown tables, or Manim/Python.

Math display:
- For school-style stacked arithmetic (add/subtract/multiply/divide in a column), you MUST set display_json to a JSON string, for example:
  "{\"type\":\"column_math\",\"operator\":\"+\",\"operands\":[\"42\",\"35\"]}"
  Allowed operators: +, -, ×, ÷ (you may also use *, /, x).
  Put 2–4 operands as strings.
  Keep prompt as a short instruction such as "Add these numbers."
  Keep answer as a plain digit string without thousand separators (e.g. "4287", not "4,287").
  Never reuse the same operands+operator pair in the same deck.
- Do NOT copy example problems from the lesson description verbatim (e.g. if the description shows 387+49 or 402-168, invent different numbers of similar difficulty).
- For other math in prompt, hints, options, answer, or explanation (fractions, exponents, roots), use LaTeX with $...$ or $$...$$. Example: $\\frac{1}{2}$, $x^2$.
- If the card is not stacked arithmetic, omit display_json (or set it null).
"""

# Code fallback when no prompt config is loaded — matches the current product default.
DEFAULT_INSTRUCTIONS = MATH_DISPLAY_INSTRUCTIONS


def generate_study_coach_deck(
    *,
    lesson_title: str,
    grounding_text: str = "",
    difficulty_mode: DifficultyMode = "easy",
    card_count: int = 6,
    prompt_config=None,
    avoid_prompts: Optional[list[str]] = None,
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
    count = max(1, min(int(card_count or 6), 20))

    if prompt_config is None:
        prompt_config = get_default_prompt_config(SERVICE_SLUG)

    grounding_mode = "grounded" if grounding else "title"

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("study_coach_deck: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_deck:resolve_model",
            endpoint="ai_service.runners.study_coach_deck",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            grounding_mode=grounding_mode,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("study_coach_deck: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_deck:resolve_model",
            endpoint="ai_service.runners.study_coach_deck",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            grounding_mode=grounding_mode,
            error_code=ai_exc.error_code,
        )

    log_run_model(
        service=SERVICE_SLUG,
        provider=settings.provider,
        model_id=settings.model_id,
        temperature=settings.temperature,
        extra=f"difficulty={mode} grounding_mode={grounding_mode} cards={count}",
    )

    instructions = (
        getattr(prompt_config, "system_prompt", None) or DEFAULT_INSTRUCTIONS
    ).strip()

    user_prompt = _build_user_prompt(
        title=title,
        grounding=grounding,
        mode=mode,
        count=count,
        avoid_prompts=avoid_prompts or [],
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc,
            context="study_coach_deck:import",
            endpoint="ai_service.runners.study_coach_deck",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            grounding_mode=grounding_mode,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=StudyDeckOut,
        instructions=instructions,
        retries={"output": 2},
        model_settings=request_model_settings(temperature=settings.temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(agent, user_prompt)
        deck: StudyDeckOut = result.output
        cards = [c.model_dump() for c in deck.cards]
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=True,
            latency_ms=latency_ms,
            grounding_mode=grounding_mode,
            extra=f"cards={len(cards)}",
        )
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
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("study_coach_deck: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=f"study_coach_deck provider={settings.provider} model={settings.model_id}",
            endpoint="ai_service.runners.study_coach_deck",
        )
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=False,
            latency_ms=latency_ms,
            grounding_mode=grounding_mode,
            extra=f"error_code={ai_exc.error_code}",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            grounding_mode=grounding_mode,
            raw_text=str(exc),
            error_code=ai_exc.error_code,
        )


def _build_user_prompt(
    *,
    title: str,
    grounding: str,
    mode: DifficultyMode,
    count: int,
    avoid_prompts: Optional[list[str]] = None,
) -> str:
    parts = [
        f"Lesson title: {title}",
        f"Difficulty mode: {mode}",
        f"Generate exactly {count} quiz cards.",
    ]
    if grounding:
        parts.append("Lesson description (use ONLY this for answers):")
        parts.append(grounding[:12000])
    else:
        parts.append(
            "No lesson description provided. Generate fair practice from the lesson title alone."
        )
    avoid = [p.strip() for p in (avoid_prompts or []) if (p or "").strip()]
    if avoid:
        parts.append(
            "Do NOT repeat or closely rephrase these existing questions; make new ones. "
            "For stacked math, do not reuse the same operands/operator:"
        )
        parts.append("\n".join(f"- {p[:200]}" for p in avoid[:40]))
    parts.append(
        "Within this deck, every card must be distinct "
        "(different prompts, or different operands/operators for column math). "
        "Do not reuse example numbers from the lesson description; invent fresh problems."
    )
    return "\n\n".join(parts)


def _fail(
    error: str,
    *,
    prompt_config=None,
    settings=None,
    grounding_mode: str = "title",
    raw_text: Optional[str] = None,
    error_code: str = "",
) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "error_code": error_code,
        "result": None,
        "provider": getattr(settings, "provider", "") if settings else "",
        "model_id": getattr(settings, "model_id", "") if settings else "",
        "temperature": getattr(settings, "temperature", None) if settings else None,
        "instruction_slug": getattr(prompt_config, "slug", "") or "",
        "raw_text": raw_text,
        "grounding_mode": grounding_mode,
    }
