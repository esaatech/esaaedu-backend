"""Admin calendar timezone middleware and resolver precedence."""

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from backend.admin_calendar_timezone_middleware import AdminCalendarTimezoneMiddleware
from settings.models import SystemSettings
from users.admin_calendar_tz import resolve_admin_calendar_timezone_name
from users.models import User


class AdminCalendarTimezoneMiddlewareTests(TestCase):
    @override_settings(TIME_ZONE="America/Chicago")
    def test_fallback_uses_time_zone_when_no_system_settings_row(self):
        """No SystemSettings row: get_calendar_timezone_fallback_name uses TIME_ZONE."""
        factory = RequestFactory()
        request = factory.get("/admin/")

        def get_response(req):
            self.assertEqual(timezone.get_current_timezone_name(), "America/Chicago")
            return HttpResponse("ok")

        AdminCalendarTimezoneMiddleware(get_response)(request)

    def test_non_admin_path_untouched(self):
        factory = RequestFactory()
        request = factory.get("/api/courses/")

        def get_response(req):
            self.assertEqual(timezone.get_current_timezone_name(), "UTC")
            return HttpResponse("ok")

        AdminCalendarTimezoneMiddleware(get_response)(request)


@override_settings(TIME_ZONE="UTC")
class AdminCalendarUserPreferenceTests(TestCase):
    """Saved User.admin_calendar_timezone wins over SystemSettings."""

    def test_user_timezone_used_in_middleware(self):
        SystemSettings.objects.create(calendar_timezone="America/Mexico_City")
        user = User.objects.create_user(
            firebase_uid="admin_tz_pref",
            email="admin_tz_pref@test.com",
            username="admin_tz_pref@test.com",
            password="pass",
            role=User.Role.ADMIN,
        )
        user.admin_calendar_timezone = "America/New_York"
        user.save(update_fields=["admin_calendar_timezone"])

        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = user

        def get_response(req):
            self.assertEqual(timezone.get_current_timezone_name(), "America/New_York")
            return HttpResponse("ok")

        AdminCalendarTimezoneMiddleware(get_response)(request)

    def test_resolve_returns_user_timezone_over_system_settings(self):
        SystemSettings.objects.create(calendar_timezone="America/Vancouver")
        user = User.objects.create_user(
            firebase_uid="resolve_uid",
            email="resolve@test.com",
            username="resolve@test.com",
            password="pass",
            role=User.Role.ADMIN,
        )
        user.admin_calendar_timezone = "America/Toronto"
        user.save(update_fields=["admin_calendar_timezone"])

        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = user
        self.assertEqual(resolve_admin_calendar_timezone_name(request), "America/Toronto")


@override_settings(TIME_ZONE="UTC")
class AdminCalendarTimezoneMiddlewareDBTests(TestCase):
    """SystemSettings used when user has no admin_calendar_timezone."""

    def test_system_settings_used_for_fallback(self):
        SystemSettings.objects.create(calendar_timezone="America/Mexico_City")
        factory = RequestFactory()
        request = factory.get("/admin/")

        def get_response(req):
            self.assertEqual(
                timezone.get_current_timezone_name(), "America/Mexico_City"
            )
            return HttpResponse("ok")

        AdminCalendarTimezoneMiddleware(get_response)(request)
