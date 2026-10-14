"""
Enqueue quiz, assignment, and assessment generation onto Cloud Tasks.

Uses its own queue, ai-lesson-generation, so a generate burst does not block
TutorX grading. The OIDC audience matches grading. The task URL is the
generation worker. When CLOUD_TASKS_QUEUE is unset, generation stays inline.
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

GENERATION_PATH = "/api/internal/ai/generate-lesson-questions/"
GENERATION_QUEUE_NAME = "ai-lesson-generation"


def generation_queue_name() -> str:
    """Queue for lesson question generation. Empty means run inline."""
    explicit = (getattr(settings, "CLOUD_TASKS_GENERATION_QUEUE", "") or "").strip()
    if explicit:
        return explicit
    if (getattr(settings, "CLOUD_TASKS_QUEUE", "") or "").strip():
        return GENERATION_QUEUE_NAME
    return ""


def generation_target_url() -> str:
    explicit = (getattr(settings, "CLOUD_TASKS_GENERATION_TARGET_URL", "") or "").strip()
    if explicit:
        return explicit
    grade_url = (getattr(settings, "CLOUD_TASKS_TARGET_URL", "") or "").strip()
    marker = "/api/internal/"
    if marker in grade_url:
        return grade_url.split(marker, 1)[0] + GENERATION_PATH
    return ""


def generation_uses_queue() -> bool:
    """
    False when Cloud Tasks is not configured (local development).
    Raises when the grading queue is set but no generation worker URL can be derived.
    """
    if not tutorx_grading_uses_queue():
        return False
    if not generation_target_url():
        raise CloudTaskConfigError(
            "Set CLOUD_TASKS_GENERATION_TARGET_URL for quiz and assignment generation."
        )
    return True


def enqueue_generation_job(job) -> str:
    """Create one Cloud Task for this run. A new run_token gets a new task name."""
    if not generation_uses_queue():
        raise CloudTaskConfigError("Cloud Tasks queue is not configured.")

    project = (
        (settings.CLOUD_TASKS_PROJECT or "").strip()
        or (getattr(settings, "GCS_PROJECT_ID", "") or "").strip()
    )
    location = (settings.CLOUD_TASKS_LOCATION or "us-central1").strip()
    queue = generation_queue_name()
    target = generation_target_url()
    service_account = settings.CLOUD_TASKS_SERVICE_ACCOUNT.strip()
    audience = (settings.CLOUD_TASKS_OIDC_AUDIENCE or settings.CLOUD_TASKS_TARGET_URL or target).strip()
    task_id = f"ai-gen-{job.id}-{job.run_token}"
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
        logger.exception("Cloud Tasks create request failed for generation job %s", job.id)
        raise CloudTaskEnqueueError("Failed to contact Cloud Tasks.") from exc

    if response.status_code == 409:
        logger.info("Cloud Task already exists for generation job %s (%s)", job.id, task_id)
        raise CloudTaskAlreadyExists(task_id)
    if response.status_code >= 400:
        detail = response.text[:500]
        logger.error(
            "Cloud Tasks create failed for generation job %s: %s %s",
            job.id,
            response.status_code,
            detail,
        )
        raise CloudTaskEnqueueError(f"Failed to enqueue generation ({response.status_code}).")

    logger.info("Enqueued generation task %s", task_id)
    return task_id
