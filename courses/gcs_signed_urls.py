"""
Generate V4 signed URLs for direct browser → GCS uploads.

Used by lesson video staged uploads so large files bypass Cloud Run's
HTTP/1 ~32 MiB request body limit.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from google.cloud import storage

    GCS_CLIENT_AVAILABLE = True
except ImportError:
    GCS_CLIENT_AVAILABLE = False
    storage = None


class SignedUrlError(Exception):
    """Raised when a signed upload URL cannot be created."""


def _get_gcs_client():
    if not GCS_CLIENT_AVAILABLE:
        return None
    if not getattr(settings, 'GS_BUCKET_NAME', None):
        return None
    try:
        if getattr(settings, 'GS_CREDENTIALS', None):
            creds = settings.GS_CREDENTIALS
            if isinstance(creds, str):
                return storage.Client.from_service_account_json(
                    creds, project=getattr(settings, 'GS_PROJECT_ID', None)
                )
            return storage.Client(
                credentials=creds, project=getattr(settings, 'GS_PROJECT_ID', None)
            )
        return storage.Client(project=getattr(settings, 'GS_PROJECT_ID', None))
    except Exception as e:
        logger.warning('Could not create GCS client for signed URLs: %s', e)
        return None


def _sign_blob_put(blob, content_type: str, expires_seconds: int) -> str:
    """
    Sign a PUT URL.

    Service-account JSON keys can sign locally. On Cloud Run (ADC / metadata
    credentials) we must pass service_account_email + access_token so IAM
    SignBlob is used.
    """
    expiration = timedelta(seconds=expires_seconds)
    try:
        return blob.generate_signed_url(
            version='v4',
            expiration=expiration,
            method='PUT',
            content_type=content_type,
        )
    except AttributeError:
        # Credentials without a private key (typical on Cloud Run)
        pass
    except Exception as first_err:
        logger.info('Direct signed URL failed, trying IAM SignBlob: %s', first_err)

    try:
        import google.auth
        from google.auth.transport import requests as google_auth_requests

        credentials, _ = google.auth.default()
        auth_request = google_auth_requests.Request()
        credentials.refresh(auth_request)
        email = getattr(credentials, 'service_account_email', None)
        if not email:
            raise SignedUrlError(
                'Signing credentials have no service_account_email. '
                'Use a service account key or grant the runtime SA signBlob.'
            )
        return blob.generate_signed_url(
            version='v4',
            expiration=expiration,
            method='PUT',
            content_type=content_type,
            service_account_email=email,
            access_token=credentials.token,
        )
    except SignedUrlError:
        raise
    except Exception as e:
        logger.exception('IAM SignBlob signed URL failed')
        raise SignedUrlError(
            'Failed to create upload URL. Ensure the service account can sign blobs '
            '(roles/iam.serviceAccountTokenCreator on itself).'
        ) from e


def generate_signed_put_url(
    object_name: str,
    content_type: str,
    *,
    expires_seconds: int = 3600,
) -> dict[str, Any]:
    """
    Return a V4 signed PUT URL for uploading ``object_name``.

    Returns:
        {
          "upload_url": str,
          "bucket": str,
          "object_name": str,
          "headers": {"Content-Type": content_type},
          "expires_seconds": int,
        }
    """
    bucket_name = getattr(settings, 'GS_BUCKET_NAME', None)
    if not bucket_name:
        raise SignedUrlError('GCS is not configured (GS_BUCKET_NAME not set).')

    client = _get_gcs_client()
    if client is None:
        raise SignedUrlError('GCS client is not available.')

    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        url = _sign_blob_put(blob, content_type, expires_seconds)
    except SignedUrlError:
        raise
    except Exception as e:
        logger.exception('Failed to generate signed PUT URL for %s', object_name)
        raise SignedUrlError(
            'Failed to create upload URL. Ensure the service account can sign blobs.'
        ) from e

    return {
        'upload_url': url,
        'bucket': bucket_name,
        'object_name': object_name,
        'headers': {'Content-Type': content_type},
        'expires_seconds': expires_seconds,
    }


def gcs_object_exists(object_name: str) -> bool:
    client = _get_gcs_client()
    bucket_name = getattr(settings, 'GS_BUCKET_NAME', None)
    if client is None or not bucket_name:
        return False
    bucket = client.bucket(bucket_name)
    return bucket.blob(object_name).exists()


def delete_gcs_object(object_name: str) -> None:
    client = _get_gcs_client()
    bucket_name = getattr(settings, 'GS_BUCKET_NAME', None)
    if client is None or not bucket_name or not object_name:
        return
    try:
        client.bucket(bucket_name).blob(object_name).delete()
    except Exception as e:
        logger.warning('Failed to delete GCS object %s: %s', object_name, e)


def download_gcs_object_to_path(object_name: str, local_path: str) -> None:
    client = _get_gcs_client()
    bucket_name = getattr(settings, 'GS_BUCKET_NAME', None)
    if client is None or not bucket_name:
        raise SignedUrlError('GCS is not configured.')
    blob = client.bucket(bucket_name).blob(object_name)
    if not blob.exists():
        raise SignedUrlError(f'Object not found in storage: {object_name}')
    blob.download_to_filename(local_path)
