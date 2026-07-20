"""
Generate ClassEvents from an EnrollmentSchedule cadence for self-paced courses.
"""
from __future__ import annotations

from datetime import datetime, timedelta, time as dtime, date
from typing import List, Tuple

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from courses.models import Class, ClassEvent, Lesson
from student.models import EnrollmentSchedule, StudentLessonProgress


LESSON_TYPE_TO_EVENT = {
    'live_class': 'live',
    'text_lesson': 'text',
    'video_audio': 'video',
    'tutorx': 'interactive',
}

MAX_LOOKAHEAD_DAYS = 366 * 2


def _lesson_event_type(lesson: Lesson) -> str:
    return LESSON_TYPE_TO_EVENT.get(lesson.type, 'text')


def _iter_repeating_slot_dates(
    schedule: EnrollmentSchedule,
    start_date: date,
    lesson_count: int,
) -> List[date]:
    if lesson_count <= 0:
        return []
    weekdays = schedule.weekdays or []
    if schedule.frequency == 'weekly' and not weekdays:
        return []

    dates: List[date] = []
    for offset in range(MAX_LOOKAHEAD_DAYS):
        if len(dates) >= lesson_count:
            break
        day = start_date + timedelta(days=offset)
        if schedule.frequency == 'daily':
            dates.append(day)
        elif schedule.frequency == 'weekly' and day.weekday() in weekdays:
            dates.append(day)
    return dates


def _parse_custom_slots(schedule: EnrollmentSchedule) -> List[Tuple[date, dtime, dtime]]:
    """Return sorted (date, start, end) from custom_slots."""
    parsed = []
    for slot in schedule.custom_slots or []:
        d = parse_date(str(slot.get('date', '')))
        st = parse_time(str(slot.get('start_time', '')))
        et = parse_time(str(slot.get('end_time', '')))
        if d and st and et:
            parsed.append((d, st, et))
    parsed.sort(key=lambda x: (x[0], x[1]))
    return parsed


def get_or_create_personal_class(schedule: EnrollmentSchedule) -> Class:
    enrollment = schedule.enrollment
    course = enrollment.course
    student_user = enrollment.student_profile.user
    teacher = course.teacher

    if schedule.class_instance_id:
        class_instance = schedule.class_instance
        if student_user not in class_instance.students.all():
            class_instance.students.add(student_user)
        return class_instance

    child_name = (
        f"{enrollment.student_profile.child_first_name or ''} "
        f"{enrollment.student_profile.child_last_name or ''}"
    ).strip() or student_user.get_full_name() or student_user.email
    class_name = f"{child_name} — Self-paced"

    class_instance = Class.objects.create(
        name=class_name[:100],
        description=f"Personal self-paced schedule for {child_name}",
        course=course,
        teacher=teacher,
        max_capacity=1,
        is_active=True,
    )
    class_instance.students.add(student_user)
    schedule.class_instance = class_instance
    schedule.save(update_fields=['class_instance', 'updated_at'])
    return class_instance


def _incomplete_lessons(enrollment) -> List[Lesson]:
    completed_ids = set(
        StudentLessonProgress.objects.filter(
            enrollment=enrollment,
            status='completed',
        ).values_list('lesson_id', flat=True)
    )
    lessons = list(enrollment.course.lessons.order_by('order'))
    return [lesson for lesson in lessons if lesson.id not in completed_ids]


def _aware_range(day: date, start: dtime, end: dtime, tz, all_day: bool):
    if all_day:
        start_dt = timezone.make_aware(datetime.combine(day, dtime.min), tz)
        end_dt = timezone.make_aware(datetime.combine(day, dtime(23, 59, 59)), tz)
        return start_dt, end_dt
    start_dt = timezone.make_aware(datetime.combine(day, start), tz)
    end_dt = timezone.make_aware(datetime.combine(day, end), tz)
    return start_dt, end_dt


@transaction.atomic
def regenerate_schedule_events(schedule: EnrollmentSchedule) -> int:
    """
    Rebuild upcoming schedule-generated ClassEvents.
    - daily / weekly+repeat_weekly: place lessons on matching days until course ends
    - weekly+not repeat: place lessons on custom_slots in order
    """
    schedule.full_clean()
    class_instance = get_or_create_personal_class(schedule)
    tz = timezone.get_current_timezone()
    now = timezone.now()
    today = timezone.localdate()

    ClassEvent.objects.filter(
        class_instance=class_instance,
        is_schedule_generated=True,
        start_time__gte=now,
    ).delete()

    incomplete = _incomplete_lessons(schedule.enrollment)
    if not incomplete:
        return 0

    created = 0
    use_custom = (
        schedule.frequency == 'weekly'
        and not schedule.repeat_weekly
    )

    if use_custom:
        slots = _parse_custom_slots(schedule)
        # only future/today slots
        slots = [(d, st, et) for (d, st, et) in slots if d >= today]
        for lesson, (day, st, et) in zip(incomplete, slots):
            start_dt, end_dt = _aware_range(day, st, et, tz, all_day=False)
            ClassEvent.objects.create(
                title=lesson.title,
                description=lesson.description or '',
                class_instance=class_instance,
                lesson=lesson,
                event_type='lesson',
                lesson_type=_lesson_event_type(lesson),
                start_time=start_dt,
                end_time=end_dt,
                all_day=False,
                is_schedule_generated=True,
            )
            created += 1
        return created

    # Repeating cadence (daily or weekly pattern)
    slot_dates = _iter_repeating_slot_dates(schedule, today, len(incomplete))
    all_day = bool(schedule.all_day or not schedule.start_time)
    start_t = schedule.start_time or dtime.min
    end_t = schedule.end_time or dtime(23, 59, 59)

    for day, lesson in zip(slot_dates, incomplete):
        start_dt, end_dt = _aware_range(day, start_t, end_t, tz, all_day)
        ClassEvent.objects.create(
            title=lesson.title,
            description=lesson.description or '',
            class_instance=class_instance,
            lesson=lesson,
            event_type='lesson',
            lesson_type=_lesson_event_type(lesson),
            start_time=start_dt,
            end_time=end_dt,
            all_day=all_day,
            is_schedule_generated=True,
        )
        created += 1

    return created
