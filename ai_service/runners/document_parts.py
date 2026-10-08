"""Build pydantic-ai document parts from lesson material file URLs."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Optional

logger = logging.getLogger(__name__)

GCS_HTTPS_PREFIX = "https://storage.googleapis.com/"
GS_PREFIX = "gs://"
MAX_EXTRACTED_CHARS = 80_000
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


class DocumentGroundingError(Exception):
    """Raised when a non-Gemini provider cannot use a document as text."""


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


def _bucket_and_blob(file_url: str) -> Optional[tuple[str, str]]:
    url = (file_url or "").strip()
    if url.startswith(GS_PREFIX):
        rest = url[len(GS_PREFIX) :].split("?", 1)[0].split("#", 1)[0]
    elif url.startswith(GCS_HTTPS_PREFIX):
        rest = url[len(GCS_HTTPS_PREFIX) :].split("?", 1)[0].split("#", 1)[0]
    else:
        return None
    bucket, _, blob = rest.partition("/")
    if not bucket or not blob:
        return None
    return bucket, blob


def _download_bytes(file_url: str) -> bytes:
    located = _bucket_and_blob(file_url)
    if located:
        bucket_name, blob_name = located
        from google.cloud import storage

        blob = storage.Client().bucket(bucket_name).blob(blob_name)
        data = blob.download_as_bytes()
    else:
        import httpx

        response = httpx.get(file_url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        data = response.content
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise DocumentGroundingError(
            "Document is too large to extract as text for this model"
        )
    return data


def _extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(part.strip() for part in pages if part and part.strip()).strip()


def extract_documents_text(documents: Optional[list[dict[str, Any]]]) -> str:
    """
    Download PDFs (and plain-text files) and return their text.

    Used for providers that cannot read a GCS document URL (DeepSeek, OpenAI).
    """
    if not documents:
        return ""

    chunks: list[str] = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        raw = (doc.get("uri") or doc.get("url") or "").strip()
        if not raw:
            continue
        title = (doc.get("title") or "document").strip() or "document"
        mime = (doc.get("mime_type") or doc.get("media_type") or "application/pdf").lower()
        try:
            data = _download_bytes(raw)
        except DocumentGroundingError:
            raise
        except Exception as exc:
            logger.exception("Failed to download document %s", raw[:160])
            raise DocumentGroundingError(
                f"Could not download '{title}' to extract text for this model"
            ) from exc

        if "pdf" in mime or raw.lower().split("?", 1)[0].endswith(".pdf"):
            text = _extract_pdf_text(data)
        elif mime.startswith("text/") or raw.lower().split("?", 1)[0].endswith(".txt"):
            text = data.decode("utf-8", errors="replace").strip()
        else:
            raise DocumentGroundingError(
                f"'{title}' is not a PDF or text file. Use Gemini to generate from this document."
            )
        if not text:
            raise DocumentGroundingError(
                f"No text could be extracted from '{title}'. "
                "Image-only PDFs need Gemini."
            )
        chunks.append(f"=== {title} ===\n{text}")

    combined = "\n\n".join(chunks).strip()
    if len(combined) > MAX_EXTRACTED_CHARS:
        combined = combined[:MAX_EXTRACTED_CHARS]
        logger.info(
            "document text truncated to %s chars for non-Gemini generation",
            MAX_EXTRACTED_CHARS,
        )
    return combined


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
        url = normalize_storage_url(raw, provider="gemini")
        mime = (doc.get("mime_type") or doc.get("media_type") or "application/pdf").strip()
        try:
            media.append(DocumentUrl(url=url, media_type=mime))
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
    Gemini: multimodal prompt with DocumentUrl (gs://).
    Other providers: plain text prompt with extracted PDF/text content.
    """
    provider_name = (provider or "gemini").strip().lower()
    if provider_name != "gemini":
        extracted = extract_documents_text(documents)
        if not extracted:
            return text_prompt
        logger.info(
            "document text extracted for provider=%s chars=%s",
            provider_name,
            len(extracted),
        )
        return (
            f"{text_prompt.rstrip()}\n\n"
            "Document text (use this as the lesson content; there is no file attachment):\n"
            f"{extracted}"
        )

    media = build_document_media(documents, provider=provider_name)
    if not media:
        return text_prompt
    return [text_prompt, *media]
