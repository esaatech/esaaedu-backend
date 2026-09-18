"""
Co-teacher can send parent SMS on an owner-created course/class.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from communication.models import SmsRoutingLog
from courses.models import Class, Course, CourseMembership
from courses.permissions import ensure_owner_membership
from users.models import StudentProfile

User = get_user_model()


def _make_user(
    *,
    email: str,
    firebase_uid: str,
    role: str,
    first_name: str,
    last_name: str,
) -> User:
    user = User(
        email=email,
        username=email,
        firebase_uid=firebase_uid,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    user.set_password('testpass123')
    user.save()
    return user


class CoTeacherSmsAPITestCase(APITestCase):
    def setUp(self):
        self.owner = _make_user(
            email='owner-sms@test.com',
            firebase_uid='owner_sms_uid',
            role='teacher',
            first_name='Own',
            last_name='Er',
        )
        self.co_teacher = _make_user(
            email='co-sms@test.com',
            firebase_uid='co_sms_uid',
            role='teacher',
            first_name='Co',
            last_name='Teacher',
        )
        self.outsider = _make_user(
            email='outsider-sms@test.com',
            firebase_uid='outsider_sms_uid',
            role='teacher',
            first_name='Out',
            last_name='Sider',
        )
        self.student = _make_user(
            email='student-sms@test.com',
            firebase_uid='student_sms_uid',
            role='student',
            first_name='Jaden',
            last_name='Student',
        )
        StudentProfile.objects.create(
            user=self.student,
            parent_phone='+15551234567',
            parent_name='Parent',
        )
        self.course = Course.objects.create(
            title='SMS Course',
            description='Desc',
            long_description='Long',
            teacher=self.owner,
            category='coding',
            age_range='8-12',
            price=0,
            is_free=True,
        )
        ensure_owner_membership(self.course)
        CourseMembership.objects.create(
            course=self.course,
            user=self.co_teacher,
            role=CourseMembership.ROLE_TEACHER,
            invited_by=self.owner,
        )
        self.class_instance = Class.objects.create(
            name='Owner Class',
            course=self.course,
            teacher=self.owner,
        )
        self.class_instance.students.add(self.student)
        self.send_url = reverse('teacher:teacher_sms_send')

    @patch('communication.services.outbound.send_sms', return_value=('SMCOTEACH01', 'queued'))
    @patch(
        'communication.services.outbound.get_twilio_credentials',
        return_value=('sid', 'token', '+15550009999'),
    )
    def test_co_teacher_can_send_sms_on_owner_course(self, _creds, mock_send):
        self.client.force_authenticate(user=self.co_teacher)
        response = self.client.post(
            self.send_url,
            {
                'student_user_id': self.student.id,
                'message': 'Hello From SbtyAcademy Jaden maths class starts soon.',
                'course_id': str(self.course.id),
                'target_phone': '+15551234567',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        mock_send.assert_called_once()
        self.assertTrue(
            SmsRoutingLog.objects.filter(
                twilio_message_sid='SMCOTEACH01',
                teacher=self.co_teacher,
                course=self.course,
                course_class=self.class_instance,
                direction=SmsRoutingLog.Direction.OUTBOUND,
            ).exists()
        )

    def test_outsider_cannot_send_sms_on_owner_course(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(
            self.send_url,
            {
                'student_user_id': self.student.id,
                'message': 'Should fail',
                'course_id': str(self.course.id),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
