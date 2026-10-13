"""Teacher read and delete for the current quiz or assignment generation draft."""
import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_service.generation_jobs import serialize_generation_job
from ai_service.models import AIGenerationJob
from courses.models import Lesson
from courses.permissions import courses_for_teacher

logger = logging.getLogger(__name__)


def _lesson_for_teacher(user, lesson_id):
    if getattr(user, "role", None) != "teacher":
        return None
    return (
        Lesson.objects.filter(id=lesson_id, course__in=courses_for_teacher(user))
        .first()
    )


class LessonGenerationJobView(APIView):
    """
    GET  /api/teacher/lessons/{lesson_id}/ai/generation-job/?kind=quiz|assignment
    DELETE the same URL. Delete removes the draft so it does not reopen.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = _lesson_for_teacher(request.user, lesson_id)
        if lesson is None:
            return Response(
                {"error": "Lesson not found or you do not have permission"},
                status=status.HTTP_404_NOT_FOUND,
            )
        kind = (request.query_params.get("kind") or "").strip()
        if kind not in (AIGenerationJob.Kind.QUIZ, AIGenerationJob.Kind.ASSIGNMENT):
            return Response(
                {"error": "kind must be quiz or assignment"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job = AIGenerationJob.objects.filter(lesson=lesson, kind=kind).first()
        if job is None:
            return Response({"job": None}, status=status.HTTP_200_OK)
        return Response(serialize_generation_job(job), status=status.HTTP_200_OK)

    def delete(self, request, lesson_id):
        lesson = _lesson_for_teacher(request.user, lesson_id)
        if lesson is None:
            return Response(
                {"error": "Lesson not found or you do not have permission"},
                status=status.HTTP_404_NOT_FOUND,
            )
        kind = (request.query_params.get("kind") or "").strip()
        if kind not in (AIGenerationJob.Kind.QUIZ, AIGenerationJob.Kind.ASSIGNMENT):
            return Response(
                {"error": "kind must be quiz or assignment"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = AIGenerationJob.objects.filter(lesson=lesson, kind=kind).delete()
        return Response({"deleted": deleted > 0}, status=status.HTTP_200_OK)
