"""Build pydantic-ai document parts from lesson material file URLs."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

GCS_HTTPS_PREFIX = "https://storage.googleapis.com/"
GS_PREFIX = "gs://"


def normalize_storage_url(file_url: str, *, provider: str = "gemini") -> str:
    """
    Normalize document URLs for the active provider.

    - gemini (Vertex): prefer gs:// so Google Cloud can read via IAM
    - openai / deepseek: http(s) only — convert gs:// back to public GCS HTTPS
    """
    url = (file_url or "").strip()
    if not url:
        return ""

    provider = (provider or "gemini").strip().lower()
    wants_gs = provider == "gemini"

    if wants_gs:
        if url.startswith(GCS_HTTPS_PREFIX):
            path = url[len(GCS_HTTPS_PREFIX) :].split("?", 1)[0].split("#", 1)[0]
            return f"{GS_PREFIX}{path}"
        return url.split("?", 1)[0]

    # Non-Gemini providers cannot fetch gs://
    if url.startswith(GS_PREFIX):
        path = url[len(GS_PREFIX) :].split("?", 1)[0].split("#", 1)[0]
        return f"{GCS_HTTPS_PREFIX}{path}"
    return url.split("?", 1)[0]


def build_document_media(
    documents: Optional[list[dict[str, Any]]],
    *,
    provider: str = "gemini",
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
        url = normalize_storage_url(raw, provider=provider)
        mime = (doc.get("mime_type") or doc.get("media_type") or "application/pdf").strip()
        try:
            # Non-Gemini: force local download of https URLs (provider can't use gs:// IAM).
            kwargs: dict[str, Any] = {"url": url, "media_type": mime}
            if (provider or "").strip().lower() != "gemini":
                try:
                    media.append(DocumentUrl(**kwargs, force_download=True))
                    continue
                except TypeError:
                    pass
            media.append(DocumentUrl(**kwargs))
        except Exception:
            logger.exception("Failed to build DocumentUrl for %s", url[:120])
    return media


def user_prompt_with_documents(
    text_prompt: str,
    documents: Optional[list[dict[str, Any]]] = None,
    *,
    provider: str = "gemini",
) -> Any:
    """
    Return a str prompt, or a multimodal list [text, DocumentUrl, ...] when docs exist.
    """
    media = build_document_media(documents, provider=provider)
    if not media:
        return text_prompt
    return [text_prompt, *media]
