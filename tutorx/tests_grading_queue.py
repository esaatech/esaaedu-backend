"""TutorX Cloud Tasks grading: queue helper, submit view, and worker."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from courses.models import Assignment, AssignmentSubmission, Course, Lesson
from student.models import EnrolledCourse
from tutorx.services.assignment_submission import TutorXGradingRetryableError
from tutorx.services.grading_queue import (
    CloudTaskAlreadyExists,
    CloudTaskConfigError,
    CloudTaskEnqueueError,
    enqueue_tutorx_grade,
    grading_run_token,
    tutorx_grading_uses_queue,
)
from users.models import StudentProfile

User = get_user_model()

QUEUE_SETTINGS = dict(
    CLOUD_TASKS_QUEUE='tutorx-assignment-grading',
    CLOUD_TASKS_PROJECT='esaasolution',
    CLOUD_TASKS_LOCATION='us-central1',
    CLOUD_TASKS_TARGET_URL='https://example.test/api/internal/tutorx/grade-submission/',
    CLOUD_TASKS_SERVICE_ACCOUNT='grader@example.iam.gserviceaccount.com',
    CLOUD_TASKS_OIDC_AUDIENCE='https://example.test/api/internal/tutorx/grade-submission/',
    CLOUD_TASKS_MAX_ATTEMPTS=3,
    CLOUD_TASKS_DISPATCH_DEADLINE_SECONDS=1200,
)


class GradingQueueHelperTests(TestCase):
    def test_inline_when_queue_name_is_empty(self):
        with override_settings(CLOUD_TASKS_QUEUE=''):
            self.assertFalse(tutorx_grading_uses_queue())

    def test_partial_queue_config_is_an_error(self):
        with override_settings(
            CLOUD_TASKS_QUEUE='tutorx-assignment-grading',
            CLOUD_TASKS_PROJECT='esaasolution',
            CLOUD_TASKS_TARGET_URL='',
            CLOUD_TASKS_SERVICE_ACCOUNT='grader@example.iam.gserviceaccount.com',
        ):
            with self.assertRaises(CloudTaskConfigError):
                tutorx_grading_uses_queue()

    @override_settings(**QUEUE_SETTINGS)
    @patch('httpx.post')
    @patch('google.auth.default')
    def test_enqueue_names_task_from_submission_and_submit_time(self, mock_auth, mock_post):
        credentials = MagicMock()
        credentials.token = 'token'
        mock_auth.return_value = (credentials, None)
        mock_post.return_value = MagicMock(status_code=200, text='')
        submitted_at = datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc)
        submission = SimpleNamespace(id='abc-123', submitted_at=submitted_at)

        task_id = enqueue_tutorx_grade(submission)

        self.assertEqual(task_id, 'tutorx-grade-abc-123-20260923060000000000')
        body = mock_post.call_args.kwargs['json']
        self.assertEqual(body['task']['name'].rsplit('/', 1)[-1], task_id)
        self.assertEqual(body['task']['dispatchDeadline'], '1200s')
        self.assertEqual(
            body['task']['httpRequest']['oidcToken']['serviceAccountEmail'],
            'grader@example.iam.gserviceaccount.com',
        )
        self.assertEqual(grading_run_token(submission), '20260923060000000000')

    @override_settings(**QUEUE_SETTINGS)
    @patch('httpx.post')
    @patch('google.auth.default')
    def test_duplicate_task_is_already_exists(self, mock_auth, mock_post):
        credentials = MagicMock()
        credentials.token = 'token'
        mock_auth.return_value = (credentials, None)
        mock_post.return_value = MagicMock(status_code=409, text='ALREADY_EXISTS')
        submission = SimpleNamespace(
            id='abc-123',
            submitted_at=datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc),
        )
        with self.assertRaises(CloudTaskAlreadyExists):
            enqueue_tutorx_grade(submission)


class TutorXGradeFlowTests(APITestCase):
    def setUp(self):
        self.teacher = User(
            email='teacher-grade@example.com',
            username='teacher-grade@example.com',
            firebase_uid='grade_teacher_uid',
            role='teacher',
            first_name='Teach',
            last_name='Er',
        )
        self.teacher.set_password('pass')
        self.teacher.save()
        self.student = User(
            email='student-grade@example.com',
            username='student-grade@example.com',
            firebase_uid='grade_student_uid',
            role='student',
            first_name='Stu',
            last_name='Dent',
        )
        self.student.set_password('pass')
        self.student.save()
        self.profile = StudentProfile.objects.create(user=self.student)
        self.course = Course.objects.create(
            title='Grade Course',
            description='Desc',
            long_description='Long',
            teacher=self.teacher,
            category='coding',
            age_range='8-12',
            price=0,
            is_free=True,
        )
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='TutorX lesson',
            order=1,
            duration=10,
            type='tutorx',
        )
        self.assignment = Assignment.objects.create(title='Essay', passing_score=70)
        self.assignment.lessons.add(self.lesson)
        self.enrollment = EnrolledCourse.objects.create(
            student_profile=self.profile,
            course=self.course,
            status='active',
        )
        self.client.force_authenticate(user=self.student)

    def _submit(self, answers=None):
        return self.client.post(
            f'/api/student/assignments/{self.assignment.id}/submit/',
            {
                'answers': answers or {'q1': 'my answer'},
                'is_draft': False,
                'submission_type': 'completed',
            },
            format='json',
        )

    def _submission(self):
        return AssignmentSubmission.objects.get(student=self.student, assignment=self.assignment)

    @override_settings(**QUEUE_SETTINGS)
    @patch('tutorx.services.grading_queue.enqueue_tutorx_grade', return_value='task')
    def test_submit_enqueues_and_returns_grading(self, mock_enqueue):
        response = self._submit()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['submission']['status'], 'grading')
        mock_enqueue.assert_called_once()

        again = self._submit()
        self.assertEqual(again.status_code, 409, again.data)
        self.assertEqual(again.data['submission']['status'], 'grading')
        mock_enqueue.assert_called_once()
        self.assertEqual(self._submission().answers['q1'], 'my answer')

    @override_settings(**QUEUE_SETTINGS)
    @patch(
        'tutorx.services.grading_queue.enqueue_tutorx_grade',
        side_effect=CloudTaskEnqueueError('down'),
    )
    def test_enqueue_failure_marks_grading_failed(self, _mock_enqueue):
        response = self._submit()
        self.assertEqual(response.status_code, 503, response.data)
        self.assertEqual(self._submission().status, 'grading_failed')

    @override_settings(CLOUD_TASKS_QUEUE='')
    @patch('tutorx.services.assignment_submission.handle_assignment_submission')
    def test_inline_grade_when_queue_is_not_configured(self, mock_handle):
        response = self._submit()
        self.assertEqual(response.status_code, 200, response.data)
        mock_handle.assert_called_once()
        self.assertEqual(self._submission().status, 'submitted')

    def _worker(self, submission, retry_count=0):
        return self.client.post(
            '/api/internal/tutorx/grade-submission/',
            {
                'submission_id': str(submission.id),
                'submitted_at': grading_run_token(submission),
            },
            format='json',
            HTTP_X_CLOUDTASKS_TASKRETRYCOUNT=str(retry_count),
        )

    @override_settings(**QUEUE_SETTINGS)
    @patch('tutorx.grading_views.verify_cloud_tasks_request', return_value=(True, '', 0))
    @patch('tutorx.grading_views.handle_assignment_submission')
    def test_worker_skips_a_finished_grade(self, mock_handle, _verify):
        submission = AssignmentSubmission.objects.create(
            student=self.student,
            assignment=self.assignment,
            enrollment=self.enrollment,
            attempt_number=1,
            status='graded',
            is_graded=True,
            answers={'q1': 'done'},
        )
        response = self._worker(submission)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'skipped')
        mock_handle.assert_not_called()

    @override_settings(**QUEUE_SETTINGS)
    @patch('tutorx.grading_views.verify_cloud_tasks_request')
    @patch(
        'tutorx.grading_views.handle_assignment_submission',
        side_effect=TutorXGradingRetryableError('gemini down'),
    )
    def test_worker_retries_then_marks_grading_failed(self, _handle, mock_verify):
        submission = AssignmentSubmission.objects.create(
            student=self.student,
            assignment=self.assignment,
            enrollment=self.enrollment,
            attempt_number=1,
            status='grading',
            is_graded=False,
            answers={'q1': 'draft'},
        )
        mock_verify.return_value = (True, '', 0)
        first = self._worker(submission, retry_count=0)
        self.assertEqual(first.status_code, 500, first.data)
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'grading')

        mock_verify.return_value = (True, '', 2)
        last = self._worker(submission, retry_count=2)
        self.assertEqual(last.status_code, 200, last.data)
        self.assertEqual(last.data['status'], 'grading_failed')
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'grading_failed')

    def test_worker_rejects_requests_without_cloud_tasks_auth(self):
        response = self.client.post(
            '/api/internal/tutorx/grade-submission/',
            {'submission_id': 'x', 'submitted_at': 'y'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_save_keeps_grading_status(self):
        submission = AssignmentSubmission.objects.create(
            student=self.student,
            assignment=self.assignment,
            enrollment=self.enrollment,
            attempt_number=1,
            status='grading',
            is_graded=False,
            answers={},
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'grading')
        submission.answers = {'q1': 'still grading'}
        submission.save(update_fields=['answers', 'status'])
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'grading')
