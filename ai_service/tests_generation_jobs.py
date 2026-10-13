"""Quiz and assignment generation jobs: one draft per lesson, delete on finish."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from ai_service.generation_jobs import (
    claim_generation_job,
    execute_generation_job,
    serialize_generation_job,
    start_lesson_generation,
)
from ai_service.generation_views import LessonQuestionGenerationTaskView
from ai_service.models import AIGenerationJob
from courses.models import Course, Lesson

User = get_user_model()


@override_settings(CLOUD_TASKS_QUEUE="")
class GenerationJobTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            email="gen-teacher@example.com",
            username="gen-teacher@example.com",
            firebase_uid="gen_teacher_uid",
            role="teacher",
            first_name="Gen",
            last_name="Teacher",
        )
        self.course = Course.objects.create(
            title="Gen Course",
            description="Desc",
            long_description="Long",
            teacher=self.teacher,
            category="coding",
            age_range="8-12",
            price=0,
            is_free=True,
        )
        self.lesson = Lesson.objects.create(
            course=self.course,
            title="Lesson",
            order=1,
            duration=10,
            type="text_lesson",
        )
        self.kwargs = {
            "lesson_title": "Lesson",
            "lesson_description": "",
            "content": "Python variables store values.",
            "documents": [],
            "total_questions": 2,
            "multiple_choice_count": 2,
            "true_false_count": 0,
            "system_instruction": "Make a quiz.",
            "temperature": 0.7,
        }

    def test_second_start_reuses_the_in_flight_row(self):
        first, should_start = claim_generation_job(
            lesson=self.lesson,
            teacher=self.teacher,
            kind="quiz",
            generation_kwargs=self.kwargs,
        )
        second, should_start_again = claim_generation_job(
            lesson=self.lesson,
            teacher=self.teacher,
            kind="quiz",
            generation_kwargs=self.kwargs,
        )
        self.assertTrue(should_start)
        self.assertFalse(should_start_again)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            AIGenerationJob.objects.filter(lesson=self.lesson, kind="quiz").count(),
            1,
        )

    @patch("ai_service.generation_jobs.generate_quiz")
    def test_inline_run_stores_the_draft_until_deleted(self, mock_generate):
        mock_generate.return_value = {
            "success": True,
            "result": {"title": "Quiz", "questions": [{"question_text": "Q1"}]},
        }
        payload, http_status = start_lesson_generation(
            lesson=self.lesson,
            teacher=self.teacher,
            kind="quiz",
            generation_kwargs=self.kwargs,
        )
        self.assertEqual(http_status, 202)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["result"]["questions"][0]["question_text"], "Q1")
        self.assertEqual(AIGenerationJob.objects.count(), 1)

        AIGenerationJob.objects.filter(lesson=self.lesson, kind="quiz").delete()
        self.assertEqual(AIGenerationJob.objects.count(), 0)

    @patch("ai_service.generation_jobs.generate_quiz")
    def test_failed_validation_does_not_retry(self, mock_generate):
        mock_generate.return_value = {
            "success": False,
            "error_code": "validation_error",
            "error": "No readable text in the PDF.",
        }
        job, _ = claim_generation_job(
            lesson=self.lesson,
            teacher=self.teacher,
            kind="quiz",
            generation_kwargs=self.kwargs,
        )
        outcome = execute_generation_job(str(job.id), job.run_token)
        job.refresh_from_db()
        self.assertEqual(outcome, "failed")
        self.assertEqual(job.status, "failed")
        self.assertIn("PDF", job.error_message)
        body = serialize_generation_job(job)
        self.assertIsNone(body["result"])

    @patch(
        "ai_service.generation_views.verify_cloud_tasks_request",
        return_value=(True, "", 0),
    )
    @patch(
        "ai_service.generation_views.execute_generation_job",
        return_value="completed",
    )
    def test_worker_accepts_a_cloud_tasks_token(self, _execute, _verify):
        request = APIRequestFactory().post(
            "/api/internal/ai/generate-lesson-questions/",
            {"job_id": "abc", "run_token": "tok"},
            format="json",
        )
        response = LessonQuestionGenerationTaskView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")
