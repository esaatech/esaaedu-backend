from collections import Counter
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django import template
from django.db.models import Sum
from django.utils import timezone

from billings.models import Payment, Subscribers
from courses.models import ClassEvent, ClassSession
from settings.models import get_calendar_timezone_fallback_name
from student.models import EnrolledCourse
from users.admin_calendar_tz import resolve_admin_calendar_timezone_name
from users.models import User

register = template.Library()

_SCHEDULABLE_EVENT_TYPES = frozenset({"lesson", "meeting", "break", "test", "exam"})


def _session_time_key(t):
    if not t:
        return None
    return (t.hour, t.minute, t.second)


def _combine_today_slot(today, t, cal_tz, end_crosses_midnight=False):
    naive = datetime.combine(today, t)
    if end_crosses_midnight:
        naive = naive + timedelta(days=1)
    return naive.replace(tzinfo=cal_tz)


def _calendar_day_bounds(today, cal_tz):
    """[range_start, range_end) in aware UTC-compatible datetimes for DB filters."""
    start = datetime.combine(today, time.min).replace(tzinfo=cal_tz)
    end = datetime.combine(today + timedelta(days=1), time.min).replace(tzinfo=cal_tz)
    return start, end


def _window_from_session_and_event(today, session, event, cal_tz):
    if (
        event
        and event.start_time
        and event.end_time
        and event.event_type in _SCHEDULABLE_EVENT_TYPES
    ):
        start = event.start_time.astimezone(cal_tz)
        end = event.end_time.astimezone(cal_tz)
        return start, end

    start = _combine_today_slot(today, session.start_time, cal_tz)
    end_t = session.end_time
    start_t = session.start_time
    crosses = end_t <= start_t
    end = _combine_today_slot(today, end_t, cal_tz, end_crosses_midnight=crosses)
    return start, end


def _window_from_orphan_event(event, cal_tz):
    start = event.start_time.astimezone(cal_tz)
    if event.end_time:
        end = event.end_time.astimezone(cal_tz)
    else:
        end = start + timedelta(hours=1)
    return start, end


def _classify_row(start, end, cal_now):
    if cal_now < start:
        return "upcoming"
    if end and cal_now > end:
        return "past"
    return "ongoing"


def _format_time_range(start, end):
    return (
        f"{start.strftime('%I:%M %p')} – {end.strftime('%I:%M %p')}"
        if end
        else start.strftime("%I:%M %p")
    )


def _build_timetable_sections(cal_now, today, weekday, cal_tz):
    sessions_today = (
        ClassSession.objects.filter(
            is_active=True,
            day_of_week=weekday,
            class_instance__is_active=True,
        )
        .select_related(
            "class_instance",
            "class_instance__course",
            "class_instance__teacher",
        )
        .order_by(
            "class_instance__course__title",
            "class_instance__name",
            "session_number",
            "start_time",
        )
    )

    class_ids = list(
        sessions_today.values_list("class_instance_id", flat=True).distinct()
    )

    range_start, range_end = _calendar_day_bounds(today, cal_tz)
    events_for_match = []
    if class_ids:
        events_for_match = list(
            ClassEvent.objects.filter(
                class_instance_id__in=class_ids,
                event_type__in=_SCHEDULABLE_EVENT_TYPES,
                start_time__gte=range_start,
                start_time__lt=range_end,
                start_time__isnull=False,
            ).select_related("class_instance", "class_instance__course", "lesson")
        )

    event_by_class_start = {}
    for ev in events_for_match:
        lt = ev.start_time.astimezone(cal_tz)
        if lt.date() != today:
            continue
        t = lt.time().replace(microsecond=0)
        key = (ev.class_instance_id, _session_time_key(t))
        if key not in event_by_class_start:
            event_by_class_start[key] = ev

    matched_event_ids = set()
    rows = []

    for session in sessions_today:
        cls = session.class_instance
        st = session.start_time.replace(microsecond=0)
        key = (cls.id, _session_time_key(st))
        event = event_by_class_start.get(key)
        if event:
            matched_event_ids.add(event.id)
        scheduled = event is not None

        start_dt, end_dt = _window_from_session_and_event(today, session, event, cal_tz)
        bucket = _classify_row(start_dt, end_dt, cal_now)

        teacher = cls.teacher
        teacher_label = (
            teacher.get_full_name() or teacher.email or str(teacher.pk)
        )

        rows.append(
            {
                "class_instance_id": cls.id,
                "time_range": start_dt and _format_time_range(start_dt, end_dt),
                "start_sort": start_dt,
                "class_name": cls.name,
                "course_title": cls.course.title,
                "teacher_label": teacher_label,
                "session_number": session.session_number,
                "from_timetable": True,
                "scheduled": scheduled,
                "event_title": event.title if event else "",
                "bucket": bucket,
            }
        )

    orphan_events = [ev for ev in events_for_match if ev.id not in matched_event_ids]
    # Weekly timetable vs one-off ClassEvent often disagree on wall-clock time (or TZ
    # conversion), so matching fails and the same class appears twice. When there is
    # only one session row for that class on this weekday, prefer the ClassEvent row
    # and drop the timetable-only row.
    if orphan_events:
        session_counts = Counter(s.class_instance_id for s in sessions_today)
        orphan_cids = {ev.class_instance_id for ev in orphan_events}
        rows = [
            r
            for r in rows
            if not (
                r["class_instance_id"] in orphan_cids
                and r["from_timetable"]
                and not r["scheduled"]
                and session_counts.get(r["class_instance_id"], 0) == 1
            )
        ]
    for event in orphan_events:
        lt = event.start_time.astimezone(cal_tz)
        if lt.date() != today:
            continue
        cls = event.class_instance
        start_dt, end_dt = _window_from_orphan_event(event, cal_tz)
        bucket = _classify_row(start_dt, end_dt, cal_now)
        teacher = cls.teacher
        teacher_label = (
            teacher.get_full_name() or teacher.email or str(teacher.pk)
        )
        rows.append(
            {
                "class_instance_id": cls.id,
                "time_range": _format_time_range(start_dt, end_dt),
                "start_sort": start_dt,
                "class_name": cls.name,
                "course_title": cls.course.title,
                "teacher_label": teacher_label,
                "session_number": None,
                "from_timetable": False,
                "scheduled": True,
                "event_title": event.title,
                "bucket": bucket,
            }
        )

    scheduled_count = sum(1 for r in rows if r["scheduled"])

    ongoing = [r for r in rows if r["bucket"] == "ongoing"]
    upcoming = [r for r in rows if r["bucket"] == "upcoming"]
    past = [r for r in rows if r["bucket"] == "past"]

    ongoing.sort(key=lambda r: r["start_sort"])
    upcoming.sort(key=lambda r: r["start_sort"])
    past.sort(key=lambda r: r["start_sort"], reverse=True)

    for group in (ongoing, upcoming, past):
        for r in group:
            del r["bucket"]
            del r["start_sort"]
            del r["class_instance_id"]

    return {
        "ongoing": ongoing,
        "upcoming": upcoming,
        "past": past,
        "scheduled_count": scheduled_count,
    }


@register.simple_tag(takes_context=True)
def admin_dashboard_snapshot(context):
    request = context.get("request")
    if request is None:
        cal_tz_name = get_calendar_timezone_fallback_name()
    else:
        cal_tz_name = resolve_admin_calendar_timezone_name(request)
    cal_tz = ZoneInfo(cal_tz_name)
    cal_now = timezone.now().astimezone(cal_tz)
    today = cal_now.date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    weekday = today.weekday()

    day_start = datetime.combine(today, time.min).replace(tzinfo=cal_tz)
    day_end = datetime.combine(today, time.max).replace(tzinfo=cal_tz)

    week_start_dt = datetime.combine(week_start, time.min).replace(tzinfo=cal_tz)
    week_end_dt = datetime.combine(week_end, time.max).replace(tzinfo=cal_tz)

    tt = _build_timetable_sections(cal_now, today, weekday, cal_tz)
    ongoing = tt["ongoing"]
    upcoming = tt["upcoming"]
    past = tt["past"]
    scheduled_count = tt["scheduled_count"]

    timetable_rows_total = len(ongoing) + len(upcoming) + len(past)

    sessions_today = ClassSession.objects.filter(
        is_active=True,
        day_of_week=weekday,
        class_instance__is_active=True,
    )
    distinct_class_ids = set(
        sessions_today.values_list("class_instance_id", flat=True).distinct()
    )
    timetable_slots_today = sessions_today.count()
    classes_today_count = len(distinct_class_ids)

    teachers_with_classes_today = len(
        set(sessions_today.values_list("class_instance__teacher_id", flat=True))
    )

    students_with_classes_today = 0
    if distinct_class_ids:
        students_with_classes_today = (
            User.objects.filter(
                role=User.Role.STUDENT,
                enrolled_classes__id__in=distinct_class_ids,
            )
            .distinct()
            .count()
        )

    payments_due_today = Subscribers.objects.filter(
        next_invoice_date__gte=day_start,
        next_invoice_date__lte=day_end,
        status__in=[
            Subscribers.STATUS_ACTIVE,
            Subscribers.STATUS_TRIALING,
            Subscribers.STATUS_PAST_DUE,
        ],
    )
    payments_due_week = Subscribers.objects.filter(
        next_invoice_date__gte=week_start_dt,
        next_invoice_date__lte=week_end_dt,
        status__in=[
            Subscribers.STATUS_ACTIVE,
            Subscribers.STATUS_TRIALING,
            Subscribers.STATUS_PAST_DUE,
        ],
    )
    due_today_total = payments_due_today.aggregate(total=Sum("next_invoice_amount"))[
        "total"
    ] or Decimal("0.00")
    due_week_total = payments_due_week.aggregate(total=Sum("next_invoice_amount"))[
        "total"
    ] or Decimal("0.00")

    enrollments_this_week = EnrolledCourse.objects.filter(
        enrollment_date__gte=week_start,
        enrollment_date__lte=week_end,
    )
    new_enrollments_count = enrollments_this_week.count()
    new_students_count = enrollments_this_week.values("student_profile").distinct().count()

    paid_payments_this_week = Payment.objects.filter(
        paid_at__gte=week_start_dt,
        paid_at__lte=week_end_dt,
        status=Payment.STATUS_SUCCEEDED,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    new_users_this_week = User.objects.filter(
        date_joined__gte=week_start_dt,
        date_joined__lte=week_end_dt,
    ).count()

    now = timezone.now()
    active_classes = (
        ClassEvent.objects.filter(
            start_time__gte=now,
            start_time__lte=(now + timedelta(days=7)),
        )
        .values("class_instance")
        .distinct()
        .count()
    )

    return {
        "today": today,
        "week_start": week_start,
        "week_end": week_end,
        "timezone_name": cal_tz_name,
        "timetable_rows_total": timetable_rows_total,
        "timetable_slots_today": timetable_slots_today,
        "timetable_slots_scheduled": scheduled_count,
        "timetable_ongoing": ongoing,
        "timetable_upcoming": upcoming,
        "timetable_past": past,
        "timetable_ongoing_count": len(ongoing),
        "timetable_upcoming_count": len(upcoming),
        "timetable_past_count": len(past),
        "classes_today_count": classes_today_count,
        "teachers_with_classes_today": teachers_with_classes_today,
        "students_with_classes_today": students_with_classes_today,
        "payments_due_today_count": payments_due_today.count(),
        "payments_due_week_count": payments_due_week.count(),
        "due_today_total": due_today_total,
        "due_week_total": due_week_total,
        "new_enrollments_count": new_enrollments_count,
        "new_students_count": new_students_count,
        "paid_payments_this_week": paid_payments_this_week,
        "new_users_this_week": new_users_this_week,
        "active_classes_next_7_days": active_classes,
    }
