"""Build pydantic-ai document parts from lesson material file URLs."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

GCS_HTTPS_PREFIX = "https://storage.googleapis.com/"


def normalize_storage_url(file_url: str) -> str:
    """
    Prefer gs:// for Vertex/Google Cloud document forwarding.

    https://storage.googleapis.com/bucket/path → gs://bucket/path
    """
    url = (file_url or "").strip()
    if not url:
        return ""
    if url.startswith(GCS_HTTPS_PREFIX):
        path = url[len(GCS_HTTPS_PREFIX) :].split("?", 1)[0].split("#", 1)[0]
        return f"gs://{path}"
    return url.split("?", 1)[0]


def build_document_media(
    documents: Optional[list[dict[str, Any]]],
) -> list[Any]:
    """
    Convert [{uri|url, mime_type, title?}, ...] into pydantic-ai DocumentUrl parts.

    Returns an empty list when documents is empty or DocumentUrl is unavailable.
    """
    if not documents:
        return []

    try:
        from pydantic_ai import DocumentUrl
    except ImportError:
        logger.warning("pydantic_ai.DocumentUrl unavailable; skipping document parts")
        return []

    media: list[Any] = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        raw = (doc.get("uri") or doc.get("url") or "").strip()
        if not raw:
            continue
        url = normalize_storage_url(raw)
        mime = (doc.get("mime_type") or doc.get("media_type") or "application/pdf").strip()
        try:
            media.append(DocumentUrl(url=url, media_type=mime))
        except Exception:
            logger.exception("Failed to build DocumentUrl for %s", url[:120])
    return media


def user_prompt_with_documents(
    text_prompt: str,
    documents: Optional[list[dict[str, Any]]] = None,
) -> Any:
    """
    Return a str prompt, or a multimodal list [text, DocumentUrl, ...] when docs exist.
    """
    media = build_document_media(documents)
    if not media:
        return text_prompt
    return [text_prompt, *media]
