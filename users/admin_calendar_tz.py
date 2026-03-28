"""
Admin calendar IANA timezone resolution for /admin (middleware + dashboard snapshot).

Precedence: logged-in user's admin_calendar_timezone (if set and valid)
→ get_calendar_timezone_fallback_name() (SystemSettings.calendar_timezone, else TIME_ZONE).
"""

from zoneinfo import available_timezones

from settings.models import get_calendar_timezone_fallback_name

_MAX_TZ_LEN = 120


def _is_valid_iana_name(name: str) -> bool:
    s = name.strip()
    return bool(s and len(s) <= _MAX_TZ_LEN and s in available_timezones())


def resolve_admin_calendar_timezone_name(request) -> str:
    """
    Return the effective IANA timezone name for admin calendar UI for this request.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        raw = getattr(user, "admin_calendar_timezone", None) or ""
        tz_name = str(raw).strip()
        if tz_name and _is_valid_iana_name(tz_name):
            return tz_name.strip()

    return get_calendar_timezone_fallback_name()
