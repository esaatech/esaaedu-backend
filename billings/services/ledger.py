"""
Staff payment ledger: querysets and resolver helpers (mirrors teacher/services/roster.py).
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db.models import F, Prefetch, Sum
from django.utils import timezone

from billings.models import Payment, Subscribers
from courses.models import Class

User = get_user_model()


def resolved_course_for_payment(p: Payment):
    if p.course_id:
        return p.course
    if p.enrolled_course_id:
        return p.enrolled_course.course
    return None


def resolved_course_id(p: Payment):
    if p.course_id:
        return p.course_id
    if p.enrolled_course_id:
        return p.enrolled_course.course_id
    return None



def get_ledger_succeeded_paid_totals_month_and_ytd(*, cal_tz: ZoneInfo) -> dict:
    """
    Match admin dashboard Payment card: succeeded rows, bounded by paid_at in cal_tz.
    Sums all currencies together (same as dashboard); nearly all rows are typically USD.
    """
    cal_now = timezone.now().astimezone(cal_tz)
    today = cal_now.date()

    month_first = today.replace(day=1)
    last_dom = monthrange(month_first.year, month_first.month)[1]
    month_last = month_first.replace(day=last_dom)
    month_start_dt = datetime.combine(month_first, time.min).replace(tzinfo=cal_tz)
    month_end_dt = datetime.combine(month_last, time.max).replace(tzinfo=cal_tz)

    year_first = today.replace(month=1, day=1)
    year_start_dt = datetime.combine(year_first, time.min).replace(tzinfo=cal_tz)
    year_end_dt = datetime.combine(today, time.max).replace(tzinfo=cal_tz)

    base = Payment.objects.filter(status=Payment.STATUS_SUCCEEDED)

    month_total = base.filter(
        paid_at__gte=month_start_dt,
        paid_at__lte=month_end_dt,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    ytd_total = base.filter(
        paid_at__gte=year_start_dt,
        paid_at__lte=year_end_dt,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    return {
        "month_total": month_total,
        "ytd_total": ytd_total,
        "calendar_year": today.year,
        "timezone_name": getattr(cal_tz, "key", str(cal_tz)),
    }


def get_payment_ledger_queryset(*, limit: int) -> list[Payment]:
    """Recent payments (all statuses); ordering prefers settled time, then record time."""
    limit = max(1, min(int(limit), 100))
    qs = (
        Payment.objects.select_related(
            "user",
            "course",
            "enrolled_course",
            "enrolled_course__course",
            "enrolled_course__student_profile__user",
        ).order_by(F("paid_at").desc(nulls_last=True), "-created_at")
    )
    return list(qs[:limit])


def classes_by_user_course_pairs(
    payments: list[Payment],
) -> dict[tuple[int, object], list[Class]]:
    """Map (user_id, course_pk) -> Class rows for list column / context."""
    mapping: defaultdict[tuple[int, object], list[Class]] = defaultdict(list)
    user_ids: set[int] = set()
    course_ids: set = set()
    for p in payments:
        user_ids.add(p.user_id)
        cid = resolved_course_id(p)
        if cid:
            course_ids.add(cid)

    if not course_ids or not user_ids:
        return dict(mapping)

    classes = (
        Class.objects.filter(course_id__in=course_ids, students__id__in=user_ids)
        .select_related("teacher", "course")
        .prefetch_related(
            Prefetch("students", queryset=User.objects.filter(pk__in=user_ids))
        )
        .distinct()
    )

    for cls in classes:
        c_pk = cls.course_id
        for student in cls.students.all():
            mapping[(student.pk, c_pk)].append(cls)

    return dict(mapping)


def class_summary_for_payment(
    p: Payment, pair_map: dict[tuple[int, object], list[Class]]
) -> str:
    cid = resolved_course_id(p)
    if not cid:
        return ""
    rows = pair_map.get((p.user_id, cid)) or []
    if not rows:
        return ""
    if len(rows) == 1:
        return rows[0].name
    return f"{rows[0].name} (+{len(rows) - 1})"


def get_payment_ledger_detail(payment_id: int) -> Payment | None:
    return (
        Payment.objects.filter(pk=payment_id)
        .select_related(
            "user",
            "user__customer_account",
            "course",
            "enrolled_course",
            "enrolled_course__course",
            "enrolled_course__student_profile__user",
        )
        .first()
    )


def subscriber_for_payment(p: Payment) -> Subscribers | None:
    cid = resolved_course_id(p)
    if not cid:
        return None
    return Subscribers.objects.filter(user_id=p.user_id, course_id=cid).first()


def classes_for_payment_detail(p: Payment) -> list[Class]:
    cid = resolved_course_id(p)
    if not cid:
        return []
    return list(
        Class.objects.filter(course_id=cid, students__id=p.user_id)
        .select_related("teacher", "course")
        .order_by("name")
    )
