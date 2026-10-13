"""Create, run, and serialize quiz/assignment generation jobs."""
from __future__ import annotations

import logging
import uuid

from django.db import transaction

from ai_service.generation_queue import enqueue_generation_job, generation_uses_queue
from ai_service.models import AIGenerationJob
from ai_service.runners.assignment_generate import generate_assignment
from ai_service.runners.quiz_generate import generate_quiz
from tutorx.services.grading_queue import (
    CloudTaskAlreadyExists,
    CloudTaskConfigError,
    CloudTaskEnqueueError,
)

logger = logging.getLogger(__name__)

IN_FLIGHT = (AIGenerationJob.Status.PENDING, AIGenerationJob.Status.RUNNING)


def serialize_generation_job(job: AIGenerationJob) -> dict:
    return {
        "job_id": str(job.id),
        "lesson_id": str(job.lesson_id),
        "kind": job.kind,
        "status": job.status,
        "result": job.result_json if job.status == AIGenerationJob.Status.COMPLETED else None,
        "error": job.error_message or "",
    }


def claim_generation_job(*, lesson, teacher, kind: str, generation_kwargs: dict):
    """
    One row per lesson and kind.

    A pending or running job is returned as-is so a second click does not
    start another draft. A completed or failed row is reused for the new run.
    Returns (job, should_start).
    """
    token = uuid.uuid4().hex
    with transaction.atomic():
        job = (
            AIGenerationJob.objects.select_for_update()
            .filter(lesson=lesson, kind=kind)
            .first()
        )
        if job is not None and job.status in IN_FLIGHT:
            return job, False
        if job is None:
            job = AIGenerationJob(
                lesson=lesson,
                teacher=teacher,
                kind=kind,
            )
        job.teacher = teacher
        job.status = AIGenerationJob.Status.PENDING
        job.run_token = token
        job.request_payload = generation_kwargs
        job.result_json = None
        job.error_message = ""
        job.save()
    return job, True


def start_lesson_generation(*, lesson, teacher, kind: str, generation_kwargs: dict) -> tuple[dict, int]:
    """
    Persist the draft and either enqueue Cloud Tasks or run inline.
    Returns (payload, http_status).
    """
    job, should_start = claim_generation_job(
        lesson=lesson,
        teacher=teacher,
        kind=kind,
        generation_kwargs=generation_kwargs,
    )
    if not should_start:
        return serialize_generation_job(job), 202

    try:
        if generation_uses_queue():
            try:
                enqueue_generation_job(job)
            except CloudTaskAlreadyExists:
                pass
            return serialize_generation_job(job), 202
    except (CloudTaskConfigError, CloudTaskEnqueueError) as exc:
        job.status = AIGenerationJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        payload = serialize_generation_job(job)
        return payload, 503

    outcome = execute_generation_job(str(job.id), job.run_token)
    job.refresh_from_db()
    if outcome == "retry":
        job.status = AIGenerationJob.Status.FAILED
        if not job.error_message:
            job.error_message = "Generation failed."
        job.save(update_fields=["status", "error_message", "updated_at"])
    return serialize_generation_job(job), 202


def execute_generation_job(job_id: str, run_token: str) -> str:
    """
    Run the stored generator.

    Returns skipped, completed, failed, or retry.
    A mismatched run_token means a newer Generate replaced this attempt.
    """
    with transaction.atomic():
        try:
            job = AIGenerationJob.objects.select_for_update().get(id=job_id)
        except AIGenerationJob.DoesNotExist:
            return "skipped"
        if job.run_token != run_token or job.status not in IN_FLIGHT:
            return "skipped"
        job.status = AIGenerationJob.Status.RUNNING
        job.save(update_fields=["status", "updated_at"])
        payload = dict(job.request_payload or {})
        kind = job.kind

    if kind == AIGenerationJob.Kind.QUIZ:
        out = generate_quiz(
            lesson_title=payload.get("lesson_title") or "",
            lesson_description=payload.get("lesson_description") or "",
            content=payload.get("content") or "",
            documents=payload.get("documents") or None,
            total_questions=int(payload.get("total_questions") or 10),
            multiple_choice_count=int(payload.get("multiple_choice_count") or 0),
            true_false_count=int(payload.get("true_false_count") or 0),
            system_instruction=payload.get("system_instruction") or None,
            temperature=payload.get("temperature"),
        )
    else:
        out = generate_assignment(
            lesson_title=payload.get("lesson_title") or "",
            lesson_description=payload.get("lesson_description") or "",
            content=payload.get("content") or "",
            documents=payload.get("documents") or None,
            total_questions=int(payload.get("total_questions") or 5),
            essay_count=int(payload.get("essay_count") or 0),
            fill_blank_count=int(payload.get("fill_blank_count") or 0),
            short_answer_count=int(payload.get("short_answer_count") or 0),
            system_instruction=payload.get("system_instruction") or None,
            temperature=payload.get("temperature"),
        )

    with transaction.atomic():
        try:
            job = AIGenerationJob.objects.select_for_update().get(id=job_id)
        except AIGenerationJob.DoesNotExist:
            return "skipped"
        if job.run_token != run_token:
            return "skipped"
        if out.get("success"):
            job.status = AIGenerationJob.Status.COMPLETED
            job.result_json = out.get("result") or {}
            job.error_message = ""
            job.save(update_fields=["status", "result_json", "error_message", "updated_at"])
            return "completed"
        error_code = out.get("error_code") or "generation_failed"
        message = out.get("error") or "Generation failed."
        if error_code == "validation_error":
            job.status = AIGenerationJob.Status.FAILED
            job.error_message = message
            job.save(update_fields=["status", "error_message", "updated_at"])
            return "failed"
        job.error_message = message
        job.status = AIGenerationJob.Status.PENDING
        job.save(update_fields=["status", "error_message", "updated_at"])
        return "retry"
