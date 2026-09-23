"""
Enqueue TutorX assignment grading onto Cloud Tasks.

When CLOUD_TASKS_QUEUE is unset, the student submit view grades inline.
When it is set, submit returns immediately and Cloud Tasks calls the worker.
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class CloudTaskConfigError(Exception):
    """Queue name is set, but the rest of the Cloud Tasks config is missing."""


class CloudTaskEnqueueError(Exception):
    """Cloud Tasks rejected the create-task call."""


class CloudTaskAlreadyExists(Exception):
    """This submit already has a task. Treat as success."""


def grading_run_token(submission) -> str:
    """Stable per-submit id. A new submit changes submitted_at and therefore the task name."""
    submitted_at = submission.submitted_at
    if submitted_at is None:
        raise CloudTaskEnqueueError('Submission has no submitted_at.')
    if timezone.is_naive(submitted_at):
        submitted_at = timezone.make_aware(submitted_at, dt_timezone.utc)
    return submitted_at.astimezone(dt_timezone.utc).strftime('%Y%m%d%H%M%S%f')


def tutorx_grading_uses_queue() -> bool:
    """
    False when the queue is not configured (local development).
    Raises when the queue name is set but the worker URL, project, or service account is missing.
    """
    queue = (getattr(settings, 'CLOUD_TASKS_QUEUE', '') or '').strip()
    if not queue:
        return False

    project = (
        (getattr(settings, 'CLOUD_TASKS_PROJECT', '') or '').strip()
        or (getattr(settings, 'GCS_PROJECT_ID', '') or '').strip()
    )
    target = (getattr(settings, 'CLOUD_TASKS_TARGET_URL', '') or '').strip()
    service_account = (getattr(settings, 'CLOUD_TASKS_SERVICE_ACCOUNT', '') or '').strip()
    missing = []
    if not project:
        missing.append('CLOUD_TASKS_PROJECT')
    if not target:
        missing.append('CLOUD_TASKS_TARGET_URL')
    if not service_account:
        missing.append('CLOUD_TASKS_SERVICE_ACCOUNT')
    if missing:
        raise CloudTaskConfigError(
            'TutorX grading queue is incomplete. Set ' + ', '.join(missing) + '.'
        )
    return True


def enqueue_tutorx_grade(submission) -> str:
    """
    Create one Cloud Task for this submit.
    Task id is tutorx-grade-{submission_id}-{submitted_at} so a double-click cannot grade twice.
    """
    if not tutorx_grading_uses_queue():
        raise CloudTaskConfigError('Cloud Tasks queue is not configured.')

    project = (
        (settings.CLOUD_TASKS_PROJECT or '').strip()
        or (getattr(settings, 'GCS_PROJECT_ID', '') or '').strip()
    )
    location = (settings.CLOUD_TASKS_LOCATION or 'us-central1').strip()
    queue = settings.CLOUD_TASKS_QUEUE.strip()
    target = settings.CLOUD_TASKS_TARGET_URL.strip()
    service_account = settings.CLOUD_TASKS_SERVICE_ACCOUNT.strip()
    audience = (settings.CLOUD_TASKS_OIDC_AUDIENCE or target).strip()
    token = grading_run_token(submission)
    task_id = f'tutorx-grade-{submission.id}-{token}'
    parent = f'projects/{project}/locations/{location}/queues/{queue}'
    task_name = f'{parent}/tasks/{task_id}'
    payload = {
        'submission_id': str(submission.id),
        'submitted_at': token,
    }
    deadline = int(getattr(settings, 'CLOUD_TASKS_DISPATCH_DEADLINE_SECONDS', 1200) or 1200)
    body = {
        'task': {
            'name': task_name,
            'dispatchDeadline': f'{deadline}s',
            'httpRequest': {
                'httpMethod': 'POST',
                'url': target,
                'headers': {'Content-Type': 'application/json'},
                'body': base64.b64encode(json.dumps(payload).encode('utf-8')).decode('ascii'),
                'oidcToken': {
                    'serviceAccountEmail': service_account,
                    'audience': audience,
                },
            },
        }
    }

    try:
        import google.auth
        import google.auth.transport.requests
        import httpx
    except ImportError as exc:
        raise CloudTaskEnqueueError('google-auth and httpx are required to enqueue Cloud Tasks.') from exc

    try:
        credentials, _ = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        credentials.refresh(google.auth.transport.requests.Request())
        access_token = credentials.token
    except Exception as exc:
        logger.exception('Failed to obtain credentials for Cloud Tasks')
        raise CloudTaskEnqueueError('Could not authenticate to Cloud Tasks.') from exc

    url = f'https://cloudtasks.googleapis.com/v2/{parent}/tasks'
    try:
        response = httpx.post(
            url,
            json=body,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            timeout=30.0,
        )
    except Exception as exc:
        logger.exception('Cloud Tasks create request failed for submission %s', submission.id)
        raise CloudTaskEnqueueError('Failed to contact Cloud Tasks.') from exc

    if response.status_code == 409:
        logger.info('Cloud Task already exists for submission %s (%s)', submission.id, task_id)
        raise CloudTaskAlreadyExists(task_id)
    if response.status_code >= 400:
        detail = response.text[:500]
        logger.error(
            'Cloud Tasks create failed for submission %s: %s %s',
            submission.id,
            response.status_code,
            detail,
        )
        raise CloudTaskEnqueueError(
            f'Failed to enqueue grading ({response.status_code}).'
        )

    logger.info('Enqueued TutorX grade task %s', task_id)
    return task_id


def verify_cloud_tasks_request(request) -> tuple[bool, str, int]:
    """
    Confirm the caller is the configured Cloud Tasks service account.
    Returns (ok, error_message, retry_count). retry_count is 0 on the first attempt.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False, 'Missing Cloud Tasks OIDC token.', 0

    service_account = (getattr(settings, 'CLOUD_TASKS_SERVICE_ACCOUNT', '') or '').strip()
    audience = (
        (getattr(settings, 'CLOUD_TASKS_OIDC_AUDIENCE', '') or '').strip()
        or (getattr(settings, 'CLOUD_TASKS_TARGET_URL', '') or '').strip()
    )
    if not service_account or not audience:
        return False, 'Cloud Tasks worker auth is not configured.', 0

    token = auth_header[7:].strip()
    try:
        import google.auth.transport.requests
        from google.oauth2 import id_token

        info = id_token.verify_oauth2_token(
            token,
            google.auth.transport.requests.Request(),
            audience=audience,
        )
    except Exception:
        logger.exception('Cloud Tasks OIDC verification failed')
        return False, 'Invalid Cloud Tasks OIDC token.', 0

    email = info.get('email')
    if email != service_account or not info.get('email_verified', False):
        return False, 'Unexpected Cloud Tasks identity.', 0

    retry_header = request.headers.get('X-CloudTasks-TaskRetryCount', '0')
    try:
        retry_count = max(int(retry_header), 0)
    except (TypeError, ValueError):
        retry_count = 0
    return True, '', retry_count


def is_last_grade_attempt(retry_count: int) -> bool:
    max_attempts = int(getattr(settings, 'CLOUD_TASKS_MAX_ATTEMPTS', 3) or 3)
    return retry_count + 1 >= max_attempts
