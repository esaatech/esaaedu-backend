"""Staff-initiated SMS (reply from log or compose to user) — Twilio + SmsRoutingLog."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from communication.models import SmsRoutingLog
from communication.services.phone import normalize_to_e164
from communication.services.twilio_sms import TwilioNotConfiguredError, get_twilio_credentials, send_sms

if TYPE_CHECKING:
    from users.models import User as UserType

User = get_user_model()
logger = logging.getLogger(__name__)


def _twilio_from_e164() -> str:
    _, _, from_number = get_twilio_credentials()
    return normalize_to_e164(from_number)


def send_staff_sms_to_e164(*, to_e164: str, message_body: str) -> SmsRoutingLog:
    """
    Send SMS to an arbitrary E.164 number (staff compose by typed number).
    No teacher/course context on the log.
    """
    body = (message_body or "").strip()
    if not body:
        raise ValueError("message is required")
    to_norm = normalize_to_e164(to_e164)
    twilio_number_e164 = _twilio_from_e164()
    try:
        with transaction.atomic():
            sid, initial_status = send_sms(to_e164=to_norm, body=body)
            return SmsRoutingLog.objects.create(
                twilio_number=twilio_number_e164,
                student_phone=to_norm,
                teacher=None,
                course=None,
                course_class=None,
                direction=SmsRoutingLog.Direction.OUTBOUND,
                body=body,
                twilio_message_sid=sid,
                delivery_status=initial_status,
                delivery_updated_at=timezone.now(),
            )
    except TwilioNotConfiguredError:
        logger.exception("Twilio not configured for staff SMS to E.164")
        raise


def send_staff_reply_from_log(*, log: SmsRoutingLog, message_body: str) -> SmsRoutingLog:
    """
    Send SMS to the log's student_phone (family line). Persists outbound SmsRoutingLog.
    Copies teacher/course context from the log when present.
    """
    body = (message_body or "").strip()
    if not body:
        raise ValueError("message is required")

    to_e164 = normalize_to_e164(log.student_phone)
    twilio_number_e164 = _twilio_from_e164()

    try:
        with transaction.atomic():
            sid, initial_status = send_sms(to_e164=to_e164, body=body)
            return SmsRoutingLog.objects.create(
                twilio_number=twilio_number_e164,
                student_phone=to_e164,
                teacher=log.teacher,
                course=log.course,
                course_class=log.course_class,
                direction=SmsRoutingLog.Direction.OUTBOUND,
                body=body,
                twilio_message_sid=sid,
                delivery_status=initial_status,
                delivery_updated_at=timezone.now(),
            )
    except TwilioNotConfiguredError:
        logger.exception("Twilio not configured for staff SMS reply")
        raise


def _phones_for_student(user: UserType) -> list[tuple[str, str]]:
    """List of (key, e164) for child / parent lines from StudentProfile."""
    from users.models import StudentProfile

    try:
        profile = StudentProfile.objects.get(user=user)
    except StudentProfile.DoesNotExist:
        return []

    out: list[tuple[str, str]] = []
    if (profile.child_phone or "").strip():
        out.append(("child", normalize_to_e164(profile.child_phone)))
    if (profile.parent_phone or "").strip():
        out.append(("parent", normalize_to_e164(profile.parent_phone)))
    return out


def _phones_for_parent(user: UserType) -> list[tuple[str, str]]:
    from users.models import ParentProfile

    try:
        profile = ParentProfile.objects.get(user=user)
    except ParentProfile.DoesNotExist:
        return []
    if not (profile.phone_number or "").strip():
        return []
    return [("parent_phone", normalize_to_e164(profile.phone_number))]


def _phones_for_teacher(user: UserType) -> list[tuple[str, str]]:
    from users.models import TeacherProfile

    try:
        profile = TeacherProfile.objects.get(user=user)
    except TeacherProfile.DoesNotExist:
        return []
    if not (profile.phone_number or "").strip():
        return []
    return [("teacher_phone", normalize_to_e164(profile.phone_number))]


def resolve_staff_compose_phones(user: UserType) -> list[dict]:
    """Return [{\"key\": str, \"phone\": str, \"label\": str}, ...] for UI."""
    role = user.role
    if role == User.Role.STUDENT:
        pairs = _phones_for_student(user)
        labels = {"child": "Student (child phone)", "parent": "Parent phone on profile"}
        return [{"key": k, "phone": p, "label": labels.get(k, k)} for k, p in pairs]
    if role == User.Role.PARENT:
        return [
            {"key": x[0], "phone": x[1], "label": "Parent profile phone"}
            for x in _phones_for_parent(user)
        ]
    if role == User.Role.TEACHER:
        return [
            {"key": x[0], "phone": x[1], "label": "Teacher profile phone"}
            for x in _phones_for_teacher(user)
        ]
    return []


def send_staff_compose_to_user(
    *,
    target_user: UserType,
    message_body: str,
    phone_key: str | None = None,
) -> SmsRoutingLog:
    """
    Send to a student/parent/teacher using profile phones.
    If phone_key is set (e.g. child vs parent), use that line; otherwise first available.
    """
    body = (message_body or "").strip()
    if not body:
        raise ValueError("message is required")

    if target_user.role not in (
        User.Role.STUDENT,
        User.Role.PARENT,
        User.Role.TEACHER,
    ):
        raise ValueError("Target user must be a student, parent, or teacher")

    options = resolve_staff_compose_phones(target_user)
    if not options:
        raise ValueError("No SMS-capable phone on file for this user")

    to_e164: str | None = None
    if phone_key:
        for opt in options:
            if opt["key"] == phone_key:
                to_e164 = opt["phone"]
                break
        if to_e164 is None:
            raise ValueError("phone_key does not match an available number for this user")
    else:
        to_e164 = options[0]["phone"]

    twilio_number_e164 = _twilio_from_e164()

    teacher = target_user if target_user.role == User.Role.TEACHER else None

    try:
        with transaction.atomic():
            sid, initial_status = send_sms(to_e164=to_e164, body=body)
            return SmsRoutingLog.objects.create(
                twilio_number=twilio_number_e164,
                student_phone=to_e164,
                teacher=teacher,
                course=None,
                course_class=None,
                direction=SmsRoutingLog.Direction.OUTBOUND,
                body=body,
                twilio_message_sid=sid,
                delivery_status=initial_status,
                delivery_updated_at=timezone.now(),
            )
    except TwilioNotConfiguredError:
        logger.exception("Twilio not configured for staff SMS compose")
        raise
