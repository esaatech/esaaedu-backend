"""
Staged lesson video upload API (signed URL → complete → convert).

Shared by Video/Audio lessons and TutorX interactive video.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Lesson, LessonVideoUpload
from courses.permissions import user_is_course_member
from courses.services.lesson_video_upload import (
    LessonVideoUploadError,
    complete_upload,
    create_draft_upload,
    delete_upload,
    get_latest_job,
    retry_conversion,
    serialize_job,
)


def _error_response(exc: LessonVideoUploadError) -> Response:
    return Response({'error': str(exc)}, status=exc.status_code)


class LessonVideoUploadCreateView(APIView):
    """
    POST /api/teacher/lesson-video-uploads/

    Body JSON:
      lesson_id, target ('video_audio'|'tutorx'),
      filename, content_type, size_bytes

    Creates a draft job and returns a signed PUT URL for direct GCS upload.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if getattr(request.user, 'role', None) != 'teacher':
            return Response({'error': 'Teacher access required'}, status=status.HTTP_403_FORBIDDEN)

        lesson_id = request.data.get('lesson_id')
        target = (request.data.get('target') or '').strip()
        filename = request.data.get('filename') or ''
        content_type = request.data.get('content_type') or 'video/mp4'
        try:
            size_bytes = int(request.data.get('size_bytes') or 0)
        except (TypeError, ValueError):
            size_bytes = 0

        if not lesson_id:
            return Response({'error': 'lesson_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        lesson = get_object_or_404(Lesson, id=lesson_id)
        try:
            job, upload_info = create_draft_upload(
                lesson=lesson,
                user=request.user,
                target=target,
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
            )
        except LessonVideoUploadError as e:
            return _error_response(e)

        return Response(
            serialize_job(job, include_upload=upload_info),
            status=status.HTTP_201_CREATED,
        )


class LessonVideoUploadDetailView(APIView):
    """GET / DELETE /api/teacher/lesson-video-uploads/<id>/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, upload_id):
        job = get_object_or_404(LessonVideoUpload, id=upload_id)
        if not user_is_course_member(request.user, job.lesson.course):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        return Response(serialize_job(job))

    def delete(self, request, upload_id):
        job = get_object_or_404(LessonVideoUpload, id=upload_id)
        try:
            delete_upload(job, user=request.user)
        except LessonVideoUploadError as e:
            return _error_response(e)
        return Response({'success': True}, status=status.HTTP_200_OK)


class LessonVideoUploadCompleteView(APIView):
    """
    POST /api/teacher/lesson-video-uploads/<id>/complete/

    Confirms the GCS object exists, then starts conversion (inline by default).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, upload_id):
        job = get_object_or_404(LessonVideoUpload, id=upload_id)
        try:
            job = complete_upload(job, user=request.user)
        except LessonVideoUploadError as e:
            return _error_response(e)
        return Response(serialize_job(job))


class LessonVideoUploadConvertView(APIView):
    """
    POST /api/teacher/lesson-video-uploads/<id>/convert/

    Retry / re-run conversion (useful after failure or for external workers).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, upload_id):
        job = get_object_or_404(LessonVideoUpload, id=upload_id)
        try:
            job = retry_conversion(job, user=request.user)
        except LessonVideoUploadError as e:
            return _error_response(e)
        return Response(serialize_job(job))


class LessonVideoUploadForLessonView(APIView):
    """GET /api/teacher/lessons/<lesson_id>/video-upload/ — latest job for lesson."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        if not user_is_course_member(request.user, lesson.course):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        job = get_latest_job(lesson)
        if not job:
            return Response({'upload': None})
        return Response({'upload': serialize_job(job)})
