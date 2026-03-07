"""
Validators for user profile fields.
"""
from django.core.exceptions import ValidationError


def validate_iana_timezone(value):
    """
    Validate that value is a valid IANA timezone name (e.g. Africa/Lagos, Asia/Shanghai).
    Empty string is allowed (optional field).
    """
    if not value or not value.strip():
        return
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(value.strip())
    except Exception:
        raise ValidationError(
            '%(value)s is not a valid IANA timezone (e.g. Africa/Lagos, Asia/Shanghai).',
            code='invalid_timezone',
            params={'value': value},
        )


def get_all_timezone_choices():
    """
    Return all IANA timezone names as choices for dropdowns, sorted alphabetically.
    Includes e.g. America/Mexico_City, Africa/Lagos, etc. Cached at module load.
    """
    from zoneinfo import available_timezones
    return [('', '---------')] + [(tz, tz) for tz in sorted(available_timezones())]


# Cached list of all timezone choices (used by admin and API)
ALL_TIMEZONE_CHOICES = None


def get_all_timezone_choices_cached():
    """Return all timezone choices, building once and reusing."""
    global ALL_TIMEZONE_CHOICES
    if ALL_TIMEZONE_CHOICES is None:
        ALL_TIMEZONE_CHOICES = get_all_timezone_choices()
    return ALL_TIMEZONE_CHOICES


# Shorter list for contexts that need a minimal dropdown (e.g. mobile). Admin uses full list.
COMMON_TIMEZONES = [
    ('Africa/Cairo', 'Africa/Cairo'),
    ('Africa/Johannesburg', 'Africa/Johannesburg'),
    ('Africa/Lagos', 'Africa/Lagos'),
    ('America/New_York', 'America/New_York'),
    ('America/Los_Angeles', 'America/Los_Angeles'),
    ('America/Chicago', 'America/Chicago'),
    ('America/Mexico_City', 'America/Mexico_City'),
    ('America/Toronto', 'America/Toronto'),
    ('America/Sao_Paulo', 'America/Sao_Paulo'),
    ('Asia/Dubai', 'Asia/Dubai'),
    ('Asia/Shanghai', 'Asia/Shanghai'),
    ('Asia/Tokyo', 'Asia/Tokyo'),
    ('Asia/Kolkata', 'Asia/Kolkata'),
    ('Asia/Singapore', 'Asia/Singapore'),
    ('Australia/Sydney', 'Australia/Sydney'),
    ('Europe/London', 'Europe/London'),
    ('Europe/Paris', 'Europe/Paris'),
    ('Europe/Berlin', 'Europe/Berlin'),
    ('UTC', 'UTC'),
]
