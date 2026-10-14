"""Assessment generation creates one draft job per lesson."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_service.generation_jobs import start_assessment_generation
from ai_service.models import AIGenerationJob
from courses.models import Course, CourseAssessment, Lesson

User = get_user_model()


@override_settings(CLOUD_TASKS_QUEUE="")
class AssessmentGenerationJobTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            email="assess-gen@example.com",
            username="assess-gen@example.com",
            firebase_uid="assess_gen_uid",
            role="teacher",
            first_name="Assess",
            last_name="Teacher",
        )
        self.course = Course.objects.create(
            title="Assess Course",
            description="Desc",
            long_description="Long",
            teacher=self.teacher,
            category="coding",
            age_range="8-12",
            price=0,
            is_free=True,
        )
        self.assessment = CourseAssessment.objects.create(
            course=self.course,
            assessment_type="test",
            title="Midterm",
            created_by=self.teacher,
        )
        self.lesson_a = Lesson.objects.create(
            course=self.course, title="Early", order=1, duration=10, type="text_lesson"
        )
        self.lesson_b = Lesson.objects.create(
            course=self.course, title="Later", order=2, duration=10, type="text_lesson"
        )

    def _plans(self):
        return [
            {
                "lesson": self.lesson_a,
                "material_ids": [],
                "total": 1,
                "counts": {"multiple_choice": 1},
                "system_instruction": "Make a test.",
                "temperature": 0.7,
                "assessment_type": "test",
            },
            {
                "lesson": self.lesson_b,
                "material_ids": [],
                "total": 1,
                "counts": {"essay": 1},
                "system_instruction": "Make a test.",
                "temperature": 0.7,
                "assessment_type": "test",
            },
        ]

    @patch("ai_service.generation_jobs._run_assessment_job")
    def test_inline_run_finishes_one_job_per_lesson(self, mock_run):
        mock_run.return_value = {
            "success": True,
            "result": {"questions": [{"question_text": "Q", "type": "multiple_choice"}]},
        }
        payload, http_status = start_assessment_generation(
            assessment=self.assessment,
            teacher=self.teacher,
            lesson_plans=self._plans(),
        )
        self.assertEqual(http_status, 202)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["result"]["questions"]), 2)
        self.assertEqual(
            AIGenerationJob.objects.filter(assessment=self.assessment).count(),
            2,
        )

    @patch("ai_service.generation_jobs._run_assessment_job")
    def test_second_start_reuses_in_flight_jobs(self, mock_run):
        AIGenerationJob.objects.create(
            lesson=self.lesson_a,
            assessment=self.assessment,
            teacher=self.teacher,
            kind=AIGenerationJob.Kind.ASSESSMENT,
            status=AIGenerationJob.Status.PENDING,
            run_token="existing",
            request_payload={},
        )
        payload, http_status = start_assessment_generation(
            assessment=self.assessment,
            teacher=self.teacher,
            lesson_plans=self._plans(),
        )
        self.assertEqual(http_status, 202)
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["total"], 1)
        mock_run.assert_not_called()
