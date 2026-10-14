"""
Assessment generation runner — Admin playground + teacher assessment generate view.

Tests and exams go through the AI Service catalog via pydantic-ai (switchable model).
Gemini receives PDFs as DocumentUrl. DeepSeek and OpenAI receive extracted PDF text.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ai_service.alerts import log_run_finished, log_run_model, notify_and_classify
from ai_service.exceptions import AIServiceError, configuration_error
from ai_service.gateway import AIServiceGatewayError, resolve_model
from ai_service.prompt_utils import get_default_prompt_config
from ai_service.runners.document_parts import (
    DocumentGroundingError,
    user_prompt_with_documents,
)
from ai_service.runners.run_helpers import request_model_settings, run_agent_sync
from ai_service.schemas_assessment_generate import (
    AssessmentGenerateOut,
    AssessmentQuestionOut,
)

logger = logging.getLogger(__name__)

SERVICE_SLUG = "assessment_generate"
PROMPT_SLUG_DEFAULT = "default"
SETUP_COMMAND = "setup_assessment_generate"

DEFAULT_INSTRUCTIONS = """You are an expert assessment creator specializing in educational tests and exams.
Generate questions that evaluate understanding of the supplied lesson materials.

Guidelines:
- Every question needs a non-empty explanation
- multiple_choice: at least 4 plain-string options and correct_answer equal to one option
- true_false: correct_answer is exactly true or false
- fill_blank: correct_answers is one string per blank, in order
- essay and short_answer: put the full model answer in correct_answer
- code: set language (python unless the material says otherwise), write clear instructions,
  and keep starter_code to at most 20 lines with no blank-line padding
- Base every question on the supplied materials
"""


def require_default_prompt_config():
    prompt_config = get_default_prompt_config(SERVICE_SLUG)
    if prompt_config is not None:
        return prompt_config
    raise configuration_error(
        f"No default AI prompt for {SERVICE_SLUG}. "
        f"Run: python manage.py setup_ai_models && python manage.py {SETUP_COMMAND}"
    )


def generate_assessment(
    *,
    lesson_contents: Optional[list[dict[str, Any]]] = None,
    documents: Optional[list[dict[str, Any]]] = None,
    assessment_type: str = "test",
    total_questions: int = 10,
    multiple_choice_count: int = 0,
    true_false_count: int = 0,
    fill_blank_count: int = 0,
    short_answer_count: int = 0,
    essay_count: int = 0,
    code_count: int = 0,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
    prompt_config=None,
) -> dict[str, Any]:
    """
    Generate test or exam questions from lesson text and/or document URLs.

    ``documents`` items: {uri|url, mime_type?, title?}
    """
    endpoint = f"ai_service.runners.{SERVICE_SLUG}"
    lessons = [item for item in (lesson_contents or []) if isinstance(item, dict)]
    docs = [
        doc
        for doc in (documents or [])
        if isinstance(doc, dict) and (doc.get("uri") or doc.get("url"))
    ]
    text = "\n\n".join(
        (item.get("content") or "").strip()
        for item in lessons
        if (item.get("content") or "").strip()
    ).strip()
    if not text and not docs and not lessons:
        return _fail(
            "lesson content or documents is required",
            error_code="validation_error",
        )

    counts = _normalize_counts(
        total_questions,
        multiple_choice_count,
        true_false_count,
        fill_blank_count,
        short_answer_count,
        essay_count,
        code_count,
    )

    try:
        if prompt_config is None:
            prompt_config = require_default_prompt_config()
    except AIServiceError as exc:
        logger.warning("assessment_generate: missing default prompt: %s", exc)
        ai_exc = notify_and_classify(
            exc, context="assessment_generate:prompt_config", endpoint=endpoint
        )
        return _fail(ai_exc.log_message, error_code=ai_exc.error_code)

    try:
        model, settings = resolve_model(prompt_config=prompt_config)
    except AIServiceGatewayError as exc:
        logger.warning("assessment_generate: resolve_model failed: %s", exc)
        ai_exc = notify_and_classify(
            exc, context="assessment_generate:resolve_model", endpoint=endpoint
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            error_code=ai_exc.error_code,
        )
    except Exception as exc:
        logger.exception("assessment_generate: unexpected resolve failure")
        ai_exc = notify_and_classify(
            exc, context="assessment_generate:resolve_model", endpoint=endpoint
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
        extra=(
            f"type={assessment_type} total={counts['total']} "
            f"lessons={len(lessons)} docs={len(docs)}"
        ),
    )

    instructions = (
        (system_instruction or "").strip()
        or (getattr(prompt_config, "system_prompt", None) or "").strip()
        or DEFAULT_INSTRUCTIONS
    )
    text_prompt = _build_user_prompt(
        lessons=lessons,
        documents=docs,
        assessment_type=assessment_type or "test",
        counts=counts,
    )
    try:
        user_prompt = user_prompt_with_documents(
            text_prompt, docs, provider=settings.provider
        )
    except DocumentGroundingError as exc:
        return _fail(
            str(exc),
            prompt_config=prompt_config,
            settings=settings,
            error_code="validation_error",
        )

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        ai_exc = notify_and_classify(
            exc, context="assessment_generate:import", endpoint=endpoint
        )
        return _fail(
            ai_exc.log_message,
            prompt_config=prompt_config,
            settings=settings,
            error_code=ai_exc.error_code,
        )

    agent = Agent(
        model,
        output_type=AssessmentGenerateOut,
        instructions=instructions,
        retries={"output": 2},
        model_settings=request_model_settings(temperature=run_temperature),
    )

    started = time.perf_counter()
    try:
        result = run_agent_sync(agent, user_prompt)
        assessment: AssessmentGenerateOut = result.output
        payload = _normalize_assessment(
            assessment,
            fallback_title=f"{(assessment_type or 'test').capitalize()}",
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
        logger.exception("assessment_generate: agent run failed")
        ai_exc = notify_and_classify(
            exc,
            context=(
                f"assessment_generate provider={settings.provider} "
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
    total: int,
    multiple_choice: int,
    true_false: int,
    fill_blank: int,
    short_answer: int,
    essay: int,
    code: int,
) -> dict[str, int]:
    total = max(1, int(total or 10))
    counts = {
        "multiple_choice": max(0, int(multiple_choice or 0)),
        "true_false": max(0, int(true_false or 0)),
        "fill_blank": max(0, int(fill_blank or 0)),
        "short_answer": max(0, int(short_answer or 0)),
        "essay": max(0, int(essay or 0)),
        "code": max(0, int(code or 0)),
    }
    specified = sum(counts.values())
    if specified == total:
        counts["total"] = total
        return counts
    if specified > total and specified > 0:
        ratio = total / specified
        keys = list(counts)
        for key in keys[:-1]:
            counts[key] = int(counts[key] * ratio)
        counts[keys[-1]] = total - sum(counts[key] for key in keys[:-1])
        if counts[keys[-1]] < 0:
            counts[keys[-1]] = 0
    else:
        active = [key for key, value in counts.items() if value > 0] or ["multiple_choice"]
        remainder = total - specified
        per_type = remainder // len(active)
        extra = remainder % len(active)
        for key in active:
            counts[key] += per_type + (1 if extra > 0 else 0)
            extra = max(0, extra - 1)
    counts["total"] = total
    return counts


def _build_user_prompt(
    *,
    lessons: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    assessment_type: str,
    counts: dict[str, int],
) -> str:
    sections = []
    for item in lessons:
        title = (item.get("lesson_title") or "Untitled Lesson").strip()
        order = item.get("lesson_order", 0)
        body = (item.get("content") or "").strip()
        block = f"=== Lesson {order}: {title} ==="
        if body:
            block += f"\n{body}"
        sections.append(block)
    content_section = "\n\n".join(sections) if sections else "No lesson text was extracted."
    doc_lines = [
        f"- {(doc.get('title') or 'document').strip()}"
        for doc in documents
    ]
    type_lines = []
    labels = {
        "multiple_choice": "multiple choice",
        "true_false": "true/false",
        "fill_blank": "fill-in-the-blank",
        "short_answer": "short answer",
        "essay": "essay",
        "code": "code",
    }
    for key, label in labels.items():
        if counts.get(key, 0) > 0:
            type_lines.append(f"- Exactly {counts[key]} {label} question(s)")
    coverage = ""
    if len(lessons) > 1:
        coverage = (
            "Cover every lesson at least once before giving any lesson a second question. "
            "After that, put extra questions on the later lessons first "
            "(higher lesson order is more recent).\n"
        )
    return (
        f"Generate a {assessment_type} from these lesson materials.\n\n"
        f"{content_section}\n\n"
        + (
            "Attached documents:\n" + "\n".join(doc_lines) + "\n\n"
            if doc_lines
            else ""
        )
        + f"Generate exactly {counts['total']} questions:\n"
        + "\n".join(type_lines)
        + "\n\n"
        + coverage
        + "For code questions, starter_code must be a short scaffold of at most 20 lines. "
        "Do not pad it with blank lines.\n"
    )


def _normalize_assessment(
    assessment: AssessmentGenerateOut, *, fallback_title: str
) -> dict[str, Any]:
    return {
        "title": assessment.title or fallback_title,
        "description": assessment.description or "",
        "questions": [_normalize_question(q) for q in assessment.questions],
    }


def _normalize_question(q: AssessmentQuestionOut) -> dict[str, Any]:
    content: dict[str, Any] = {}
    if q.type == "multiple_choice":
        content = {"options": list(q.options), "correct_answer": q.correct_answer}
    elif q.type == "true_false":
        content = {"correct_answer": q.correct_answer}
    elif q.type == "fill_blank":
        content = {
            "blanks": list(q.blanks),
            "correct_answers": list(q.correct_answers),
        }
    elif q.type == "essay":
        content = {
            "correct_answer": q.correct_answer,
            "instructions": q.instructions or "",
        }
    elif q.type == "short_answer":
        content = {
            "correct_answer": q.correct_answer,
            "accept_variations": True,
        }
    elif q.type == "code":
        content = {
            "language": q.language or "python",
            "instructions": q.instructions,
            "starter_code": q.starter_code or "",
        }
    return {
        "question_text": q.question_text,
        "type": q.type,
        "points": int(q.points or 1),
        "content": content,
        "explanation": q.explanation,
    }


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
