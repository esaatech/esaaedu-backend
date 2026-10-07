"""
Assignment generation runner — Admin playground + teacher AIGenerateAssignmentView.

All assignment generation (text + PDF/document URLs) goes through the AI Service
catalog via pydantic-ai (switchable model). Documents are attached as DocumentUrl.
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
from ai_service.schemas_assignment_generate import (
    AssignmentGenerateOut,
    AssignmentQuestionOut,
)

logger = logging.getLogger(__name__)

SERVICE_SLUG = "assignment_generate"
PROMPT_SLUG_DEFAULT = "default"
SETUP_COMMAND = "setup_assignment_generate"

DEFAULT_INSTRUCTIONS = """You are an expert assignment creator specializing in educational content.
Generate comprehensive assignment questions that require students to demonstrate understanding and application of lesson material.
Create a mix of essay questions, fill-in-the-blank, and short answer questions with clear requirements.

Guidelines:
- Essay questions should require critical thinking and application
- Fill-in-the-blank questions should test key concepts
- Short answer questions should be specific and answerable
- For essay questions: put the detailed model answer in the explanation field ONLY; do not include a rubric field in content
- Ensure questions align with learning objectives
- Questions should be appropriate for the target age group"""


def require_default_prompt_config():
    prompt_config = get_default_prompt_config(SERVICE_SLUG)
    if prompt_config is not None:
        return prompt_config
    raise configuration_error(
        f"No default AI prompt for {SERVICE_SLUG}. "
        f"Run: python manage.py setup_ai_models && python manage.py {SETUP_COMMAND}"
    )


def generate_assignment(
    *,
    lesson_title: str,
    lesson_description: str = "",
    content: str = "",
    documents: Optional[list[dict[str, Any]]] = None,
    total_questions: int = 5,
    essay_count: int = 2,
    fill_blank_count: int = 3,
    short_answer_count: int = 0,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
    prompt_config=None,
) -> dict[str, Any]:
    """
    Generate an assignment from lesson text and/or document URLs (PDF, etc.).

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

    essay, fill, short, total = _normalize_counts(
        total_questions, essay_count, fill_blank_count, short_answer_count
    )

    try:
        if prompt_config is None:
            prompt_config = require_default_prompt_config()
    except AIServiceError as exc:
        logger.warning("assignment_generate: missing default prompt: %s", exc)
        ai_exc = notify_and_classify(
            exc, context="assignment_generate:prompt_config", endpoint=endpoint
        )
        return _fail(ai_exc.log_message, error_code=ai_exc.error_code)

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("assignment_generate: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc, context="assignment_generate:resolve_model", endpoint=endpoint
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("assignment_generate: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc, context="assignment_generate:resolve_model", endpoint=endpoint
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
        extra=f"total={total} essay={essay} fill={fill} short={short} docs={len(docs)}",
    )

    instructions = (
        (system_instruction or "").strip()
        or (getattr(prompt_config, "system_prompt", None) or "").strip()
        or DEFAULT_INSTRUCTIONS
    )
    type_requirement = _type_requirement(essay, fill, short)
    if type_requirement and type_requirement.lower() not in instructions.lower():
        instructions = f"{instructions}\n{type_requirement}"

    text_prompt = _build_user_prompt(
        lesson_title=title,
        lesson_description=lesson_description or "",
        content=text,
        documents=docs,
        total_questions=total,
        essay_count=essay,
        fill_blank_count=fill,
        short_answer_count=short,
    )
    user_prompt = user_prompt_with_documents(
        text_prompt, docs, provider=settings.provider
    )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc, context="assignment_generate:import", endpoint=endpoint
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=AssignmentGenerateOut,
        instructions=instructions,
        retries={"output": 2},
        model_settings=request_model_settings(temperature=run_temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(agent, user_prompt)
        assignment: AssignmentGenerateOut = result.output
        payload = _normalize_assignment(
            assignment, fallback_title=f"Assignment: {title}"
        )
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
        logger.exception("assignment_generate: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=(
                f"assignment_generate provider={settings.provider} "
                f"model={settings.model_id}"
            ),
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


def _normalize_counts(
    total: int, essay: int, fill: int, short: int
) -> tuple[int, int, int, int]:
    total = max(1, int(total or 5))
    essay = max(0, int(essay or 0))
    fill = max(0, int(fill or 0))
    short = max(0, int(short or 0))
    typed = essay + fill + short
    if typed != total:
        # Prefer essay+fill when short is 0 (legacy UI default)
        if short == 0:
            if essay + fill > total and (essay + fill) > 0:
                ratio = total / (essay + fill)
                essay = int(essay * ratio)
                fill = total - essay
            else:
                fill = total - essay
                if fill < 0:
                    essay = total
                    fill = 0
        else:
            # Scale all three proportionally
            if typed > 0:
                ratio = total / typed
                essay = int(essay * ratio)
                fill = int(fill * ratio)
                short = total - essay - fill
                if short < 0:
                    short = 0
                    fill = max(0, total - essay)
    return essay, fill, short, total


def _type_requirement(essay: int, fill: int, short: int) -> str:
    parts = []
    if essay > 0:
        parts.append(f"{essay} essay question{'s' if essay != 1 else ''}")
    if fill > 0:
        parts.append(
            f"{fill} fill-in-the-blank question{'s' if fill != 1 else ''}"
        )
    if short > 0:
        parts.append(f"{short} short answer question{'s' if short != 1 else ''}")
    if not parts:
        return ""
    return (
        f"Create {', and '.join(parts)} with clear requirements, "
        f"helpful explanations, and grading guidance where applicable."
    )


def _build_user_prompt(
    *,
    lesson_title: str,
    lesson_description: str,
    content: str,
    documents: list[dict[str, Any]],
    total_questions: int,
    essay_count: int,
    fill_blank_count: int,
    short_answer_count: int,
) -> str:
    desc = f"Lesson Description: {lesson_description}\n" if lesson_description.strip() else ""
    if content.strip():
        content_block = f"Content:\n{content[:50000]}"
    elif documents:
        titles = ", ".join(
            (d.get("title") or "document").strip() or "document" for d in documents
        )
        content_block = (
            f"Content: See attached document(s): {titles}. "
            f"Base the assignment only on the attached materials."
        )
    else:
        content_block = "Content: (none)"
    lines = [
        "Generate a comprehensive assignment for the following lesson:",
        "",
        f"Lesson Title: {lesson_title}",
        desc.rstrip(),
        "",
        content_block,
        "",
        (
            f"Generate exactly {total_questions} assignment questions that require "
            f"students to demonstrate understanding and application of the lesson content:"
        ),
        f"- Exactly {essay_count} essay questions",
        f"- Exactly {fill_blank_count} fill-in-the-blank questions",
    ]
    if short_answer_count > 0:
        lines.append(f"- Exactly {short_answer_count} short answer questions")
    lines.extend(
        [
            "",
            "CRITICAL INSTRUCTIONS FOR ESSAY QUESTIONS:",
            "- Put a detailed model answer in the explanation field ONLY.",
            "- DO NOT include a rubric field in content.",
            "- Optionally include content.instructions for students.",
            "",
            "For fill-in-the-blank questions: provide clear blanks and correct answers.",
            "Each question should have clear requirements and helpful explanations.",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def _normalize_assignment(
    assignment: AssignmentGenerateOut, *, fallback_title: str
) -> dict[str, Any]:
    validated = [_normalize_question(q) for q in assignment.questions]
    return {
        "title": assignment.title or fallback_title,
        "description": assignment.description or "",
        "questions": validated,
    }


def _normalize_question(q: AssignmentQuestionOut) -> dict[str, Any]:
    content = dict(q.content) if isinstance(q.content, dict) else {}
    qtype = q.type or "essay"
    item = {
        "question_text": q.question_text or "",
        "type": qtype,
        "points": int(q.points or 10),
        "content": content,
        "explanation": q.explanation or "",
    }

    if qtype == "fill_blank":
        content.setdefault("blanks", [])
        content.setdefault("correct_answers", {})
    elif qtype == "essay":
        if "rubric" in content:
            logger.warning(
                "Removing rubric field from essay question — should not be included"
            )
            del content["rubric"]
        content.setdefault("instructions", "")
    elif qtype == "short_answer":
        content.setdefault("correct_answer", "")
        content.setdefault("accept_variations", True)

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
