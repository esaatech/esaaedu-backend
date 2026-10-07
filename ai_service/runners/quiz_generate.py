"""
Quiz generation runner — Admin playground + teacher AIGenerateQuizView.

All quiz generation (text + PDF/document URLs) goes through the AI Service catalog
via pydantic-ai (switchable model). Documents are attached as DocumentUrl parts.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.exceptions import AIServiceError, configuration_error
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.runners.document_parts import user_prompt_with_documents
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas_quiz_generate import (
    QuizGenerateOut,
    QuizQuestionOut,
    _option_texts,
)

logger = logging.getLogger(__name__)

SERVICE_SLUG = "quiz_generate"
PROMPT_SLUG_DEFAULT = "default"
SETUP_COMMAND = "setup_quiz_generate"

DEFAULT_INSTRUCTIONS = """You are an expert quiz creator specializing in educational content.
Generate comprehensive quiz questions that test understanding of the lesson material.
Create a mix of multiple choice and true/false questions with clear correct answers.

Guidelines:
- Questions should test understanding, not just memorization
- Multiple choice questions should have 4 clear options
- True/false questions should be unambiguous
- Include helpful explanations for each question
- Ensure questions cover different aspects of the lesson content
- Questions should be appropriate for the target age group
- For every multiple_choice question you MUST put at least 4 options in content.options
  as plain strings, and set content.correct_answer to the exact matching option text
- Example: content={"options": ["Red","Blue","Green","Yellow"], "correct_answer": "Blue"}
- Never leave content.options empty"""


def require_default_prompt_config():
    prompt_config = get_default_prompt_config(SERVICE_SLUG)
    if prompt_config is not None:
        return prompt_config
    raise configuration_error(
        f"No default AI prompt for {SERVICE_SLUG}. "
        f"Run: python manage.py setup_ai_models && python manage.py {SETUP_COMMAND}"
    )


def generate_quiz(
    *,
    lesson_title: str,
    lesson_description: str = "",
    content: str = "",
    documents: Optional[list[dict[str, Any]]] = None,
    total_questions: int = 10,
    multiple_choice_count: int = 7,
    true_false_count: int = 3,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
    prompt_config=None,
) -> dict[str, Any]:
    """
    Generate a quiz from lesson text and/or document URLs (PDF, etc.).

    ``documents`` items: {uri|url, mime_type?, title?}

    Returns:
      { success, error, error_code, result: {title, description, questions},
        provider, model_id, temperature, instruction_slug, raw_text, latency_ms }
    """
    endpoint = f"ai_service.runners.{SERVICE_SLUG}"
    title = (lesson_title or "").strip()
    if not title:
        return _fail("lesson_title is required", error_code="validation_error")

    text = (content or "").strip()
    docs = [d for d in (documents or []) if isinstance(d, dict) and (d.get("uri") or d.get("url"))]
    if not text and not docs:
        return _fail(
            "content or documents is required",
            error_code="validation_error",
        )

    mc, tf, total = _normalize_counts(
        total_questions, multiple_choice_count, true_false_count
    )

    try:
        if prompt_config is None:
            prompt_config = require_default_prompt_config()
    except AIServiceError as exc:
        logger.warning("quiz_generate: missing default prompt: %s", exc)
        ai_exc = notify_and_classify(
            exc, context="quiz_generate:prompt_config", endpoint=endpoint
        )
        return _fail(ai_exc.log_message, error_code=ai_exc.error_code)

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("quiz_generate: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc, context="quiz_generate:resolve_model", endpoint=endpoint
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("quiz_generate: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc, context="quiz_generate:resolve_model", endpoint=endpoint
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )

    run_temperature = (
        float(temperature) if temperature is not None else settings.temperature
    )
    log_run_model(
        service=SERVICE_SLUG,
        provider=settings.provider,
        model_id=settings.model_id,
        temperature=run_temperature,
        extra=f"total={total} mc={mc} tf={tf} docs={len(docs)}",
    )

    instructions = (
        (system_instruction or "").strip()
        or (getattr(prompt_config, "system_prompt", None) or "").strip()
        or DEFAULT_INSTRUCTIONS
    )
    type_requirement = _type_requirement(mc, tf)
    if type_requirement and type_requirement.lower() not in instructions.lower():
        instructions = f"{instructions}\n{type_requirement}"

    text_prompt = _build_user_prompt(
        lesson_title=title,
        lesson_description=lesson_description or "",
        content=text,
        documents=docs,
        total_questions=total,
        multiple_choice_count=mc,
        true_false_count=tf,
    )
    user_prompt = user_prompt_with_documents(text_prompt, docs)

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc, context="quiz_generate:import", endpoint=endpoint
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=QuizGenerateOut,
        instructions=instructions,
        retries={"output": 3},
        model_settings=request_model_settings(temperature=run_temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(agent, user_prompt)
        quiz: QuizGenerateOut = result.output
        payload = _normalize_quiz(quiz, fallback_title=f"Quiz: {title}")
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=True,
            latency_ms=latency_ms,
            extra=f"questions={len(payload['questions'])}",
        )
        return {
            "success": True,
            "error": "",
            "error_code": "",
            "result": payload,
            "provider": settings.provider,
            "model_id": settings.model_id,
            "temperature": run_temperature,
            "instruction_slug": getattr(prompt_config, "slug", "") or "",
            "raw_text": str(payload)[:20000],
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("quiz_generate: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=f"quiz_generate provider={settings.provider} model={settings.model_id}",
            endpoint=endpoint,
        )
        log_run_finished(
            service=SERVICE_SLUG,
            provider=settings.provider,
            model_id=settings.model_id,
            success=False,
            latency_ms=latency_ms,
            extra=f"error_code={ai_exc.error_code}",
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            temperature=run_temperature,
            raw_text=str(exc),
            error_code=ai_exc.error_code,
        )


def _normalize_counts(total: int, mc: int, tf: int) -> tuple[int, int, int]:
    total = max(1, int(total or 10))
    mc = max(0, int(mc or 0))
    tf = max(0, int(tf or 0))
    if mc + tf != total:
        if mc + tf > total and (mc + tf) > 0:
            ratio = total / (mc + tf)
            mc = int(mc * ratio)
            tf = total - mc
        else:
            tf = total - mc
            if tf < 0:
                mc = total
                tf = 0
    return mc, tf, total


def _type_requirement(mc: int, tf: int) -> str:
    parts = []
    if mc > 0:
        parts.append(f"{mc} multiple choice question{'s' if mc != 1 else ''}")
    if tf > 0:
        parts.append(f"{tf} true/false question{'s' if tf != 1 else ''}")
    if not parts:
        return ""
    return (
        f"Create {', and '.join(parts)} with clear correct answers and helpful explanations."
    )


def _build_user_prompt(
    *,
    lesson_title: str,
    lesson_description: str,
    content: str,
    documents: list[dict[str, Any]],
    total_questions: int,
    multiple_choice_count: int,
    true_false_count: int,
) -> str:
    desc = f"Lesson Description: {lesson_description}\n" if lesson_description.strip() else ""
    if content.strip():
        content_section = f"Content:\n{content[:50000]}\n\n"
    elif documents:
        titles = ", ".join(
            (d.get("title") or "document").strip() or "document" for d in documents
        )
        content_section = (
            f"Content: See attached document(s): {titles}. "
            f"Base the quiz only on the attached materials.\n\n"
        )
    else:
        content_section = "Content: (none)\n\n"
    return (
        f"Generate a quiz for the following lesson.\n\n"
        f"Lesson Title: {lesson_title}\n"
        f"{desc}\n"
        f"{content_section}"
        f"Generate exactly {total_questions} questions:\n"
        f"- Exactly {multiple_choice_count} multiple choice questions\n"
        f"- Exactly {true_false_count} true/false questions\n\n"
        f"For each multiple_choice question, content.options MUST be an array of "
        f"at least 2 plain strings (prefer 4), and content.correct_answer MUST "
        f"exactly match one of those option strings.\n\n"
        f"Follow the system instruction, including any teacher instructions, "
        f"when choosing what the quiz assesses."
    )


def _normalize_quiz(quiz: QuizGenerateOut, *, fallback_title: str) -> dict[str, Any]:
    validated: list[dict[str, Any]] = []
    for q in quiz.questions:
        item = _normalize_question(q)
        if item is not None:
            validated.append(item)

    if not validated and quiz.questions:
        sample = quiz.questions[0].model_dump()
        logger.error(
            "quiz_generate: all questions failed validation sample=%s",
            str(sample)[:2000],
        )
        raise ValueError(
            "AI generated quiz questions but none passed validation "
            "(multiple choice questions need at least 2 options)"
        )

    return {
        "title": quiz.title or fallback_title,
        "description": quiz.description or "",
        "questions": validated,
    }


def _normalize_question(q: QuizQuestionOut) -> Optional[dict[str, Any]]:
    raw_content = q.content if isinstance(q.content, dict) else {}
    content = dict(raw_content)
    qtype = q.type or "multiple_choice"
    item = {
        "question_text": q.question_text or "",
        "type": qtype,
        "points": int(q.points or 1),
        "content": content,
        "explanation": q.explanation or "",
    }

    if qtype == "multiple_choice":
        normalized_options = _option_texts(content.get("options"))
        if len(normalized_options) < 2:
            # Alternate keys some models use
            for key in ("choices", "answers", "answer_choices"):
                normalized_options = _option_texts(content.get(key))
                if len(normalized_options) >= 2:
                    break
        if len(normalized_options) < 2:
            normalized_options = _option_texts(q.options)
        content["options"] = normalized_options

        correct = content.get("correct_answer") or q.correct_answer or ""
        content["correct_answer"] = (
            correct.strip() if isinstance(correct, str) else str(correct)
        )
        item["content"] = content
        if len(normalized_options) < 2:
            logger.warning(
                "Skipping multiple_choice question with fewer than 2 options: %s raw=%s",
                item["question_text"][:80],
                str(q.model_dump())[:800],
            )
            return None

    elif qtype == "true_false":
        correct = content.get("correct_answer") or q.correct_answer or "true"
        content["correct_answer"] = str(correct).lower()
        item["content"] = content

    return item


def _fail(
    error: str,
    *,
    prompt_config=None,
    settings=None,
    temperature: Optional[float] = None,
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
        "temperature": (
            temperature
            if temperature is not None
            else (getattr(settings, "temperature", None) if settings else None)
        ),
        "instruction_slug": getattr(prompt_config, "slug", "") or "",
        "raw_text": raw_text,
    }
