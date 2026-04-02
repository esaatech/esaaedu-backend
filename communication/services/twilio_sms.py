"""Low-level Twilio REST + webhook signature checks."""

from __future__ import annotations

import logging

from django.conf import settings
from twilio.request_validator import RequestValidator
from twilio.rest import Client

logger = logging.getLogger(__name__)


class TwilioNotConfiguredError(RuntimeError):
    """Twilio credentials or from-number missing."""


def get_twilio_credentials() -> tuple[str, str, str]:
    sid = (getattr(settings, "TWILIO_ACCOUNT_SID", None) or "").strip()
    token = (getattr(settings, "TWILIO_AUTH_TOKEN", None) or "").strip()
    from_number = (getattr(settings, "TWILIO_FROM_NUMBER", None) or "").strip()
    if not sid or not token or not from_number:
        raise TwilioNotConfiguredError(
            "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER must be set"
        )
    return sid, token, from_number


def validate_inbound_webhook_signature(request) -> bool:
    """Return True if X-Twilio-Signature matches this request."""
    try:
        _, token, _ = get_twilio_credentials()
    except TwilioNotConfiguredError:
        logger.warning("Twilio webhook received but Twilio is not configured")
        return False

    validator = RequestValidator(token)
    url = request.build_absolute_uri()
    params = request.POST.dict()
    signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "") or ""
    if not signature:
        logger.warning("Twilio webhook missing X-Twilio-Signature header")
        return False
    if not validator.validate(url, params, signature):
        logger.warning(
            "Twilio webhook signature invalid (check TWILIO_AUTH_TOKEN and that "
            "SECURE_PROXY_SSL_HEADER matches your proxy, e.g. ngrok). url_used=%r",
            url,
        )
        return False
    return True


def send_sms(*, to_e164: str, body: str) -> str:
    """
    Send SMS via Twilio. Returns Message SID.
    """
    sid, token, from_number = get_twilio_credentials()
    client = Client(sid, token)
    msg = client.messages.create(to=to_e164, from_=from_number, body=body)
    return msg.sid
