"""
Full admin view for a single Class (students, sessions, attendance, peer sections).

Peer sections for the same course load below the primary block on the same page via fetch.
"""

from __future__ import annotations

import datetime

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from student.models import StudentAttendance

from .models import Class

ATTENDANCE_LAST_DATES = 5


def _user_may_view_class(user) -> bool:
    return user.is_active and user.is_staff and (
        user.has_perm("courses.view_class") or user.has_perm("courses.change_class")
    )


def build_class_detail_context(class_obj: Class) -> dict:
    """Shared context for the primary page and peer HTML fragments."""
    sessions = class_obj.sessions.filter(is_active=True).order_by(
        "day_of_week", "start_time", "session_number"
    )
    students = list(
        class_obj.students.all().order_by("last_name", "first_name", "email")
    )

    dates = list(
        StudentAttendance.objects.filter(class_session_id=class_obj.id)
        .values_list("date", flat=True)
        .distinct()
        .order_by("-date")[:ATTENDANCE_LAST_DATES]
    )
    dates = sorted(dates)

    records = StudentAttendance.objects.filter(
        class_session_id=class_obj.id, date__in=dates
    ).select_related("student")
    status_by_student_date: dict[tuple[int, datetime.date], str] = {}
    for r in records:
        status_by_student_date[(r.student_id, r.date)] = r.get_status_display()

    attendance_rows = []
    for student in students:
        cells = []
        for d in dates:
            cells.append(
                {
                    "date": d,
                    "label": status_by_student_date.get((student.id, d), "—"),
                }
            )
        attendance_rows.append({"student": student, "cells": cells})

    peer_classes = list(
        Class.objects.filter(course_id=class_obj.course_id, is_active=True)
        .exclude(pk=class_obj.pk)
        .order_by("name")
    )

    return {
        "class_obj": class_obj,
        "sessions": sessions,
        "students": students,
        "attendance_dates": dates,
        "attendance_rows": attendance_rows,
        "peer_classes": peer_classes,
    }


@require_GET
def class_detail_view(request, class_id):
    if not _user_may_view_class(request.user):
        raise PermissionDenied

    class_obj = get_object_or_404(
        Class.objects.select_related("course", "teacher"),
        pk=class_id,
    )
    ctx = build_class_detail_context(class_obj)
    ctx["title"] = f"{class_obj.name} — {class_obj.course.title}"
    ctx["is_primary"] = True
    return render(request, "admin/courses/class_snapshot.html", ctx)


@require_GET
def class_detail_section_view(request, class_id):
    """HTML fragment for another section (same course); appended under the primary block."""
    if not _user_may_view_class(request.user):
        raise PermissionDenied

    class_obj = get_object_or_404(
        Class.objects.select_related("course", "teacher"),
        pk=class_id,
    )
    ctx = build_class_detail_context(class_obj)
    ctx["is_primary"] = False
    html = render(
        request,
        "admin/courses/_class_detail_peer_fragment.html",
        ctx,
    ).content.decode("utf-8")
    return HttpResponse(html)
