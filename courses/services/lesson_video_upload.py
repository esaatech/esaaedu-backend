"""
Orchestrate staged lesson video uploads for Video/Audio and TutorX targets.
"""
from __future__ import annotations

import logging
import re
import uuid as uuid_mod
from typing import Any

from django.db import transaction
from django.utils import timezone

from courses.gcs_signed_urls import (
    SignedUrlError,
    delete_gcs_object,
    gcs_object_exists,
    generate_signed_put_url,
)
from courses.hls_utils import delete_hls_from_gcs
from courses.models import Lesson, LessonVideoUpload
from courses.permissions import user_is_course_member
from courses.services.lesson_video_conversion import get_conversion_backend

logger = logging.getLogger(__name__)

MAX_VIDEO_BYTES = 500 * 1024 * 1024
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'ogg', 'mov', 'avi', 'wmv', 'm4v'}
SIGNED_URL_TTL_SECONDS = 3600


class LessonVideoUploadError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _sanitize_filename(name: str) -> str:
    base = (name or 'video.mp4').split('/')[-1].split('\\')[-1]
    base = re.sub(r'[^A-Za-z0-9._-]+', '_', base).strip('._') or 'video.mp4'
    return base[:180]


def serialize_job(job: LessonVideoUpload, *, include_upload: dict | None = None) -> dict[str, Any]:
    data = {
        'id': str(job.id),
        'lesson_id': str(job.lesson_id),
        'target': job.target,
        'status': job.status,
        'original_filename': job.original_filename,
        'content_type': job.content_type,
        'declared_size_bytes': job.declared_size_bytes,
        'playlist_url': job.playlist_url,
        'audio_video_material_id': (
            str(job.audio_video_material_id) if job.audio_video_material_id else None
        ),
        'error_message': job.error_message or '',
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'uploaded_at': job.uploaded_at.isoformat() if job.uploaded_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
    }
    if include_upload:
        data['upload'] = include_upload
    return data


def get_blocking_job(lesson: Lesson) -> LessonVideoUpload | None:
    return (
        LessonVideoUpload.objects.filter(
            lesson=lesson,
            status__in=LessonVideoUpload.BLOCKING_STATUSES,
        )
        .order_by('-created_at')
        .first()
    )


def get_latest_job(lesson: Lesson) -> LessonVideoUpload | None:
    return LessonVideoUpload.objects.filter(lesson=lesson).order_by('-created_at').first()


@transaction.atomic
def create_draft_upload(
    *,
    lesson: Lesson,
    user,
    target: str,
    filename: str,
    content_type: str,
    size_bytes: int,
) -> tuple[LessonVideoUpload, dict[str, Any]]:
    if not user_is_course_member(user, lesson.course):
        raise LessonVideoUploadError('Only course teachers can upload lesson videos', 403)

    if target == LessonVideoUpload.TARGET_VIDEO_AUDIO and lesson.type != 'video_audio':
        raise LessonVideoUploadError('Lesson type must be Video/Audio for this upload target')
    if target == LessonVideoUpload.TARGET_TUTORX and lesson.type != 'tutorx':
        raise LessonVideoUploadError('Lesson type must be TutorX for this upload target')

    if target not in (
        LessonVideoUpload.TARGET_VIDEO_AUDIO,
        LessonVideoUpload.TARGET_TUTORX,
    ):
        raise LessonVideoUploadError('Invalid upload target')

    blocking = get_blocking_job(lesson)
    if blocking:
        raise LessonVideoUploadError(
            'An unfinished video upload already exists for this lesson. '
            'Delete it before starting a new upload.',
            409,
        )

    if size_bytes <= 0 or size_bytes > MAX_VIDEO_BYTES:
        raise LessonVideoUploadError(
            f'File size must be between 1 byte and {MAX_VIDEO_BYTES // (1024 * 1024)}MB'
        )

    safe_name = _sanitize_filename(filename)
    ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise LessonVideoUploadError(
            f'File type ".{ext}" is not allowed. Use MP4, WebM, MOV, or similar.'
        )

    ct = (content_type or 'video/mp4').split(';')[0].strip().lower()
    if not ct.startswith('video/'):
        raise LessonVideoUploadError('Content type must be a video/* MIME type')

    upload_id = uuid_mod.uuid4()
    object_name = f'pending/lesson-videos/{lesson.id}/{upload_id}/{safe_name}'

    try:
        upload_info = generate_signed_put_url(
            object_name,
            ct,
            expires_seconds=SIGNED_URL_TTL_SECONDS,
        )
    except SignedUrlError as e:
        raise LessonVideoUploadError(str(e), 503) from e

    job = LessonVideoUpload.objects.create(
        id=upload_id,
        lesson=lesson,
        target=target,
        status=LessonVideoUpload.STATUS_DRAFT,
        original_filename=safe_name,
        content_type=ct,
        declared_size_bytes=size_bytes,
        gcs_object_name=object_name,
        created_by=user,
    )
    return job, upload_info


def complete_upload(job: LessonVideoUpload, *, user) -> LessonVideoUpload:
    if not user_is_course_member(user, job.lesson.course):
        raise LessonVideoUploadError('Only course teachers can complete this upload', 403)

    if job.status not in (
        LessonVideoUpload.STATUS_DRAFT,
        LessonVideoUpload.STATUS_FAILED,
    ):
        # Idempotent: already uploaded/processing/ready
        if job.status in (
            LessonVideoUpload.STATUS_UPLOADED,
            LessonVideoUpload.STATUS_PROCESSING,
            LessonVideoUpload.STATUS_READY,
        ):
            return job
        raise LessonVideoUploadError(f'Cannot complete upload in status "{job.status}"')

    if not gcs_object_exists(job.gcs_object_name):
        raise LessonVideoUploadError(
            'Uploaded file was not found in storage. Try uploading again.',
            400,
        )

    job.status = LessonVideoUpload.STATUS_UPLOADED
    job.uploaded_at = timezone.now()
    job.error_message = ''
    job.save(update_fields=['status', 'uploaded_at', 'error_message', 'updated_at'])

    # Kick conversion (inline today; swappable via settings).
    backend = get_conversion_backend()
    return backend.start(job)


def retry_conversion(job: LessonVideoUpload, *, user) -> LessonVideoUpload:
    if not user_is_course_member(user, job.lesson.course):
        raise LessonVideoUploadError('Only course teachers can retry conversion', 403)
    if job.status not in (
        LessonVideoUpload.STATUS_UPLOADED,
        LessonVideoUpload.STATUS_FAILED,
        LessonVideoUpload.STATUS_PROCESSING,
    ):
        raise LessonVideoUploadError(f'Cannot convert upload in status "{job.status}"')
    if not gcs_object_exists(job.gcs_object_name):
        raise LessonVideoUploadError('Source file missing from storage', 400)
    return get_conversion_backend().start(job)


def attach_ready_job_to_lesson(job: LessonVideoUpload) -> None:
    """Link converted media onto the lesson / TutorX interactive video."""
    if job.status != LessonVideoUpload.STATUS_READY or not job.playlist_url:
        return

    lesson = job.lesson
    if job.target == LessonVideoUpload.TARGET_VIDEO_AUDIO:
        lesson.video_url = job.playlist_url
        lesson.save(update_fields=['video_url'])
        return

    if job.target == LessonVideoUpload.TARGET_TUTORX:
        from tutorx.models import InteractiveVideo

        interactive, _ = InteractiveVideo.objects.get_or_create(lesson=lesson)
        old = interactive.audio_video_material
        interactive.audio_video_material = job.audio_video_material
        interactive.save(update_fields=['audio_video_material', 'updated_at'])
        # Delete previous material if it is a different row
        if old and job.audio_video_material_id and old.id != job.audio_video_material_id:
            try:
                old.delete()
            except Exception as e:
                logger.warning('Failed deleting previous TutorX AV material: %s', e)


@transaction.atomic
def delete_upload(job: LessonVideoUpload, *, user) -> None:
    if not user_is_course_member(user, job.lesson.course):
        raise LessonVideoUploadError('Only course teachers can delete this upload', 403)

    lesson = job.lesson
    playlist = job.playlist_url
    material = job.audio_video_material

    # Clear lesson links if this job owns them
    if job.target == LessonVideoUpload.TARGET_VIDEO_AUDIO and playlist and lesson.video_url == playlist:
        lesson.video_url = ''
        lesson.save(update_fields=['video_url'])

    if job.target == LessonVideoUpload.TARGET_TUTORX and material:
        from tutorx.models import InteractiveVideo

        InteractiveVideo.objects.filter(
            lesson=lesson, audio_video_material=material
        ).update(audio_video_material=None)

    object_name = job.gcs_object_name
    job_id = job.id
    job.delete()

    # GCS cleanup after DB row is gone
    delete_gcs_object(object_name)
    try:
        delete_hls_from_gcs(f'hls/audio-video/{job_id}/')
    except Exception:
        pass

    if material:
        try:
            material.delete()
        except Exception as e:
            logger.warning('Failed deleting AudioVideoMaterial %s: %s', material.id, e)
