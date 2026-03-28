"""
Activate Django's per-request timezone for /admin/* from resolved calendar zone.

Resolution (see ``users.admin_calendar_tz.resolve_admin_calendar_timezone_name``):
logged-in user's ``admin_calendar_timezone`` if set, else
``get_calendar_timezone_fallback_name()`` (SystemSettings → TIME_ZONE).
"""

from zoneinfo import ZoneInfo

from django.utils import timezone

from settings.models import get_calendar_timezone_fallback_name
from users.admin_calendar_tz import resolve_admin_calendar_timezone_name


class AdminCalendarTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin"):
            self._activate(request)
        try:
            return self.get_response(request)
        finally:
            if request.path.startswith("/admin"):
                timezone.deactivate()

    def _activate(self, request):
        name = resolve_admin_calendar_timezone_name(request)
        try:
            timezone.activate(ZoneInfo(name))
        except Exception:
            timezone.activate(ZoneInfo(get_calendar_timezone_fallback_name()))
