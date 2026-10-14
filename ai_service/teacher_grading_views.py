"""
Cloud Tasks worker for teacher assignment and assessment grading.

POST /api/internal/ai/grade-teacher-submission/
Body: {"job_id": "...", "run_token": "..."}
"""
import logging

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_service.models import AIGradingJob
from ai_service.teacher_grading_jobs import IN_FLIGHT, execute_teacher_grading_job
from tutorx.services.grading_queue import is_last_grade_attempt, verify_cloud_tasks_request

logger = logging.getLogger(__name__)


class TeacherGradingTaskView(APIView):
    """Internal worker. Accepts only a Cloud Tasks OIDC token."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        ok, error, retry_count = verify_cloud_tasks_request(request)
        if not ok:
            return Response({"error": error}, status=status.HTTP_401_UNAUTHORIZED)

        job_id = request.data.get("job_id")
        run_token = request.data.get("run_token")
        if not job_id or not run_token:
            return Response(
                {"error": "job_id and run_token are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            outcome = execute_teacher_grading_job(str(job_id), str(run_token))
        except (ValueError, TypeError, ValidationError):
            return Response({"error": "Invalid job_id."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Teacher grading job %s failed", job_id)
            return self._retry_or_fail(job_id, run_token, retry_count, exc)

        if outcome == "retry":
            return self._retry_or_fail(
                job_id,
                run_token,
                retry_count,
                RuntimeError("Grading did not finish."),
            )
        return Response({"status": outcome}, status=status.HTTP_200_OK)

    def _retry_or_fail(self, job_id, run_token, retry_count, exc):
        if is_last_grade_attempt(retry_count):
            AIGradingJob.objects.filter(
                id=job_id,
                run_token=run_token,
                status__in=list(IN_FLIGHT),
            ).update(
                status=AIGradingJob.Status.FAILED,
                error_message=str(exc)[:2000],
            )
            logger.error("Teacher grading job %s exhausted retries: %s", job_id, exc)
            return Response(
                {"status": "failed", "error": str(exc)},
                status=status.HTTP_200_OK,
            )
        logger.warning(
            "Teacher grading job %s retryable failure attempt %s: %s",
            job_id,
            retry_count + 1,
            exc,
        )
        return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
