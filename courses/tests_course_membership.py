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


def _make_user(*, email: str, firebase_uid: str, role: str, first_name: str, last_name: str) -> User:
    user = User(
        email=email,
        username=email,
        firebase_uid=firebase_uid,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    user.set_password('pass')
    user.save()
    return user


class CourseMembershipPermissionsTests(TestCase):
    def setUp(self):
        self.owner = _make_user(
            email='owner@example.com',
            firebase_uid='membership_owner_uid',
            role='teacher',
            first_name='Own',
            last_name='Er',
        )
        self.co_teacher = _make_user(
            email='co@example.com',
            firebase_uid='membership_co_uid',
            role='teacher',
            first_name='Co',
            last_name='Teacher',
        )
        self.other = _make_user(
            email='other@example.com',
            firebase_uid='membership_other_uid',
            role='teacher',
            first_name='Other',
            last_name='Teacher',
        )
        self.student = _make_user(
            email='student@example.com',
            firebase_uid='membership_student_uid',
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

    def test_enrollment_query_needs_distinct_with_memberships(self):
        """Membership join multiplies enrollments unless distinct() is applied."""
        from student.models import EnrolledCourse
        from users.models import StudentProfile
        from courses.permissions import owned_or_member_q

        CourseMembership.objects.create(
            course=self.course,
            user=self.other,
            role=CourseMembership.ROLE_TEACHER,
            invited_by=self.owner,
        )
        profile = StudentProfile.objects.create(user=self.student)
        EnrolledCourse.objects.create(
            student_profile=profile,
            course=self.course,
            status='active',
        )
        duplicated = EnrolledCourse.objects.filter(
            owned_or_member_q(self.owner, 'course__')
        )
        deduped = duplicated.distinct()
        self.assertGreater(duplicated.count(), 1)
        self.assertEqual(deduped.count(), 1)
