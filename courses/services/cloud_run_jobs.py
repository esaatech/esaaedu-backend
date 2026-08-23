"""
Enqueue Cloud Run Job executions (lesson video HLS conversion).

Uses the Run Admin API with Application Default Credentials so we do not
require the google-cloud-run client library.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class CloudRunJobError(Exception):
    """Raised when a Cloud Run Job cannot be started."""


def enqueue_lesson_video_convert(upload_id: str) -> dict[str, Any]:
    """
    Start ``LESSON_VIDEO_CLOUD_RUN_JOB_NAME`` with args:
    manage.py convert_lesson_video_upload <upload_id>
    """
    job_name = getattr(settings, 'LESSON_VIDEO_CLOUD_RUN_JOB_NAME', '') or ''
    region = getattr(settings, 'LESSON_VIDEO_CLOUD_RUN_JOB_REGION', '') or 'us-central1'
    project = (
        getattr(settings, 'LESSON_VIDEO_CLOUD_RUN_PROJECT', None)
        or getattr(settings, 'GCS_PROJECT_ID', None)
        or getattr(settings, 'GS_PROJECT_ID', None)
    )

    if not job_name:
        raise CloudRunJobError(
            'LESSON_VIDEO_CLOUD_RUN_JOB_NAME is not configured on this service.'
        )
    if not project:
        raise CloudRunJobError(
            'Cloud project id is not configured (LESSON_VIDEO_CLOUD_RUN_PROJECT / GCS_PROJECT_ID).'
        )

    resource = (
        f'projects/{project}/locations/{region}/jobs/{job_name}'
    )
    url = f'https://run.googleapis.com/v2/{resource}:run'

    body = {
        'overrides': {
            'containerOverrides': [
                {
                    # Replaces Job container args; keep manage.py + command + upload id.
                    'args': [
                        'manage.py',
                        'convert_lesson_video_upload',
                        str(upload_id),
                    ],
                }
            ],
        },
    }

    try:
        import google.auth
        import google.auth.transport.requests
        import httpx
    except ImportError as e:
        raise CloudRunJobError(
            'google-auth and httpx are required to enqueue Cloud Run Jobs.'
        ) from e

    try:
        credentials, _ = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)
        token = credentials.token
    except Exception as e:
        logger.exception('Failed to obtain credentials for Cloud Run Jobs API')
        raise CloudRunJobError(
            'Could not authenticate to start the video conversion job.'
        ) from e

    try:
        response = httpx.post(
            url,
            json=body,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            timeout=30.0,
        )
    except Exception as e:
        logger.exception('Cloud Run Jobs API request failed for %s', upload_id)
        raise CloudRunJobError(
            'Failed to contact Cloud Run to start video conversion.'
        ) from e

    if response.status_code >= 400:
        detail = response.text[:500]
        logger.error(
            'Cloud Run Jobs API error for %s: %s %s',
            upload_id,
            response.status_code,
            detail,
        )
        raise CloudRunJobError(
            f'Failed to start conversion job ({response.status_code}). '
            'Ensure this service account can run the Cloud Run Job.'
        )

    data = {}
    try:
        data = response.json()
    except Exception:
        pass

    logger.info(
        'Enqueued Cloud Run Job %s for lesson video upload %s (name=%s)',
        job_name,
        upload_id,
        data.get('name') or data.get('metadata', {}).get('name'),
    )
    return data
