from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, available_timezones

from django.db.models import QuerySet
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from courses.models import ClassEvent, ClassSession
from users.admin_calendar_tz import resolve_admin_calendar_timezone_detail

_SCHEDULABLE_EVENT_TYPES = frozenset({"lesson", "meeting", "break", "test", "exam"})


@dataclass
class WeekMeta:
    week_start: date
    week_end: date
    tz_name: str


def _session_time_key(t: time) -> tuple[int, int]:
    return (t.hour, t.minute)


def _day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, time.min).replace(tzinfo=tz),
        datetime.combine(day, time.max).replace(tzinfo=tz),
    )


def _resolve_tz_name(request, tz_name: str | None) -> str:
    if tz_name and tz_name in available_timezones():
        return tz_name
    return resolve_admin_calendar_timezone_detail(request)[0]


def _parse_week_start(start_date_raw: str | None, now_in_tz: datetime) -> date:
    if start_date_raw:
        try:
            parsed = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
            return parsed - timedelta(days=parsed.weekday())
        except ValueError:
            pass
    today = now_in_tz.date()
    return today - timedelta(days=today.weekday())


def _match_day_rows(day: date, tz: ZoneInfo, sessions_qs: QuerySet[ClassSession]) -> list[dict]:
    weekday = day.weekday()
    sessions_today = list(
        sessions_qs.filter(day_of_week=weekday).order_by(
            "class_instance__course__title",
            "class_instance__name",
            "session_number",
            "start_time",
        )
    )
    class_ids = [s.class_instance_id for s in sessions_today]
    day_start, day_end = _day_bounds(day, tz)

    events_for_match = []
    if class_ids:
        events_for_match = list(
            ClassEvent.objects.filter(
                class_instance_id__in=class_ids,
                event_type__in=_SCHEDULABLE_EVENT_TYPES,
                start_time__gte=day_start,
                start_time__lte=day_end,
                start_time__isnull=False,
            ).select_related("class_instance", "class_instance__course", "class_instance__teacher")
        )

    event_by_class_start = {}
    for ev in events_for_match:
        local_start = ev.start_time.astimezone(tz)
        if local_start.date() != day:
            continue
        event_by_class_start[(ev.class_instance_id, _session_time_key(local_start.time().replace(microsecond=0)))] = ev

    matched_ids: set[str] = set()
    rows: list[dict] = []

    for session in sessions_today:
        cls = session.class_instance
        st = session.start_time.replace(microsecond=0)
        event = event_by_class_start.get((cls.id, _session_time_key(st)))
        if event:
            matched_ids.add(str(event.id))

        start_dt = datetime.combine(day, st).replace(tzinfo=tz)
        end_source = session.end_time if session.end_time else (datetime.combine(day, st) + timedelta(hours=1)).time()
        end_dt = datetime.combine(day, end_source).replace(tzinfo=tz)
        if event and event.start_time:
            start_dt = event.start_time.astimezone(tz)
            end_dt = event.end_time.astimezone(tz) if event.end_time else (start_dt + timedelta(hours=1))

        teacher = cls.teacher
        teacher_name = teacher.get_full_name() or teacher.email or str(teacher.pk)
        try:
            class_detail_url = reverse("admin:courses_class_detail", args=[cls.id])
        except NoReverseMatch:
            class_detail_url = ""

        rows.append(
            {
                "event_id": str(event.id) if event else f"session-{session.id}-{day.isoformat()}",
                "course_id": str(cls.course_id),
                "course_title": cls.course.title,
                "class_id": str(cls.id),
                "class_name": cls.name,
                "teacher_id": teacher.pk,
                "teacher_name": teacher_name,
                "start_at": start_dt,
                "end_at": end_dt,
                "status": "scheduled" if event else "not_scheduled",
                "event_title": event.title if event else "",
                "class_detail_url": class_detail_url,
            }
        )

    orphan_events = [ev for ev in events_for_match if str(ev.id) not in matched_ids]
    for event in orphan_events:
        cls = event.class_instance
        start_dt = event.start_time.astimezone(tz)
        if start_dt.date() != day:
            continue
        end_dt = event.end_time.astimezone(tz) if event.end_time else (start_dt + timedelta(hours=1))
        teacher = cls.teacher
        teacher_name = teacher.get_full_name() or teacher.email or str(teacher.pk)
        try:
            class_detail_url = reverse("admin:courses_class_detail", args=[cls.id])
        except NoReverseMatch:
            class_detail_url = ""

        rows.append(
            {
                "event_id": str(event.id),
                "course_id": str(cls.course_id),
                "course_title": cls.course.title,
                "class_id": str(cls.id),
                "class_name": cls.name,
                "teacher_id": teacher.pk,
                "teacher_name": teacher_name,
                "start_at": start_dt,
                "end_at": end_dt,
                "status": "event_only",
                "event_title": event.title,
                "class_detail_url": class_detail_url,
            }
        )

    rows.sort(key=lambda r: r["start_at"])
    return rows


def get_week_calendar_data(request, *, start_date_raw: str | None = None, tz_name: str | None = None) -> tuple[WeekMeta, list[dict]]:
    tz_name_resolved = _resolve_tz_name(request, tz_name)
    tz = ZoneInfo(tz_name_resolved)
    now_tz = timezone.now().astimezone(tz)
    week_start = _parse_week_start(start_date_raw, now_tz)
    week_end = week_start + timedelta(days=6)

    sessions_qs = (
        ClassSession.objects.filter(
            is_active=True,
            class_instance__is_active=True,
            # Mirror admin dashboard rules: exclude archived + self-paced courses.
            class_instance__course__status__in=["draft", "published"],
            class_instance__course__delivery_type__in=["live", "hybrid"],
        )
        .select_related(
            "class_instance",
            "class_instance__course",
            "class_instance__teacher",
        )
    )

    events: list[dict] = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        events.extend(_match_day_rows(day, tz, sessions_qs))

    return WeekMeta(week_start=week_start, week_end=week_end, tz_name=tz_name_resolved), events


def serialize_calendar_events(events: list[dict]) -> list[dict]:
    payload = []
    for e in events:
        payload.append(
            {
                "event_id": e["event_id"],
                "course_id": e["course_id"],
                "course_title": e["course_title"],
                "class_id": e["class_id"],
                "class_name": e["class_name"],
                "teacher_id": e["teacher_id"],
                "teacher_name": e["teacher_name"],
                "start_at": e["start_at"].isoformat(),
                "end_at": e["end_at"].isoformat(),
                "status": e["status"],
                "event_title": e["event_title"],
                "class_detail_url": e["class_detail_url"],
            }
        )
    return payload
