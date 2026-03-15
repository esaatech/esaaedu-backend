"""
TutorX GCS storage helpers.

Used by views (content PUT, image delete) and by the lesson pre_delete signal
to delete TutorX images from Google Cloud Storage.
"""
import json
import logging
from pathlib import Path
from urllib.parse import urlparse, unquote

from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

# Placeholder for pending images (not yet uploaded); skip when cleaning up content
PENDING_IMAGE_PREFIX = "__pending__"


def file_path_from_tutorx_image_url(image_url: str) -> str | None:
    """
    Extract GCS storage path from a TutorX image URL.

    URL format: https://storage.googleapis.com/BUCKET_NAME/path/to/file
    Returns the path after the bucket name (e.g. tutorx-images/uuid-name.jpg).
    Returns None if the URL is empty, not a string, or does not look like a real URL.
    """
    if not image_url or not isinstance(image_url, str):
        return None
    url = image_url.strip()
    if not url or url.startswith(PENDING_IMAGE_PREFIX) or not url.startswith(("http://", "https://")):
        return None
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/", 1)
        if len(path_parts) > 1:
            file_path = unquote(path_parts[1])
        else:
            file_path = unquote(parsed.path.strip("/"))
        return file_path if file_path else None
    except Exception as e:
        logger.warning("Could not parse TutorX image URL %s: %s", image_url[:80], e)
        return None


def delete_image_and_thumbnail(file_path: str) -> tuple[bool, bool]:
    """
    Delete both the main image and its thumbnail from GCS.

    Args:
        file_path: The GCS path to the main image file (e.g. tutorx-images/uuid-name.jpg).

    Returns:
        Tuple of (main_image_deleted, thumbnail_deleted).
    """
    main_deleted = False
    thumb_deleted = False

    if default_storage.exists(file_path):
        try:
            default_storage.delete(file_path)
            main_deleted = True
            logger.info("Deleted main image from GCS: %s", file_path)
        except Exception as e:
            logger.error("Failed to delete main image %s: %s", file_path, e)

    try:
        path_obj = Path(file_path)
        filename = path_obj.name
        directory = path_obj.parent

        if "-" in filename and filename.endswith(".jpg"):
            name_without_ext = filename[:-4]
            parts = name_without_ext.rsplit("-", 1)
            if len(parts) == 2:
                uuid_part, base_name = parts[0], parts[1]
                thumb_filename = f"{uuid_part}-{base_name}-thumb.jpg"
                if str(directory).endswith("/images") or "images" in str(directory):
                    thumb_dir = directory / "thumbnails"
                else:
                    thumb_dir = directory / "thumbnails"
                thumb_path = str(thumb_dir / thumb_filename)

                if default_storage.exists(thumb_path):
                    try:
                        default_storage.delete(thumb_path)
                        thumb_deleted = True
                        logger.info("Deleted thumbnail from GCS: %s", thumb_path)
                    except Exception as e:
                        logger.error("Failed to delete thumbnail %s: %s", thumb_path, e)
    except Exception as e:
        logger.warning("Could not derive thumbnail path from %s: %s", file_path, e)

    return (main_deleted, thumb_deleted)


def _collect_image_urls_from_blocks(blocks: list) -> list[str]:
    """Recursively collect image block props.url from BlockNote blocks (and children)."""
    urls = []
    for b in blocks or []:
        if b.get("type") == "image" and isinstance(b.get("props"), dict):
            url_val = (b["props"].get("url") or "").strip()
            if url_val and url_val.startswith(("http://", "https://")):
                urls.append(url_val)
        if isinstance(b.get("children"), list):
            urls.extend(_collect_image_urls_from_blocks(b["children"]))
    return urls


def collect_image_urls_from_blocknote_string(content: str) -> list[str]:
    """
    Parse a BlockNote JSON string and return all image URLs (GCS) found in blocks.
    Used for interactive event prompt/explanation so we can diff and delete removed images.
    Returns empty list if content is not valid JSON or not a list of blocks.
    """
    if not content or not isinstance(content, str) or not content.strip():
        return []
    stripped = content.strip()
    if not stripped.startswith("["):
        return []
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return _collect_image_urls_from_blocks(data)


def collect_image_urls_from_event_payload(ev: dict) -> list[str]:
    """
    Collect all image URLs from an interactive event payload (prompt, explanation, etc.).
    For pop_quiz we only use questions[0] for prompt/explanation so we don't double-count
    stale top-level prompt (which can still contain removed images and would prevent GCS delete).
    """
    urls = []
    event_type = ev.get("type") or ev.get("event_type")
    is_pop_quiz = event_type == "pop_quiz"

    if is_pop_quiz and ev.get("questions"):
        first_q = (ev.get("questions") or [])[0]
        if isinstance(first_q, dict):
            for field in ("prompt", "question", "explanation"):
                val = first_q.get(field)
                if isinstance(val, str):
                    urls.extend(collect_image_urls_from_blocknote_string(val))
    else:
        for field in ("prompt", "explanation", "explanationYes", "explanation_yes", "explanationNo", "explanation_no", "model_answer", "modelAnswer"):
            val = ev.get(field)
            if isinstance(val, str):
                urls.extend(collect_image_urls_from_blocknote_string(val))
    return urls


def delete_tutorx_images_from_content(tutorx_content: str) -> None:
    """
    Parse TutorX BlockNote content JSON and delete every image file from GCS.

    Walks all blocks and children for type=='image', extracts props.url (GCS URLs),
    and calls delete_image_and_thumbnail for each. Skips __pending__ and non-http URLs.
    Logs and continues on per-URL errors so one failure does not block the rest.
    """
    if not tutorx_content or not tutorx_content.strip():
        return
    try:
        data = json.loads(tutorx_content)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Could not parse tutorx_content for image cleanup: %s", e)
        return
    if not isinstance(data, list):
        return
    urls = _collect_image_urls_from_blocks(data)
    seen = set()
    for image_url in urls:
        if image_url in seen:
            continue
        seen.add(image_url)
        file_path = file_path_from_tutorx_image_url(image_url)
        if not file_path:
            continue
        try:
            delete_image_and_thumbnail(file_path)
        except Exception as e:
            logger.warning("Failed to delete TutorX image from GCS %s: %s", image_url[:80], e)
