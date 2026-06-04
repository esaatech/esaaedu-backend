"""
Application error alerts — log always, optional throttled Slack to SLACK_ERROR_ALERTS.

Use notify_error_alert() for any backend error worth paging ops.
AI endpoints use notify_ai_failure() (thin wrapper with source="AI").
"""
from __future__ import annotations

import logging
from typing import Any

from decouple import config
from django.core.cache import cache

logger = logging.getLogger(__name__)

ERROR_ALERT_THROTTLE_SECONDS = 15 * 60


def _error_alerts_channel() -> str:
    return (config("SLACK_ERROR_ALERTS", default="") or "").strip()


def _user_label(user: Any) -> str:
    if user is None:
        return "unknown"
    email = getattr(user, "email", None) or ""
    user_id = getattr(user, "id", None) or getattr(user, "pk", None)
    role = getattr(user, "role", None) or ""
    parts = [p for p in (email, f"id={user_id}" if user_id else "", role) if p]
    return " ".join(parts) if parts else "unknown"


def _should_notify_slack(error_code: str) -> bool:
    cache_key = f"error_alert:{error_code}"
    try:
        if cache.get(cache_key):
            return False
        cache.set(cache_key, True, timeout=ERROR_ALERT_THROTTLE_SECONDS)
        return True
    except Exception as cache_exc:
        logger.warning(
            "Error alert throttle cache unavailable; sending Slack anyway: %s",
            cache_exc,
        )
        return True


def notify_error_alert(
    *,
    error_code: str,
    log_message: str,
    context: str,
    source: str = "Application",
    user=None,
    endpoint: str = "",
    notify_slack: bool = True,
) -> None:
    """
    Log an error and optionally send a throttled Slack alert to SLACK_ERROR_ALERTS.
    Never raises — alert failures must not break the user request.
    """
    user_label = _user_label(user)
    logger.error(
        "%s error [%s] context=%s endpoint=%s user=%s detail=%s",
        source,
        error_code,
        context,
        endpoint or "n/a",
        user_label,
        log_message,
        exc_info=False,
    )

    if not notify_slack or not _should_notify_slack(error_code):
        return

    alerts_channel = _error_alerts_channel()
    if not alerts_channel:
        logger.warning(
            "SLACK_ERROR_ALERTS not set; skipping Slack alert for [%s]",
            error_code,
        )
        return

    slack_body = (
        f"*Source:* {source}\n"
        f"*Error code:* `{error_code}`\n"
        f"*Context:* {context}\n"
        f"*Endpoint:* {endpoint or 'n/a'}\n"
        f"*User:* {user_label}\n"
        f"*Detail:*\n```{log_message[:2000]}```"
    )

    try:
        from slack_notifications import send_system_notification

        send_system_notification(
            title=f"{source} Error: {error_code}",
            message=slack_body,
            color="#e01e5a",
            channel=alerts_channel,
        )
    except Exception as slack_exc:
        logger.warning("Failed to send error Slack alert: %s", slack_exc, exc_info=True)


def notify_ai_failure(
    *,
    error_code: str,
    log_message: str,
    context: str,
    user=None,
    endpoint: str = "",
    notify_admin: bool = True,
) -> None:
    """AI/Gemini failures — routes to SLACK_ERROR_ALERTS via notify_error_alert."""
    notify_error_alert(
        error_code=error_code,
        log_message=log_message,
        context=context,
        source="AI",
        user=user,
        endpoint=endpoint,
        notify_slack=notify_admin,
    )
