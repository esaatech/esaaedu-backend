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

    if kind == AIGenerationJob.Kind.ASSESSMENT:
        out = _run_assessment_job(payload)
    elif kind == AIGenerationJob.Kind.QUIZ:
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


def _run_assessment_job(payload: dict) -> dict:
    from courses.models import Lesson, LessonMaterial

    from ai_service.assessment_sources import collect_lesson_source
    from ai_service.runners.assessment_generate import generate_assessment

    lesson = Lesson.objects.get(id=payload["lesson_id"])
    material_ids = payload.get("material_ids") or []
    materials = LessonMaterial.objects.filter(id__in=material_ids).prefetch_related("book_pages")
    source = collect_lesson_source(lesson, materials)
    if not source["has_source"]:
        return {
            "success": False,
            "error": "No content found in selected materials",
            "error_code": "validation_error",
        }
    counts = payload.get("counts") or {}
    return generate_assessment(
        lesson_contents=[
            {
                "lesson_title": source["lesson_title"],
                "lesson_order": source["lesson_order"],
                "content": source["content"],
            }
        ],
        documents=source["documents"],
        assessment_type=payload.get("assessment_type") or "test",
        total_questions=int(payload.get("total_questions") or 1),
        multiple_choice_count=int(counts.get("multiple_choice") or 0),
        true_false_count=int(counts.get("true_false") or 0),
        fill_blank_count=int(counts.get("fill_blank") or 0),
        short_answer_count=int(counts.get("short_answer") or 0),
        essay_count=int(counts.get("essay") or 0),
        code_count=int(counts.get("code") or 0),
        system_instruction=payload.get("system_instruction") or None,
        temperature=payload.get("temperature"),
    )


def assessment_jobs_for(assessment):
    return (
        AIGenerationJob.objects.filter(
            assessment=assessment,
            kind=AIGenerationJob.Kind.ASSESSMENT,
        )
        .select_related("lesson")
        .order_by("lesson__order", "lesson__created_at")
    )


def serialize_assessment_batch(jobs) -> dict:
    jobs = list(jobs)
    statuses = [job.status for job in jobs]
    in_flight = any(status in IN_FLIGHT for status in statuses)
    questions = []
    errors = []
    if not in_flight:
        for job in jobs:
            if job.status == AIGenerationJob.Status.COMPLETED:
                questions.extend((job.result_json or {}).get("questions") or [])
            elif job.status == AIGenerationJob.Status.FAILED:
                title = getattr(job.lesson, "title", "") or "A lesson"
                errors.append(job.error_message or f"{title} failed")
    if in_flight:
        overall = (
            "running"
            if any(status == AIGenerationJob.Status.RUNNING for status in statuses)
            else "pending"
        )
    elif questions:
        overall = "completed"
    else:
        overall = "failed"
    finished = sum(
        1
        for status in statuses
        if status in (AIGenerationJob.Status.COMPLETED, AIGenerationJob.Status.FAILED)
    )
    return {
        "jobs": [
            {
                "job_id": str(job.id),
                "lesson_id": str(job.lesson_id),
                "lesson_title": getattr(job.lesson, "title", ""),
                "status": job.status,
                "error": job.error_message or "",
            }
            for job in jobs
        ],
        "status": overall,
        "finished": finished,
        "total": len(jobs),
        "result": None if in_flight or not questions else {"questions": questions},
        "error": "" if in_flight else "; ".join(error for error in errors if error),
    }


def start_assessment_generation(*, assessment, teacher, lesson_plans: list[dict]) -> tuple[dict, int]:
    """
    One job per lesson. An in-flight set is returned unchanged.

    ``lesson_plans`` items: lesson, material_ids, total, counts,
    system_instruction, temperature, assessment_type.
    """
    with transaction.atomic():
        existing = list(
            AIGenerationJob.objects.select_for_update()
            .filter(assessment=assessment, kind=AIGenerationJob.Kind.ASSESSMENT)
            .select_related("lesson")
            .order_by("lesson__order", "lesson__created_at")
        )
        if any(job.status in IN_FLIGHT for job in existing):
            return serialize_assessment_batch(existing), 202
        if existing:
            AIGenerationJob.objects.filter(id__in=[job.id for job in existing]).delete()
        jobs = []
        for plan in lesson_plans:
            lesson = plan["lesson"]
            jobs.append(
                AIGenerationJob.objects.create(
                    lesson=lesson,
                    assessment=assessment,
                    teacher=teacher,
                    kind=AIGenerationJob.Kind.ASSESSMENT,
                    status=AIGenerationJob.Status.PENDING,
                    run_token=uuid.uuid4().hex,
                    request_payload={
                        "lesson_id": str(lesson.id),
                        "material_ids": list(plan.get("material_ids") or []),
                        "total_questions": int(plan["total"]),
                        "counts": plan["counts"],
                        "system_instruction": plan.get("system_instruction") or "",
                        "temperature": plan.get("temperature"),
                        "assessment_type": plan.get("assessment_type") or "test",
                    },
                )
            )

    try:
        if generation_uses_queue():
            failed = 0
            for job in jobs:
                try:
                    enqueue_generation_job(job)
                except CloudTaskAlreadyExists:
                    pass
                except (CloudTaskConfigError, CloudTaskEnqueueError) as exc:
                    failed += 1
                    job.status = AIGenerationJob.Status.FAILED
                    job.error_message = str(exc)
                    job.save(update_fields=["status", "error_message", "updated_at"])
            batch = serialize_assessment_batch(assessment_jobs_for(assessment))
            if failed and failed == len(jobs):
                return batch, 503
            return batch, 202
    except (CloudTaskConfigError, CloudTaskEnqueueError) as exc:
        for job in jobs:
            job.status = AIGenerationJob.Status.FAILED
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message", "updated_at"])
        return serialize_assessment_batch(assessment_jobs_for(assessment)), 503

    for job in jobs:
        outcome = execute_generation_job(str(job.id), job.run_token)
        if outcome == "retry":
            job.refresh_from_db()
            job.status = AIGenerationJob.Status.FAILED
            if not job.error_message:
                job.error_message = "Generation failed."
            job.save(update_fields=["status", "error_message", "updated_at"])
    return serialize_assessment_batch(assessment_jobs_for(assessment)), 202
