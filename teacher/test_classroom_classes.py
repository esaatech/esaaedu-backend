from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Class, ClassEvent, Course, CourseMembership
from courses.permissions import ensure_owner_membership

User = get_user_model()


class TeacherClassroomClassesAPITestCase(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            firebase_uid='teacher_classroom_uid',
            email='teacher-classroom@test.com',
            username='teacher-classroom@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Teacher',
            role='teacher',
        )
        self.co_teacher = User.objects.create_user(
            firebase_uid='co_teacher_classroom_uid',
            email='co-classroom@test.com',
            username='co-classroom@test.com',
            password='testpass123',
            first_name='Co',
            last_name='Teacher',
            role='teacher',
        )
        self.student = User.objects.create_user(
            firebase_uid='student_classroom_uid',
            email='student-classroom@test.com',
            username='student-classroom@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Student',
            role='student',
        )
        self.course = Course.objects.create(
            title='Classroom Course',
            description='Desc',
            teacher=self.teacher,
            category='Computer Science',
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
        self.class_instance = Class.objects.create(
            name='Morning Group',
            course=self.course,
            teacher=self.teacher,
        )
        now = timezone.now()
        self.live_event = ClassEvent.objects.create(
            title='Live Lesson',
            class_instance=self.class_instance,
            event_type='lesson',
            start_time=now - timedelta(minutes=10),
            end_time=now + timedelta(minutes=50),
        )
        self.past_event = ClassEvent.objects.create(
            title='Past Lesson',
            class_instance=self.class_instance,
            event_type='lesson',
            start_time=now - timedelta(days=2),
            end_time=now - timedelta(days=2) + timedelta(hours=1),
        )
        self.url = reverse('teacher:teacher_classroom_classes')

    def test_student_cannot_access(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_sees_live_and_past_classes(self):
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['in_progress_classes']), 1)
        self.assertEqual(response.data['in_progress_classes'][0]['id'], str(self.class_instance.id))
        self.assertEqual(response.data['in_progress_classes'][0]['current_event']['title'], 'Live Lesson')
        self.assertEqual(response.data['summary']['total_finished'], 1)
        self.assertEqual(response.data['finished_events'][0]['event_title'], 'Past Lesson')

    def test_co_teacher_sees_shared_classes(self):
        self.client.force_authenticate(user=self.co_teacher)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['in_progress_classes']), 1)
        self.assertEqual(response.data['in_progress_classes'][0]['id'], str(self.class_instance.id))
