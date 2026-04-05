"""
Map inbound unread SmsRoutingLog rows to teacher roster enrollments (course + profile phones).

Used by GET /api/courses/teacher/students/master/ for sms_unread_count (and optional split).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Optional, Tuple
import uuid

from communication.models import SmsRoutingLog
from communication.services.phone import normalize_to_e164


def _normalize_or_none(raw: Optional[str]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    try:
        return normalize_to_e164(str(raw).strip())
    except ValueError:
        return None


def build_teacher_sms_unread_pair_counts(teacher) -> Dict[Tuple[Optional[uuid.UUID], str], int]:
    """
    Count inbound unread logs per (course_id, student_phone) as stored on SmsRoutingLog.
    course_id may be None for uncorrelated rows (not attributed to roster rows here).
    """
    counts: Dict[Tuple[Optional[uuid.UUID], str], int] = defaultdict(int)
    qs = SmsRoutingLog.objects.filter(
        teacher=teacher,
        direction=SmsRoutingLog.Direction.INBOUND,
        read_at__isnull=True,
    ).values_list("course_id", "student_phone")
    for course_id, student_phone in qs:
        if not student_phone:
            continue
        counts[(course_id, student_phone)] += 1
    return dict(counts)


def sms_unread_fields_for_enrollment(
    pair_counts: Dict[Tuple[Optional[uuid.UUID], str], int],
    *,
    course_id: uuid.UUID,
    profile,
) -> Dict[str, Any]:
    """
    Fields for one master student row: sms_unread_count; split parent/student when phones differ.
    """
    child_e164 = _normalize_or_none(getattr(profile, "child_phone", None))
    parent_e164 = _normalize_or_none(getattr(profile, "parent_phone", None))

    def cnt(phone: Optional[str]) -> int:
        if not phone:
            return 0
        return int(pair_counts.get((course_id, phone), 0))

    if not child_e164 and not parent_e164:
        return {"sms_unread_count": 0}

    if child_e164 and parent_e164 and child_e164 == parent_e164:
        total = cnt(child_e164)
        return {"sms_unread_count": total}

    st = cnt(child_e164)
    pr = cnt(parent_e164)
    if st == 0 and pr == 0:
        return {"sms_unread_count": 0}
    return {
        "sms_unread_count": st + pr,
        "student_sms_unread_count": st,
        "parent_sms_unread_count": pr,
    }
