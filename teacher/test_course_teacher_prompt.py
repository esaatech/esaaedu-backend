from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ai.models import CourseTeacherPrompt
from courses.models import Course, CourseMembership
from courses.permissions import ensure_owner_membership

User = get_user_model()


class CourseTeacherPromptAPITestCase(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            firebase_uid="teacher_prompt_uid",
            email="teacher-prompt@test.com",
            username="teacher-prompt@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Teacher",
            role="teacher",
        )
        self.co_teacher = User.objects.create_user(
            firebase_uid="co_teacher_prompt_uid",
            email="co-prompt@test.com",
            username="co-prompt@test.com",
            password="testpass123",
            first_name="Co",
            last_name="Teacher",
            role="teacher",
        )
        self.student = User.objects.create_user(
            firebase_uid="student_prompt_uid",
            email="student-prompt@test.com",
            username="student-prompt@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Student",
            role="student",
        )
        self.course = Course.objects.create(
            title="Prompt Course",
            description="Desc",
            long_description="Long",
            teacher=self.teacher,
            category="Computer Science",
            age_range="8-12",
            price=0,
            is_free=True,
        )
        ensure_owner_membership(self.course)
        CourseMembership.objects.create(
            course=self.course,
            user=self.co_teacher,
            role=CourseMembership.ROLE_TEACHER,
            invited_by=self.teacher,
        )
        self.url = reverse(
            "teacher:course_teacher_prompt",
            kwargs={"course_id": self.course.id, "kind": "quiz"},
        )

    def test_get_returns_empty_instruction_when_missing(self):
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["instruction"], "")

    def test_put_upserts_and_get_returns_saved_instruction(self):
        self.client.force_authenticate(user=self.teacher)
        put_response = self.client.put(
            self.url,
            {"instruction": "Focus on fractions."},
            format="json",
        )
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        self.assertEqual(put_response.data["instruction"], "Focus on fractions.")

        get_response = self.client.get(self.url)
        self.assertEqual(get_response.data["instruction"], "Focus on fractions.")
        self.assertEqual(CourseTeacherPrompt.objects.count(), 1)

    def test_co_teacher_has_separate_instruction(self):
        self.client.force_authenticate(user=self.teacher)
        self.client.put(self.url, {"instruction": "Owner prompt"}, format="json")

        self.client.force_authenticate(user=self.co_teacher)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["instruction"], "")

        self.client.put(self.url, {"instruction": "Co-teacher prompt"}, format="json")
        self.assertEqual(CourseTeacherPrompt.objects.count(), 2)

    def test_student_cannot_access(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_kind_returns_400(self):
        self.client.force_authenticate(user=self.teacher)
        url = reverse(
            "teacher:course_teacher_prompt",
            kwargs={"course_id": self.course.id, "kind": "exam"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
