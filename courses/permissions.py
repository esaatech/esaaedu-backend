"""
Course access helpers for owner vs co-teacher membership.

Course.teacher remains the source of truth for ownership.
CourseMembership tracks owner + co-teachers for teaching access.
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import Course, CourseMembership


def user_is_course_owner(user, course) -> bool:
    """True if user is the primary course owner (Course.teacher)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return course.teacher_id == user.id


def user_is_course_member(user, course) -> bool:
    """True if user is owner or a co-teacher on the course."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if course.teacher_id == user.id:
        return True
    return CourseMembership.objects.filter(course_id=course.pk, user_id=user.id).exists()


def get_course_role(user, course) -> str | None:
    """Return 'owner', 'teacher', or None if not a member."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if course.teacher_id == user.id:
        return CourseMembership.ROLE_OWNER
    if CourseMembership.objects.filter(course_id=course.pk, user_id=user.id).exists():
        return CourseMembership.ROLE_TEACHER
    return None


def owned_or_member_q(user, prefix: str = '') -> Q:
    """
    Q filter for courses the user owns or co-teaches.

    prefix=''           → filter Course queryset
    prefix='course__'   → filter related objects with a course FK
    prefix='lesson__course__' etc. for deeper relations
    """
    teacher_key = f'{prefix}teacher' if prefix else 'teacher'
    membership_key = f'{prefix}memberships__user' if prefix else 'memberships__user'
    return Q(**{teacher_key: user}) | Q(**{membership_key: user})


def courses_for_teacher(user) -> QuerySet:
    """Courses the teacher owns or co-teaches."""
    return Course.objects.filter(owned_or_member_q(user)).distinct()


def ensure_owner_membership(course, invited_by=None) -> CourseMembership:
    """Create or sync the owner membership row for course.teacher."""
    membership, created = CourseMembership.objects.get_or_create(
        course=course,
        user=course.teacher,
        defaults={
            'role': CourseMembership.ROLE_OWNER,
            'invited_by': invited_by,
        },
    )
    if not created and membership.role != CourseMembership.ROLE_OWNER:
        membership.role = CourseMembership.ROLE_OWNER
        membership.save(update_fields=['role'])
    return membership


def user_can_access_class(user, class_instance) -> bool:
    """True if user teaches the class or is a course member."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if class_instance.teacher_id == user.id:
        return True
    return user_is_course_member(user, class_instance.course)


def classes_for_teacher(user) -> QuerySet:
    """Classes the teacher owns or can access via course membership."""
    from .models import Class

    return Class.objects.filter(
        Q(teacher=user) | owned_or_member_q(user, prefix='course__')
    ).distinct()
