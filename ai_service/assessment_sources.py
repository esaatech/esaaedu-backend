"""Turn one lesson's selected materials into text and document refs for the runner."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MIME_BY_EXTENSION = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "rtf": "application/rtf",
}


def collect_lesson_source(lesson, materials) -> dict:
    """
    ``materials`` belong to ``lesson``.

    Documents stay as URL refs. Video and audio transcripts are read here so
    each Cloud Task does that work for its own lesson.
    """
    from courses.models import DocumentMaterial, VideoMaterial

    documents = []
    text_parts = []
    transcription_service = None

    for material in materials:
        material_content = None
        document_ref = None
        material_type = material.material_type

        if material_type == "note":
            material_content = material.description or ""
        elif material_type in ("video", "audio"):
            try:
                video_material = VideoMaterial.objects.filter(lesson_material=material).first()
                if not video_material and material.file_url:
                    video_material = VideoMaterial.objects.filter(video_url=material.file_url).first()
                if video_material and video_material.has_transcript and video_material.transcript:
                    material_content = video_material.transcript
                elif material.file_url:
                    if transcription_service is None:
                        from ai.video_transcription_service import VideoTranscriptionService

                        transcription_service = VideoTranscriptionService()
                    result = transcription_service.transcribe_video(material.file_url)
                    if result.get("success") and result.get("transcript"):
                        material_content = result["transcript"]
                    else:
                        material_content = (
                            f"[Video/Audio URL: {material.file_url} - Transcription unavailable]"
                        )
                else:
                    material_content = f"[Video/Audio material: {material.title} - No URL available]"
            except Exception:
                logger.exception("Error processing video/audio material %s", material.id)
                material_content = f"[Video/Audio material: {material.title} - Error processing]"
        elif material_type == "book":
            pages = material.book_pages.all().order_by("page_number")
            if pages.exists():
                page_contents = []
                for page in pages:
                    page_text = f"Page {page.page_number}"
                    if page.title:
                        page_text += f": {page.title}"
                    page_text += f"\n{page.content}"
                    page_contents.append(page_text)
                material_content = "\n\n".join(page_contents)
            else:
                material_content = material.description or ""
        elif material_type == "document":
            try:
                document_material = DocumentMaterial.objects.filter(lesson_material=material).first()
                file_url = None
                mime_type = None
                if document_material and document_material.file_url:
                    file_url = document_material.file_url
                    mime_type = document_material.mime_type or "application/pdf"
                elif material.file_url:
                    file_url = material.file_url
                    extension = (material.file_extension or "").lower()
                    mime_type = _MIME_BY_EXTENSION.get(extension, "application/pdf")
                if file_url:
                    document_ref = {
                        "uri": file_url,
                        "mime_type": mime_type or "application/pdf",
                        "title": material.title or "document",
                    }
                else:
                    material_content = material.description or ""
            except Exception:
                logger.exception("Error processing document material %s", material.id)
                material_content = material.description or ""
        else:
            material_content = material.description or ""

        if document_ref:
            documents.append(document_ref)
        elif material_content and str(material_content).strip():
            text_parts.append(
                f"=== {material.title} ({material_type}) ===\n{material_content}"
            )

    content = "\n\n".join(text_parts)
    return {
        "lesson_title": lesson.title,
        "lesson_order": lesson.order,
        "content": content,
        "documents": documents,
        "has_source": bool(content.strip() or documents),
    }
