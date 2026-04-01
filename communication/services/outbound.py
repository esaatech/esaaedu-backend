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
    format_branded_outbound,
    get_twilio_credentials,
    send_sms,
)

if TYPE_CHECKING:
    from courses.models import Class

User = get_user_model()
logger = logging.getLogger(__name__)


def send_teacher_sms_to_student(
    *,
    teacher: User,
    student: User,
    message_body: str,
    course_class: Class | None = None,
) -> SmsRoutingLog:
    """
    Validate access, normalize destination phone, send branded SMS, persist outbound log.
    """
    from courses.models import Class as ClassModel
    from users.models import StudentProfile

    if not teacher.is_teacher:
        raise PermissionError("Only teachers can send SMS")
    if student.role != User.Role.STUDENT:
        raise ValueError("Target user must be a student")

    if course_class is not None:
        if course_class.teacher_id != teacher.id:
            raise PermissionError("You do not teach this class")
        if not course_class.students.filter(pk=student.pk).exists():
            raise PermissionError("Student is not in this class")
    else:
        if not ClassModel.objects.filter(teacher=teacher, students=student).exists():
            raise PermissionError("You have no shared class with this student")

    try:
        profile = StudentProfile.objects.get(user=student)
    except StudentProfile.DoesNotExist:
        raise ValueError("Student has no profile") from None

    raw_phone = (profile.child_phone or "").strip() or (profile.parent_phone or "").strip()
    if not raw_phone:
        raise ValueError("No child_phone or parent_phone on student profile")

    to_e164 = normalize_to_e164(raw_phone)
    _, _, from_number = get_twilio_credentials()
    twilio_number_e164 = normalize_to_e164(from_number)

    teacher_name = teacher.get_full_name() or teacher.email
    class_name = course_class.name if course_class else None
    full_body = format_branded_outbound(
        class_name=class_name,
        teacher_display_name=teacher_name,
        message_body=message_body,
    )

    try:
        with transaction.atomic():
            sid = send_sms(to_e164=to_e164, body=full_body)
            log = SmsRoutingLog.objects.create(
                twilio_number=twilio_number_e164,
                student_phone=to_e164,
                teacher=teacher,
                course_class=course_class,
                direction=SmsRoutingLog.Direction.OUTBOUND,
                body=full_body,
                twilio_message_sid=sid,
            )
    except TwilioNotConfiguredError:
        logger.exception("Twilio not configured for outbound SMS")
        raise

    return log
