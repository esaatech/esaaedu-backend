"""
Cloud Tasks worker for TutorX assignment grading.

POST /api/internal/tutorx/grade-submission/
Body: {"submission_id": "...", "submitted_at": "<grading_run_token>"}
"""
import logging

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import AssignmentSubmission
from tutorx.services.assignment_submission import (
    TutorXGradingPermanentError,
    TutorXGradingRetryableError,
    handle_assignment_submission,
)
from tutorx.services.grading_queue import (
    grading_run_token,
    is_last_grade_attempt,
    verify_cloud_tasks_request,
)

logger = logging.getLogger(__name__)


def _mark_grading_failed(submission) -> None:
    """Set grading_failed only if this run is still the active one."""
    updated = AssignmentSubmission.objects.filter(
        pk=submission.pk,
        status='grading',
    ).update(status='grading_failed')
    if updated:
        submission.status = 'grading_failed'


class TutorXGradeSubmissionTaskView(APIView):
    """Internal worker. Accepts only a Cloud Tasks OIDC token for the runtime service account."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        ok, error, retry_count = verify_cloud_tasks_request(request)
        if not ok:
            return Response({'error': error}, status=status.HTTP_401_UNAUTHORIZED)

        submission_id = request.data.get('submission_id')
        submitted_at = request.data.get('submitted_at')
        if not submission_id or not submitted_at:
            logger.error('TutorX grade task missing submission_id or submitted_at')
            return Response(
                {'error': 'submission_id and submitted_at are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            submission = AssignmentSubmission.objects.select_related('assignment').get(id=submission_id)
        except AssignmentSubmission.DoesNotExist:
            logger.error('TutorX grade task submission %s does not exist', submission_id)
            return Response({'status': 'skipped', 'reason': 'missing'}, status=status.HTTP_200_OK)
        except (ValueError, TypeError, ValidationError):
            return Response({'error': 'Invalid submission_id.'}, status=status.HTTP_400_BAD_REQUEST)

        if submission.status != 'grading' or grading_run_token(submission) != submitted_at:
            logger.info(
                'TutorX grade task skipped submission %s status=%s',
                submission.id,
                submission.status,
            )
            return Response({'status': 'skipped'}, status=status.HTTP_200_OK)

        try:
            handle_assignment_submission(submission, raise_on_grader_error=True)
        except TutorXGradingPermanentError as exc:
            logger.error('TutorX grade permanent failure submission %s: %s', submission.id, exc)
            _mark_grading_failed(submission)
            return Response(
                {'status': 'grading_failed', 'error': str(exc)},
                status=status.HTTP_200_OK,
            )
        except TutorXGradingRetryableError as exc:
            return self._retry_or_fail(submission, retry_count, exc)
        except Exception as exc:
            logger.exception('TutorX grade failed submission %s', submission.id)
            return self._retry_or_fail(submission, retry_count, exc)

        submission.refresh_from_db()
        if submission.status == 'grading':
            return self._retry_or_fail(
                submission,
                retry_count,
                TutorXGradingRetryableError('Grading did not finish.'),
            )
        return Response({'status': submission.status}, status=status.HTTP_200_OK)

    def _retry_or_fail(self, submission, retry_count, exc):
        if is_last_grade_attempt(retry_count):
            logger.error(
                'TutorX grade exhausted retries submission %s: %s',
                submission.id,
                exc,
            )
            _mark_grading_failed(submission)
            return Response(
                {'status': 'grading_failed', 'error': str(exc)},
                status=status.HTTP_200_OK,
            )
        logger.warning(
            'TutorX grade retryable failure submission %s attempt %s: %s',
            submission.id,
            retry_count + 1,
            exc,
        )
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
