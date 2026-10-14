"""Create, run, and serialize teacher AI grading drafts."""
from __future__ import annotations

import logging
import uuid

from django.db import transaction

from ai_service.models import AIGradingJob
from ai_service.teacher_grading_queue import enqueue_teacher_grading_job, teacher_grading_uses_queue
from tutorx.services.grading_queue import (
    CloudTaskAlreadyExists,
    CloudTaskConfigError,
    CloudTaskEnqueueError,
)

logger = logging.getLogger(__name__)

IN_FLIGHT = (AIGradingJob.Status.PENDING, AIGradingJob.Status.RUNNING)


def serialize_grading_job(job: AIGradingJob) -> dict:
    return {
        "job_id": str(job.id),
        "kind": job.kind,
        "submission_id": str(job.submission_id),
        "status": job.status,
        "result": job.result_json if job.status == AIGradingJob.Status.COMPLETED else None,
        "error": job.error_message or "",
    }


def grading_job_for(kind: str, submission_id) -> AIGradingJob | None:
    return AIGradingJob.objects.filter(kind=kind, submission_id=submission_id).first()


def delete_grading_job(kind: str, submission_id) -> bool:
    deleted, _ = AIGradingJob.objects.filter(kind=kind, submission_id=submission_id).delete()
    return deleted > 0


def start_teacher_grading(*, teacher, kind: str, submission_id, questions, context) -> tuple[dict, int]:
    """
    One draft per submission. An in-flight draft is returned unchanged.
    Returns (payload, http_status).
    """
    token = uuid.uuid4().hex
    with transaction.atomic():
        job = (
            AIGradingJob.objects.select_for_update()
            .filter(kind=kind, submission_id=submission_id)
            .first()
        )
        if job is not None and job.status in IN_FLIGHT:
            return serialize_grading_job(job), 202
        if job is None:
            job = AIGradingJob(kind=kind, submission_id=submission_id, teacher=teacher)
        job.teacher = teacher
        job.status = AIGradingJob.Status.PENDING
        job.run_token = token
        job.request_payload = {
            "questions": questions,
            "context": context or {},
        }
        job.result_json = None
        job.error_message = ""
        job.save()

    try:
        if teacher_grading_uses_queue():
            try:
                enqueue_teacher_grading_job(job)
            except CloudTaskAlreadyExists:
                pass
            return serialize_grading_job(job), 202
    except (CloudTaskConfigError, CloudTaskEnqueueError) as exc:
        job.status = AIGradingJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        return serialize_grading_job(job), 503

    outcome = execute_teacher_grading_job(str(job.id), job.run_token)
    job.refresh_from_db()
    if outcome == "retry":
        job.status = AIGradingJob.Status.FAILED
        if not job.error_message:
            job.error_message = "Grading failed."
        job.save(update_fields=["status", "error_message", "updated_at"])
    return serialize_grading_job(job), 202


def execute_teacher_grading_job(job_id: str, run_token: str) -> str:
    """Returns skipped, completed, failed, or retry."""
    with transaction.atomic():
        try:
            job = AIGradingJob.objects.select_for_update().get(id=job_id)
        except AIGradingJob.DoesNotExist:
            return "skipped"
        if job.run_token != run_token or job.status not in IN_FLIGHT:
            return "skipped"
        job.status = AIGradingJob.Status.RUNNING
        job.save(update_fields=["status", "updated_at"])
        payload = dict(job.request_payload or {})
        kind = job.kind

    questions = payload.get("questions") or []
    context = payload.get("context") or None
    try:
        if kind == AIGradingJob.Kind.ASSESSMENT:
            from teacher.assessment_grading_helper import run_assessment_hybrid_grading

            result = run_assessment_hybrid_grading(questions, context)
        else:
            from teacher.ai_grading_helper import (
                ASSIGNMENT_GRADING_TEMPLATE,
                run_teacher_ai_grading_batch,
            )

            result = run_teacher_ai_grading_batch(
                questions,
                context,
                ASSIGNMENT_GRADING_TEMPLATE,
            )
        out = {
            "success": True,
            "result": {
                "grades": result.get("grades") or [],
                "total_score": result.get("total_score"),
                "total_possible": result.get("total_possible"),
            },
        }
    except Exception as exc:
        logger.exception("Teacher grading job %s failed", job_id)
        out = {"success": False, "error": str(exc), "error_code": "generation_failed"}

    with transaction.atomic():
        try:
            job = AIGradingJob.objects.select_for_update().get(id=job_id)
        except AIGradingJob.DoesNotExist:
            return "skipped"
        if job.run_token != run_token:
            return "skipped"
        if out.get("success"):
            job.status = AIGradingJob.Status.COMPLETED
            job.result_json = out.get("result") or {}
            job.error_message = ""
            job.save(update_fields=["status", "result_json", "error_message", "updated_at"])
            return "completed"
        message = out.get("error") or "Grading failed."
        if "validation_error" in message:
            job.status = AIGradingJob.Status.FAILED
            job.error_message = message
            job.save(update_fields=["status", "error_message", "updated_at"])
            return "failed"
        job.error_message = message
        job.status = AIGradingJob.Status.PENDING
        job.save(update_fields=["status", "error_message", "updated_at"])
        return "retry"
