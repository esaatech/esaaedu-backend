"""Apply Twilio message status updates to SmsRoutingLog (outbound)."""

from __future__ import annotations

from django.utils import timezone

from communication.models import SmsRoutingLog


def apply_twilio_message_status(
    *,
    message_sid: str,
    status: str,
    error_code: str = "",
    error_message: str = "",
) -> int:
    """
    Update outbound log by Twilio MessageSid. Returns number of rows updated (0 or 1).
    """
    sid = (message_sid or "").strip()
    if not sid:
        return 0
    st = (status or "").strip().lower()[:24]
    code = (error_code or "").strip()[:32]
    msg = (error_message or "").strip()[:500]
    now = timezone.now()
    return SmsRoutingLog.objects.filter(
        twilio_message_sid=sid,
        direction=SmsRoutingLog.Direction.OUTBOUND,
    ).update(
        delivery_status=st,
        delivery_error_code=code,
        delivery_error_message=msg,
        delivery_updated_at=now,
    )
