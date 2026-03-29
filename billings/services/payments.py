"""
Staff-facing payment listing: single queryset builder for API and future consumers.
"""
from __future__ import annotations

from datetime import datetime, time
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from billings.models import Payment

def get_staff_payments_queryset(
    *,
    status: str | None = None,
    paid_after=None,
    paid_before=None,
    user_id: int | None = None,
    course_id=None,
    enrolled_course_id: int | None = None,
) -> QuerySet[Payment]:
    """
    Ordered list of payments with relations prefetched for list serialization.

    paid_after / paid_before: aware datetimes (inclusive bounds on paid_at).
    """
    qs = (
        Payment.objects.select_related('user', 'course')
        .order_by('-created_at')
    )
    if status:
        qs = qs.filter(status=status)
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    if enrolled_course_id is not None:
        qs = qs.filter(enrolled_course_id=enrolled_course_id)
    if paid_after is not None:
        qs = qs.filter(paid_at__gte=paid_after)
    if paid_before is not None:
        qs = qs.filter(paid_at__lte=paid_before)
    return qs


def parse_datetime_query_param(value: str | None):
    """
    Parse ISO date or datetime string for filter query params.
    Returns aware datetime or None if value is empty.
    Raises ValueError if non-empty and invalid.
    """
    if value is None or value == '':
        return None
    stripped = value.strip()
    if not stripped:
        return None
    dt = parse_datetime(stripped)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    d = parse_date(stripped)
    if d is not None:
        return timezone.make_aware(datetime.combine(d, time.min))
    raise ValueError(f'Invalid date or datetime: {value!r}')


def payment_is_manual(payment: Payment) -> bool:
    """True when no Stripe identifiers are set (admin/cash-style rows)."""
    return not any(
        (getattr(payment, field, '') or '').strip()
        for field in (
            'stripe_payment_intent_id',
            'stripe_invoice_id',
            'stripe_charge_id',
        )
    )
