"""
Tests for course membership permission helpers.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from courses.models import Course, CourseMembership
from courses.permissions import (
    user_is_course_owner,
    user_is_course_member,
    get_course_role,
    courses_for_teacher,
    ensure_owner_membership,
)

User = get_user_model()


class CourseMembershipPermissionsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='pass',
            role='teacher',
            first_name='Own',
            last_name='Er',
        )
        self.co_teacher = User.objects.create_user(
            username='co@example.com',
            email='co@example.com',
            password='pass',
            role='teacher',
            first_name='Co',
            last_name='Teacher',
        )
        self.other = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='pass',
            role='teacher',
            first_name='Other',
            last_name='Teacher',
        )
        self.student = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='pass',
            role='student',
            first_name='Stu',
            last_name='Dent',
        )
        self.course = Course.objects.create(
            title='Test Course',
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

    def test_owner_helpers(self):
        self.assertTrue(user_is_course_owner(self.owner, self.course))
        self.assertTrue(user_is_course_member(self.owner, self.course))
        self.assertEqual(get_course_role(self.owner, self.course), 'owner')

    def test_co_teacher_helpers(self):
        self.assertFalse(user_is_course_owner(self.co_teacher, self.course))
        self.assertTrue(user_is_course_member(self.co_teacher, self.course))
        self.assertEqual(get_course_role(self.co_teacher, self.course), 'teacher')

    def test_non_member(self):
        self.assertFalse(user_is_course_owner(self.other, self.course))
        self.assertFalse(user_is_course_member(self.other, self.course))
        self.assertIsNone(get_course_role(self.other, self.course))
        self.assertFalse(user_is_course_member(self.student, self.course))

    def test_courses_for_teacher_includes_shared(self):
        owned_ids = set(courses_for_teacher(self.owner).values_list('id', flat=True))
        co_ids = set(courses_for_teacher(self.co_teacher).values_list('id', flat=True))
        other_ids = set(courses_for_teacher(self.other).values_list('id', flat=True))
        self.assertIn(self.course.id, owned_ids)
        self.assertIn(self.course.id, co_ids)
        self.assertNotIn(self.course.id, other_ids)
