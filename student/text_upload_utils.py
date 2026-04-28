"""
Upload plain text (.txt) files to Google Cloud Storage — mirrors css_upload_utils.py.

Paths use prefix text-files/ and content-type text/plain; charset=utf-8.
"""
import uuid
import re
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

try:
    from google.cloud import storage
    from google.oauth2 import service_account
    GCS_CLIENT_AVAILABLE = True
except ImportError:
    GCS_CLIENT_AVAILABLE = False
    logger.warning("google-cloud-storage not available for text uploads")


def sanitize_filename(filename):
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '-', filename)
    sanitized = re.sub(r'-+', '-', sanitized)
    sanitized = sanitized.strip('.-')
    if sanitized.startswith('.'):
        sanitized = 'file' + sanitized
    if not sanitized:
        sanitized = 'document'
    if not sanitized.lower().endswith('.txt'):
        sanitized = sanitized + '.txt'
    return sanitized.lower()


def _default_storage_is_gcs() -> bool:
    """
    Return True when Django default_storage points to GoogleCloudStorage.
    """
    try:
        storage_cls = default_storage.__class__
        return (
            storage_cls.__name__ == 'GoogleCloudStorage'
            or 'storages.backends.gcloud' in storage_cls.__module__
        )
    except Exception:
        return False


def upload_text_to_gcp(text_content, title=None, snippet_id=None):
    """
    Upload plain text to GCS at text-files/{snippet_id or uuid}-{sanitized-title}.txt
    Mirrors upload_css_to_gcp.
    """
    if not text_content or not str(text_content).strip():
        logger.warning("Attempted to upload empty text content")
        return None, None

    if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
        logger.error("Google Cloud Storage is not configured. GS_BUCKET_NAME not set.")
        return None, None

    try:
        if snippet_id:
            unique_id = str(snippet_id)
        else:
            unique_id = str(uuid.uuid4())

        if title and title.strip():
            sanitized_title = sanitize_filename(title.strip())
            if len(sanitized_title) > 50:
                sanitized_title = sanitized_title[:50]
            filename = f"{unique_id}-{sanitized_title}"
        else:
            filename = f"{unique_id}-document.txt"

        if not filename.endswith('.txt'):
            filename = filename + '.txt'

        storage_path = f"text-files/{filename}"

        txt_file = ContentFile(text_content.encode('utf-8'))
        txt_file.name = filename

        if snippet_id and GCS_CLIENT_AVAILABLE:
            try:
                if hasattr(settings, 'GS_CREDENTIALS') and settings.GS_CREDENTIALS:
                    if isinstance(settings.GS_CREDENTIALS, str):
                        client = storage.Client.from_service_account_json(
                            settings.GS_CREDENTIALS,
                            project=settings.GS_PROJECT_ID
                        )
                    else:
                        client = storage.Client(
                            credentials=settings.GS_CREDENTIALS,
                            project=settings.GS_PROJECT_ID
                        )
                else:
                    client = storage.Client(project=settings.GS_PROJECT_ID)

                bucket = client.bucket(settings.GS_BUCKET_NAME)
                blob = bucket.blob(storage_path)
                blob.cache_control = 'no-cache, no-store, must-revalidate'
                blob.content_type = 'text/plain; charset=utf-8'

                txt_file.seek(0)
                blob.upload_from_file(txt_file, content_type='text/plain; charset=utf-8')
                blob.make_public()

                saved_path = storage_path
                file_url = blob.public_url
            except Exception as e:
                if not _default_storage_is_gcs():
                    logger.error(
                        "Text upload failed via GCS client and default_storage is not GCS; "
                        "refusing local fallback to avoid false success",
                        exc_info=True,
                    )
                    return None, None
                logger.warning(f"GCS client upload failed for text, using default_storage: {e}")
                txt_file.seek(0)
                saved_path = default_storage.save(storage_path, txt_file)
                file_url = default_storage.url(saved_path)
                if not file_url.startswith('http'):
                    file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
        else:
            if not _default_storage_is_gcs():
                logger.error(
                    "GCS client unavailable for text upload and default_storage is not GCS; "
                    "refusing local fallback to avoid false success"
                )
                return None, None
            saved_path = default_storage.save(storage_path, txt_file)
            file_url = default_storage.url(saved_path)
            if not file_url.startswith('http'):
                file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"

        logger.info(f"Text file uploaded to GCS: {saved_path}")
        return file_url, saved_path

    except Exception as e:
        logger.error(f"Error uploading text file to GCS: {e}", exc_info=True)
        return None, None


def _storage_path_from_text_file_url(text_file_url):
    """
    Extract storage path (text-files/...) from a stored URL.
    Mirrors CSS URL parsing in update_css_in_gcp / delete_css_from_gcp.
    """
    if not text_file_url:
        return None
    if 'storage.googleapis.com' in text_file_url:
        parts = text_file_url.split('/')
        try:
            idx = parts.index('text-files')
            return '/'.join(parts[idx:])
        except ValueError:
            tail = text_file_url.split('/text-files/')[-1]
            if tail:
                return f"text-files/{tail}"
            logger.warning(f"Could not extract path from text file URL: {text_file_url}")
            return None
    return text_file_url.lstrip('/')


def update_text_in_gcp(text_file_url, text_content):
    """
    Overwrite existing text at the given URL path.
    Same strategy as update_css_in_gcp: GCS client first, then default_storage fallback.
    """
    if not text_file_url:
        logger.warning("Attempted to update text file without URL")
        return None, None
    if not text_content or not text_content.strip():
        logger.warning("Attempted to update text file with empty content")
        return None, None
    if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
        logger.error("Google Cloud Storage is not configured. GS_BUCKET_NAME not set.")
        return None, None

    file_path = _storage_path_from_text_file_url(text_file_url)
    if not file_path:
        return None, None

    txt_file = ContentFile(text_content.encode('utf-8'))
    txt_file.name = file_path.split('/')[-1]

    def _save_via_default_storage():
        if not _default_storage_is_gcs():
            logger.error(
                "Text update fallback blocked: default_storage is not GCS; "
                "refusing local fallback to avoid false success"
            )
            return None, None
        txt_file.seek(0)
        saved_path = default_storage.save(file_path, txt_file)
        file_url = default_storage.url(saved_path)
        if not file_url.startswith('http'):
            file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
        return file_url, saved_path

    if GCS_CLIENT_AVAILABLE:
        try:
            if hasattr(settings, 'GS_CREDENTIALS') and settings.GS_CREDENTIALS:
                if isinstance(settings.GS_CREDENTIALS, str):
                    client = storage.Client.from_service_account_json(
                        settings.GS_CREDENTIALS,
                        project=settings.GS_PROJECT_ID
                    )
                else:
                    client = storage.Client(
                        credentials=settings.GS_CREDENTIALS,
                        project=settings.GS_PROJECT_ID
                    )
            else:
                client = storage.Client(project=settings.GS_PROJECT_ID)

            bucket = client.bucket(settings.GS_BUCKET_NAME)
            blob = bucket.blob(file_path)
            blob.cache_control = 'no-cache, no-store, must-revalidate'
            blob.content_type = 'text/plain; charset=utf-8'
            txt_file.seek(0)
            blob.upload_from_file(txt_file, content_type='text/plain; charset=utf-8')
            blob.make_public()
            logger.info(f"Text file updated successfully in GCS: {file_path}")
            return blob.public_url, file_path
        except Exception as e:
            logger.warning(f"GCS client text update failed, falling back to default_storage: {e}")

    try:
        return _save_via_default_storage()
    except Exception as e:
        logger.error(f"Error updating text file in storage: {e}", exc_info=True)
        return None, None


def delete_text_from_gcp(text_file_url):
    """Delete text file from GCS by URL. Mirrors delete_css_from_gcp."""
    if not text_file_url:
        return False

    try:
        file_path = _storage_path_from_text_file_url(text_file_url)
        if not file_path:
            return False

        if default_storage.exists(file_path):
            default_storage.delete(file_path)
            logger.info(f"Text file deleted from GCS: {file_path}")
            return True
        logger.warning(f"Text file not found in GCS: {file_path}")
        return False

    except Exception as e:
        logger.error(f"Error deleting text file from GCS: {e}", exc_info=True)
        return False
