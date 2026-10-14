"""
Enqueue teacher AI grading onto the grading Cloud Tasks queue.

Uses tutorx-assignment-grading, not the lesson-generation queue. When
CLOUD_TASKS_QUEUE is unset, grading stays inline.
"""
from __future__ import annotations

import base64
import json
import logging

from django.conf import settings

from tutorx.services.grading_queue import (
    CloudTaskAlreadyExists,
    CloudTaskConfigError,
    CloudTaskEnqueueError,
    tutorx_grading_uses_queue,
)

logger = logging.getLogger(__name__)

GRADING_PATH = "/api/internal/ai/grade-teacher-submission/"


def teacher_grading_target_url() -> str:
    explicit = (getattr(settings, "CLOUD_TASKS_TEACHER_GRADING_TARGET_URL", "") or "").strip()
    if explicit:
        return explicit
    grade_url = (getattr(settings, "CLOUD_TASKS_TARGET_URL", "") or "").strip()
    marker = "/api/internal/"
    if marker in grade_url:
        return grade_url.split(marker, 1)[0] + GRADING_PATH
    return ""


def teacher_grading_uses_queue() -> bool:
    if not tutorx_grading_uses_queue():
        return False
    if not teacher_grading_target_url():
        raise CloudTaskConfigError(
            "Set CLOUD_TASKS_TARGET_URL so teacher grading can reach its worker."
        )
    return True


def enqueue_teacher_grading_job(job) -> str:
    if not teacher_grading_uses_queue():
        raise CloudTaskConfigError("Cloud Tasks queue is not configured.")

    project = (
        (settings.CLOUD_TASKS_PROJECT or "").strip()
        or (getattr(settings, "GCS_PROJECT_ID", "") or "").strip()
    )
    location = (settings.CLOUD_TASKS_LOCATION or "us-central1").strip()
    queue = settings.CLOUD_TASKS_QUEUE.strip()
    target = teacher_grading_target_url()
    service_account = settings.CLOUD_TASKS_SERVICE_ACCOUNT.strip()
    audience = (settings.CLOUD_TASKS_OIDC_AUDIENCE or settings.CLOUD_TASKS_TARGET_URL or target).strip()
    task_id = f"ai-grade-{job.id}-{job.run_token}"
    parent = f"projects/{project}/locations/{location}/queues/{queue}"
    task_name = f"{parent}/tasks/{task_id}"
    payload = {"job_id": str(job.id), "run_token": job.run_token}
    deadline = int(getattr(settings, "CLOUD_TASKS_DISPATCH_DEADLINE_SECONDS", 1200) or 1200)
    body = {
        "task": {
            "name": task_name,
            "dispatchDeadline": f"{deadline}s",
            "httpRequest": {
                "httpMethod": "POST",
                "url": target,
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii"),
                "oidcToken": {
                    "serviceAccountEmail": service_account,
                    "audience": audience,
                },
            },
        }
    }

    try:
        import google.auth
        import google.auth.transport.requests
        import httpx
    except ImportError as exc:
        raise CloudTaskEnqueueError("google-auth and httpx are required to enqueue Cloud Tasks.") from exc

    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        access_token = credentials.token
    except Exception as exc:
        logger.exception("Failed to obtain credentials for Cloud Tasks")
        raise CloudTaskEnqueueError("Could not authenticate to Cloud Tasks.") from exc

    url = f"https://cloudtasks.googleapis.com/v2/{parent}/tasks"
    try:
        response = httpx.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    except Exception as exc:
        logger.exception("Cloud Tasks create request failed for grading job %s", job.id)
        raise CloudTaskEnqueueError("Failed to contact Cloud Tasks.") from exc

    if response.status_code == 409:
        logger.info("Cloud Task already exists for grading job %s (%s)", job.id, task_id)
        raise CloudTaskAlreadyExists(task_id)
    if response.status_code >= 400:
        detail = response.text[:500]
        logger.error(
            "Cloud Tasks create failed for grading job %s: %s %s",
            job.id,
            response.status_code,
            detail,
        )
        raise CloudTaskEnqueueError(f"Failed to enqueue grading ({response.status_code}).")

    logger.info("Enqueued teacher grading task %s", task_id)
    return task_id
