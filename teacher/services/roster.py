from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch, Q

from courses.models import Class, Course
from users.models import TeacherPayout

User = get_user_model()


def get_teacher_roster_queryset(*, q: str | None = None, focus_id: int | None = None):
    """Top-level teacher rows for list rendering / API."""
    qs = (
        User.objects.filter(role=User.Role.TEACHER, is_active=True)
        .select_related("teacher_profile")
        .prefetch_related(
            Prefetch(
                "teacher_profile__payouts",
                queryset=TeacherPayout.objects.order_by("-due_date", "-created_at"),
            )
        )
        .annotate(
            courses_count=Count("created_courses", distinct=True),
            classes_active_count=Count(
                "taught_classes",
                filter=Q(taught_classes__is_active=True),
                distinct=True,
            ),
        )
        .order_by("first_name", "last_name", "email")
    )

    if q:
        needle = q.strip()
        if needle:
            qs = qs.filter(
                Q(first_name__icontains=needle)
                | Q(last_name__icontains=needle)
                | Q(email__icontains=needle)
            )

    if focus_id:
        focused = [u for u in qs if u.pk == focus_id]
        others = [u for u in qs if u.pk != focus_id]
        return focused + others

    return list(qs)


def get_teacher_roster_detail(teacher_id: int):
    """Selected teacher detail payload input with prefetched courses/classes/students."""
    class_qs = (
        Class.objects.filter(is_active=True)
        .select_related("course")
        .prefetch_related("students")
        .order_by("name")
    )
    course_qs = (
        Course.objects.filter(status="published")
        .prefetch_related(Prefetch("classes", queryset=class_qs))
        .order_by("title")
    )

    return (
        User.objects.filter(role=User.Role.TEACHER, is_active=True, pk=teacher_id)
        .select_related("teacher_profile")
        .prefetch_related(
            Prefetch("created_courses", queryset=course_qs),
            Prefetch("taught_classes", queryset=class_qs),
            Prefetch(
                "teacher_profile__payouts",
                queryset=TeacherPayout.objects.order_by("-due_date", "-created_at"),
            ),
        )
        .first()
    )
