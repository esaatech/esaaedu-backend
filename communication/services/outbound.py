"""Orchestration: teacher → student SMS + SmsRoutingLog."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction

from communication.models import SmsRoutingLog
from communication.services.phone import normalize_to_e164
from communication.services.twilio_sms import (
    TwilioNotConfiguredError,
    get_twilio_credentials,
    send_sms,
)

if TYPE_CHECKING:
    from courses.models import Class, Course

User = get_user_model()
logger = logging.getLogger(__name__)


def send_teacher_sms_to_student(
    *,
    teacher: User,
    student: User,
    message_body: str,
    course: Course | None = None,
    course_class: Class | None = None,
    target_phone: str | None = None,
) -> SmsRoutingLog:
    """
    Validate access, normalize destination phone, send branded SMS, persist outbound log.

    Pass ``course`` and/or ``course_class`` from the API (course_id / class_id resolution).
    If neither is passed, uses any class shared between teacher and student for access and logging.
    """
    from courses.models import Class as ClassModel
    from courses.models import Course as CourseModel
    from users.models import StudentProfile

    if not teacher.is_teacher:
        raise PermissionError("Only teachers can send SMS")
    if student.role != User.Role.STUDENT:
        raise ValueError("Target user must be a student")

    resolved_class: ClassModel | None = course_class
    resolved_course: CourseModel | None = course

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
        matches = ClassModel.objects.filter(
            teacher=teacher,
            course=course,
            students=student,
        )
        n = matches.count()
        if n == 0:
            raise PermissionError("Student is not in your class for this course")
        if n > 1:
            raise PermissionError(
                "Multiple classes match this course and student; send class_id to disambiguate"
            )
        resolved_class = matches.first()

    else:
        shared = ClassModel.objects.filter(teacher=teacher, students=student).order_by("id")
        if not shared.exists():
            raise PermissionError("You have no shared class with this student")
        resolved_class = shared.first()
        resolved_course = resolved_class.course if resolved_class else None

    try:
        profile = StudentProfile.objects.get(user=student)
    except StudentProfile.DoesNotExist:
        raise ValueError("Student has no profile") from None

    child_raw = (profile.child_phone or "").strip()
    parent_raw = (profile.parent_phone or "").strip()

    if target_phone:
        target_e164 = normalize_to_e164(target_phone)
        allowed: set[str] = set()
        if child_raw:
            allowed.add(normalize_to_e164(child_raw))
        if parent_raw:
            allowed.add(normalize_to_e164(parent_raw))
        if not allowed:
            raise ValueError("No child_phone or parent_phone on student profile")
        if target_e164 not in allowed:
            raise PermissionError("target_phone is not an allowed student/parent phone for this student")
        to_e164 = target_e164
    else:
        raw_phone = child_raw or parent_raw
        if not raw_phone:
            raise ValueError("No child_phone or parent_phone on student profile")
        to_e164 = normalize_to_e164(raw_phone)
    _, _, from_number = get_twilio_credentials()
    twilio_number_e164 = normalize_to_e164(from_number)

    # Send the client-rendered body as-is; templates already include branding and course wording.
    full_body = message_body.strip()

    try:
        with transaction.atomic():
            sid = send_sms(to_e164=to_e164, body=full_body)
            log = SmsRoutingLog.objects.create(
                twilio_number=twilio_number_e164,
                student_phone=to_e164,
                teacher=teacher,
                course=resolved_course,
                course_class=resolved_class,
                direction=SmsRoutingLog.Direction.OUTBOUND,
                body=full_body,
                twilio_message_sid=sid,
            )
    except TwilioNotConfiguredError:
        logger.exception("Twilio not configured for outbound SMS")
        raise

    return log
