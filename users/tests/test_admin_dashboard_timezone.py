"""Regression tests for admin snapshot timetable timezone resolution."""

from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from zoneinfo import ZoneInfo

from courses.models import Class as ClassModel
from courses.models import ClassEvent, ClassSession, Course
from settings.models import SystemSettings
from users.admin_calendar_tz import resolve_admin_calendar_timezone_name
from users.templatetags.admin_dashboard import (
    _build_timetable_sections,
    _combine_today_slot,
    _format_time_range,
)

User = get_user_model()


class AdminDashboardCalendarTzTests(TestCase):
    def test_combine_slot_formats_wall_clock_in_zone(self):
        """Naive session times are interpreted as local wall clock in the calendar zone."""
        cal_tz = ZoneInfo("America/New_York")
        today = date(2026, 3, 27)
        start = _combine_today_slot(today, time(18, 15), cal_tz)
        end = _combine_today_slot(today, time(19, 15), cal_tz)
        label = _format_time_range(start, end)
        self.assertIn("06:15 PM", label)
        self.assertIn("07:15 PM", label)

    @override_settings(TIME_ZONE="UTC")
    def test_resolve_uses_system_settings_when_no_user_tz(self):
        SystemSettings.objects.create(calendar_timezone="America/Chicago")
        request = RequestFactory().get("/admin/")
        self.assertEqual(
            resolve_admin_calendar_timezone_name(request), "America/Chicago"
        )

    @override_settings(TIME_ZONE="UTC")
    def test_resolve_uses_time_zone_when_no_system_settings_row(self):
        request = RequestFactory().get("/admin/")
        self.assertEqual(resolve_admin_calendar_timezone_name(request), "UTC")

    @override_settings(TIME_ZONE="UTC")
    def test_admin_dashboard_snapshot_timezone_matches_resolver(self):
        SystemSettings.objects.create(calendar_timezone="America/Denver")
        request = RequestFactory().get("/admin/")
        tpl = Template(
            "{% load admin_dashboard %}"
            "{% admin_dashboard_snapshot as snapshot %}"
            "{{ snapshot.timezone_name }}"
        )
        out = tpl.render(Context({"request": request})).strip()
        self.assertEqual(out, "America/Denver")


class AdminTimetableOrphanDedupTests(TestCase):
    def test_single_session_timetable_hidden_when_unmatched_event_same_day(self):
        """
        When weekly ClassSession times do not match ClassEvent local start (no key match),
        the dashboard used to show two rows. With exactly one session on that weekday,
        keep the ClassEvent row only.
        """
        cal_tz = ZoneInfo("America/New_York")
        today = date(2026, 3, 24)
        teacher = User.objects.create_user(
            firebase_uid="dedup_teacher_uid",
            email="dedup_teacher@test.com",
            username="dedup_teacher@test.com",
            password="pass",
            role="teacher",
        )
        course = Course.objects.create(
            title="Dedup Course",
            description="x",
            long_description="x",
            age_range="6-10",
            teacher=teacher,
            category="CS",
            price=1,
            is_free=False,
        )
        klass = ClassModel.objects.create(
            name="Section A",
            course=course,
            teacher=teacher,
        )
        ClassSession.objects.create(
            class_instance=klass,
            day_of_week=1,
            start_time=time(17, 0),
            end_time=time(18, 0),
            session_number=1,
            is_active=True,
        )
        utc = ZoneInfo("UTC")
        start_utc = datetime(2026, 3, 24, 23, 0, tzinfo=utc)
        end_utc = datetime(2026, 3, 25, 0, 0, tzinfo=utc)
        ClassEvent.objects.create(
            class_instance=klass,
            title="Live slot",
            event_type="meeting",
            start_time=start_utc,
            end_time=end_utc,
        )

        cal_now = datetime(2026, 3, 24, 22, 0, tzinfo=cal_tz)
        tt = _build_timetable_sections(cal_now, today, 1, cal_tz)
        all_rows = tt["ongoing"] + tt["upcoming"] + tt["past"]
        self.assertEqual(len(all_rows), 1)
        self.assertTrue(all_rows[0]["scheduled"])
        self.assertIn("07:00 PM", all_rows[0]["time_range"])
