"""
Convert a single LessonVideoUpload job (Cloud Run Job entrypoint).

Usage:
  python manage.py convert_lesson_video_upload <upload_uuid>

Set LESSON_VIDEO_CONVERSION_BACKEND=deferred on the API service, then run this
command from a Cloud Run Job (or worker) that has ffmpeg + GCS access.
"""
from django.core.management.base import BaseCommand, CommandError

from courses.models import LessonVideoUpload
from courses.services.lesson_video_conversion import InlineFfmpegConversionBackend


class Command(BaseCommand):
    help = 'Convert a staged lesson video upload (download from GCS → HLS → attach)'

    def add_arguments(self, parser):
        parser.add_argument('upload_id', type=str, help='LessonVideoUpload UUID')

    def handle(self, *args, **options):
        upload_id = options['upload_id']
        try:
            job = LessonVideoUpload.objects.select_related('lesson', 'audio_video_material').get(
                id=upload_id
            )
        except LessonVideoUpload.DoesNotExist as e:
            raise CommandError(f'Upload not found: {upload_id}') from e

        if job.status not in (
            LessonVideoUpload.STATUS_UPLOADED,
            LessonVideoUpload.STATUS_PROCESSING,
            LessonVideoUpload.STATUS_FAILED,
        ):
            raise CommandError(
                f'Upload {upload_id} has status "{job.status}"; '
                'expected uploaded, processing, or failed.'
            )

        self.stdout.write(f'Converting {upload_id} ({job.original_filename})…')
        job = InlineFfmpegConversionBackend().start(job)
        if job.status == LessonVideoUpload.STATUS_READY:
            self.stdout.write(self.style.SUCCESS(f'Ready: {job.playlist_url}'))
        else:
            raise CommandError(job.error_message or f'Conversion ended as {job.status}')
