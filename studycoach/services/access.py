"""Enrollment / access helpers for Study Coach."""

from courses.models import Lesson
from courses.permissions import user_is_course_member
from student.models import EnrolledCourse


def user_can_manage_lesson_bank(user, lesson: Lesson) -> bool:
    """True if the user owns or co-teaches the lesson's course."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if not hasattr(user, "teacher_profile"):
        return False
    return user_is_course_member(user, lesson.course)


def user_can_study_lesson(user, lesson: Lesson) -> bool:
    """True if the user is enrolled in the lesson's course (active or completed)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if not hasattr(user, "student_profile"):
        return False
    return EnrolledCourse.objects.filter(
        student_profile=user.student_profile,
        course=lesson.course,
        status__in=["active", "completed"],
    ).exists()
