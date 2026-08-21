"""
Pluggable lesson-video conversion backends.

Default: in-process ffmpeg (InlineFfmpegConversionBackend).
Future: CloudRunJobConversionBackend that enqueues a job and returns immediately.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Protocol

from django.conf import settings
from django.utils import timezone

from courses.gcs_signed_urls import download_gcs_object_to_path
from courses.hls_utils import (
    HLSConversionError,
    HLSUploadError,
    convert_to_hls,
    delete_hls_from_gcs,
    upload_hls_to_gcs,
)
from courses.models import AudioVideoMaterial, LessonVideoUpload

logger = logging.getLogger(__name__)


class VideoConversionBackend(Protocol):
    def start(self, job: LessonVideoUpload) -> LessonVideoUpload:
        """Begin conversion for ``job``. May run sync or enqueue async work."""
        ...


class InlineFfmpegConversionBackend:
    """
    Download the pending GCS object, convert to HLS, attach to the lesson.

    Suitable for modest files. Large files may still hit Cloud Run memory/time
    limits — swap this backend for a Cloud Run Job when ready.
    """

    def start(self, job: LessonVideoUpload) -> LessonVideoUpload:
        from courses.services.lesson_video_upload import attach_ready_job_to_lesson

        job.status = LessonVideoUpload.STATUS_PROCESSING
        job.error_message = ''
        job.save(update_fields=['status', 'error_message', 'updated_at'])

        temp_path = None
        local_hls_dir = None
        material_id = job.id  # stable HLS prefix tied to upload id

        try:
            suffix = os.path.splitext(job.original_filename)[1] or '.mp4'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name
            download_gcs_object_to_path(job.gcs_object_name, temp_path)

            gcs_prefix = f'hls/audio-video/{material_id}/'
            # Replace any previous HLS for this upload id
            try:
                delete_hls_from_gcs(gcs_prefix)
            except Exception:
                pass

            local_hls_dir = convert_to_hls(temp_path)
            playlist_url = upload_hls_to_gcs(local_hls_dir, gcs_prefix)

            file_extension = (
                job.original_filename.rsplit('.', 1)[-1].lower()
                if '.' in job.original_filename
                else 'mp4'
            )
            safe_name = job.original_filename[:200]

            if job.audio_video_material_id:
                av = job.audio_video_material
                # Old material may point at different HLS — delete then recreate path
                try:
                    if av and av.file_name.startswith('hls/'):
                        delete_hls_from_gcs(av.file_name.rsplit('/', 1)[0] + '/')
                except Exception:
                    pass
                av.file_name = f'{gcs_prefix}playlist.m3u8'
                av.original_filename = safe_name
                av.file_url = playlist_url
                av.file_size = job.declared_size_bytes or av.file_size
                av.file_extension = file_extension
                av.mime_type = job.content_type or av.mime_type
                av.save()
            else:
                av = AudioVideoMaterial.objects.create(
                    file_name=f'{gcs_prefix}playlist.m3u8',
                    original_filename=safe_name,
                    file_url=playlist_url,
                    file_size=job.declared_size_bytes or 0,
                    file_extension=file_extension,
                    mime_type=job.content_type or 'video/mp4',
                    uploaded_by=job.created_by,
                    lesson_material=None,
                )
                job.audio_video_material = av

            job.playlist_url = playlist_url
            job.status = LessonVideoUpload.STATUS_READY
            job.completed_at = timezone.now()
            job.error_message = ''
            job.save(
                update_fields=[
                    'audio_video_material',
                    'playlist_url',
                    'status',
                    'completed_at',
                    'error_message',
                    'updated_at',
                ]
            )
            attach_ready_job_to_lesson(job)

            # Source MP4 is only needed for conversion; drop it once HLS is ready.
            try:
                from courses.gcs_signed_urls import delete_gcs_object

                if job.gcs_object_name:
                    delete_gcs_object(job.gcs_object_name)
                    logger.info(
                        'Deleted pending source object after HLS ready: %s',
                        job.gcs_object_name,
                    )
            except Exception as cleanup_err:
                # Playback still works; teacher delete / later GC can clean leftovers.
                logger.warning(
                    'Failed to delete pending source for job %s: %s',
                    job.id,
                    cleanup_err,
                )

            return job

        except (HLSConversionError, HLSUploadError, Exception) as e:
            logger.exception('Lesson video conversion failed for job %s', job.id)
            job.status = LessonVideoUpload.STATUS_FAILED
            job.error_message = str(e)[:2000]
            job.save(update_fields=['status', 'error_message', 'updated_at'])
            return job
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            if local_hls_dir is not None:
                import shutil

                try:
                    shutil.rmtree(local_hls_dir, ignore_errors=True)
                except Exception:
                    pass


class DeferredConversionBackend:
    """
    Mark the job as processing and leave conversion to an external worker.

    Wire a Cloud Run Job / queue consumer to call InlineFfmpegConversionBackend
    (or shared convert logic) for STATUS_PROCESSING jobs.
    """

    def start(self, job: LessonVideoUpload) -> LessonVideoUpload:
        job.status = LessonVideoUpload.STATUS_PROCESSING
        job.error_message = ''
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        # Future: enqueue Cloud Run Job with job.id
        logger.info(
            'Deferred conversion requested for lesson video upload %s '
            '(no worker configured — job left in processing)',
            job.id,
        )
        return job


def get_conversion_backend() -> VideoConversionBackend:
    mode = getattr(settings, 'LESSON_VIDEO_CONVERSION_BACKEND', 'inline')
    if mode == 'deferred':
        return DeferredConversionBackend()
    return InlineFfmpegConversionBackend()
