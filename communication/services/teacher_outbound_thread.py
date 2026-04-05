"""
Teacher-facing outbound channel thread (SMS first): same phone line + Twilio number as send SMS.

Email/WhatsApp reserved via API channel= parameter.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

from communication.models import SmsRoutingLog
from communication.services.phone import normalize_to_e164
from communication.services.staff_sms_ui import conversation_match_q
from communication.services.twilio_sms import get_twilio_credentials
from courses.models import Class, Course
from users.models import StudentProfile

User = get_user_model()

SMS_THREAD_LIMIT = 80


class _PhoneAnchor:
    __slots__ = ("student_phone", "twilio_number")

    def __init__(self, student_phone: str, twilio_number: str):
        self.student_phone = student_phone
        self.twilio_number = twilio_number


def _resolve_course_class(
    *,
    teacher,
    student: User,
    course: Course | None,
    course_class: Class | None,
) -> tuple[Course | None, Class | None]:
    if not teacher.is_teacher:
        raise PermissionError("Only teachers can access this")
    if student.role != User.Role.STUDENT:
        raise ValueError("Target user must be a student")

    resolved_class: Class | None = course_class
    resolved_course: Course | None = course

    if course_class is not None:
        if course_class.teacher_id != teacher.id:
            raise PermissionError("You do not teach this class")
        if not course_class.students.filter(pk=student.pk).exists():
            raise PermissionError("Student is not in this class")
        if course is not None and course_class.course_id != course.id:
            raise ValueError("class_id does not belong to the given course_id")
        resolved_course = course_class.course

    elif course is not None:
        if course.teacher_id != teacher.id:
            raise PermissionError("You do not teach this course")
        matches = Class.objects.filter(teacher=teacher, course=course, students=student)
        n = matches.count()
        if n == 0:
            raise PermissionError("Student is not in your class for this course")
        if n > 1:
            raise PermissionError(
                "Multiple classes match this course and student; pass class_id to disambiguate"
            )
        resolved_class = matches.first()

    else:
        shared = Class.objects.filter(teacher=teacher, students=student).order_by("id")
        if not shared.exists():
            raise PermissionError("You have no shared class with this student")
        resolved_class = shared.first()
        resolved_course = resolved_class.course if resolved_class else None

    return resolved_course, resolved_class


def resolve_teacher_sms_peer_e164(
    *,
    teacher,
    student: User,
    course: Course | None = None,
    course_class: Class | None = None,
    recipient_type: str,
    target_phone: str | None = None,
) -> tuple[str, str, Course | None, Class | None]:
    """
    E.164 peer phone + Twilio from-number, after permission checks.
    recipient_type: 'parent' | 'student' — matches TeacherStudentMessagingPanel SMS line selection.
    """
    resolved_course, resolved_class = _resolve_course_class(
        teacher=teacher, student=student, course=course, course_class=course_class
    )

    try:
        profile = StudentProfile.objects.get(user=student)
    except StudentProfile.DoesNotExist as e:
        raise ValueError("Student has no profile") from e

    child_raw = (profile.child_phone or "").strip()
    parent_raw = (profile.parent_phone or "").strip()

    if target_phone:
        target_e164 = normalize_to_e164(target_phone.strip())
        allowed: set[str] = set()
        if child_raw:
            allowed.add(normalize_to_e164(child_raw))
        if parent_raw:
            allowed.add(normalize_to_e164(parent_raw))
        if not allowed:
            raise ValueError("No child_phone or parent_phone on student profile")
        if target_e164 not in allowed:
            raise PermissionError(
                "target_phone is not an allowed student/parent phone for this student"
            )
        to_e164 = target_e164
    else:
        if recipient_type == "parent":
            raw = parent_raw or child_raw
        else:
            raw = child_raw
        if not raw:
            raise ValueError("No phone on file for this recipient line")
        to_e164 = normalize_to_e164(raw)

    _, _, from_number = get_twilio_credentials()
    twilio_e164 = normalize_to_e164(from_number)
    return to_e164, twilio_e164, resolved_course, resolved_class


def queryset_teacher_sms_thread(
    *,
    teacher,
    student_phone_e164: str,
    twilio_number_e164: str,
    course_id: uuid.UUID | None,
):
    anchor = _PhoneAnchor(student_phone_e164, twilio_number_e164)
    q = conversation_match_q(anchor)
    qs = SmsRoutingLog.objects.filter(q, teacher=teacher)
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    return qs.order_by("-created_at")[: max(1, min(SMS_THREAD_LIMIT, 200))]


def serialize_sms_log_row(log: SmsRoutingLog) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(log.id),
        "direction": log.direction,
        "body": log.body or "",
        "created_at": log.created_at.isoformat(),
    }
    if log.direction == SmsRoutingLog.Direction.INBOUND:
        row["read_at"] = log.read_at.isoformat() if log.read_at else None
    else:
        row["delivery_status"] = (log.delivery_status or "").strip()
        row["delivery_error_code"] = (log.delivery_error_code or "").strip()
    return row


def mark_teacher_sms_thread_inbound_read(
    *,
    teacher,
    student_phone_e164: str,
    twilio_number_e164: str,
    course_id: uuid.UUID | None,
) -> int:
    anchor = _PhoneAnchor(student_phone_e164, twilio_number_e164)
    q = conversation_match_q(anchor)
    flt = SmsRoutingLog.objects.filter(
        q,
        teacher=teacher,
        direction=SmsRoutingLog.Direction.INBOUND,
        read_at__isnull=True,
    )
    if course_id is not None:
        flt = flt.filter(course_id=course_id)
    return flt.update(read_at=timezone.now())
