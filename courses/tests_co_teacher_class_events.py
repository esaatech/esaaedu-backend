"""
Co-teacher can schedule events on owner-created classes.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Class, ClassEvent, Course, CourseMembership
from courses.permissions import ensure_owner_membership

User = get_user_model()


def _make_teacher(*, email: str, firebase_uid: str, first_name: str, last_name: str) -> User:
    user = User(
        email=email,
        username=email,
        firebase_uid=firebase_uid,
        role='teacher',
        first_name=first_name,
        last_name=last_name,
    )
    user.set_password('testpass123')
    user.save()
    return user


class CoTeacherClassEventsAPITestCase(APITestCase):
    def setUp(self):
        self.owner = _make_teacher(
            email='owner-schedule@test.com',
            firebase_uid='owner_schedule_uid',
            first_name='Own',
            last_name='Er',
        )
        self.co_teacher = _make_teacher(
            email='co-schedule@test.com',
            firebase_uid='co_schedule_uid',
            first_name='Co',
            last_name='Teacher',
        )
        self.outsider = _make_teacher(
            email='outsider-schedule@test.com',
            firebase_uid='outsider_schedule_uid',
            first_name='Out',
            last_name='Sider',
        )
        self.course = Course.objects.create(
            title='Schedule Course',
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
        # Class owned by course owner — the shared-class case
        self.class_instance = Class.objects.create(
            name='Owner Class',
            course=self.course,
            teacher=self.owner,
        )
        now = timezone.now()
        self.existing_event = ClassEvent.objects.create(
            title='Existing Session',
            class_instance=self.class_instance,
            event_type='meeting',
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
        )
        self.events_url = reverse(
            'courses:class_events',
            kwargs={'class_id': self.class_instance.id},
        )
        self.detail_url = reverse(
            'courses:teacher_class_detail',
            kwargs={'class_id': self.class_instance.id},
        )

    def test_co_teacher_can_list_events_on_owner_class(self):
        self.client.force_authenticate(user=self.co_teacher)
        response = self.client.get(self.events_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['class_id']), str(self.class_instance.id))
        self.assertEqual(len(response.data['events']), 1)
        self.assertEqual(response.data['events'][0]['title'], 'Existing Session')

    def test_co_teacher_can_create_event_on_owner_class(self):
        self.client.force_authenticate(user=self.co_teacher)
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        response = self.client.post(
            self.events_url,
            {
                'title': 'Co-teacher Session',
                'description': 'Scheduled by co-teacher',
                'event_type': 'meeting',
                'start_time': start.isoformat(),
                'end_time': end.isoformat(),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['title'], 'Co-teacher Session')
        self.assertTrue(
            ClassEvent.objects.filter(
                class_instance=self.class_instance,
                title='Co-teacher Session',
            ).exists()
        )

    def test_co_teacher_can_get_owner_class_detail(self):
        self.client.force_authenticate(user=self.co_teacher)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Owner Class')

    def test_outsider_cannot_list_events(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.events_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
