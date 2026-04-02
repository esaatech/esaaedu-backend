"""
Post-inbound SMS processing (AI routing, Conversation/Message, FCM).

Correlates inbound SMS to the latest qualifying outbound (same thread + optional max age).
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.conf import settings

from communication.models import SmsRoutingLog

logger = logging.getLogger(__name__)


def _reply_max_age_seconds() -> int:
    raw = getattr(settings, "COMMUNICATION_SMS_REPLY_MAX_AGE_SECONDS", 3600)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 3600
    return max(0, n)


def process_inbound_sms_routing(log_id: uuid.UUID) -> None:
    """Match inbound to latest outbound on same phones within COMMUNICATION_SMS_REPLY_MAX_AGE_SECONDS."""
    try:
        log = SmsRoutingLog.objects.get(
            pk=log_id,
            direction=SmsRoutingLog.Direction.INBOUND,
        )
    except SmsRoutingLog.DoesNotExist:
        logger.warning("Inbound SMS routing: log %s not found or not inbound", log_id)
        return

    if log.inbound_routing not in (
        None,
        "",
        SmsRoutingLog.InboundRouting.PENDING,
    ):
        return

    # DB truth for created_at (avoids stale in-memory instance).
    log.refresh_from_db(fields=["created_at", "student_phone", "twilio_number", "inbound_routing"])

    max_age = _reply_max_age_seconds()
    cutoff = log.created_at - timedelta(seconds=max_age) if max_age > 0 else None

    qs = SmsRoutingLog.objects.filter(
        direction=SmsRoutingLog.Direction.OUTBOUND,
        student_phone=log.student_phone,
        twilio_number=log.twilio_number,
        created_at__lte=log.created_at,
    )
    if max_age > 0:
        qs = qs.filter(created_at__gte=cutoff)

    prior = qs.order_by("-created_at").first()

    # Defense in depth (must match queryset; catches ORM/DB edge cases).
    if prior is not None and max_age > 0 and cutoff is not None:
        if prior.created_at < cutoff:
            prior = None

    if prior:
        SmsRoutingLog.objects.filter(pk=log_id).update(
            teacher_id=prior.teacher_id,
            course_id=prior.course_id,
            course_class_id=prior.course_class_id,
            related_outbound_id=prior.id,
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        logger.info(
            "Inbound SMS correlated log_id=%s -> outbound_id=%s twilio_sid=%s max_age_s=%s inbound_at=%s",
            log_id,
            prior.id,
            prior.twilio_message_sid,
            max_age,
            log.created_at,
        )
    else:
        SmsRoutingLog.objects.filter(pk=log_id).update(
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
            teacher_id=None,
            course_id=None,
            course_class_id=None,
            related_outbound_id=None,
        )
        logger.info(
            "Inbound SMS generic_admin log_id=%s max_age_s=%s inbound_at=%s cutoff=%s phones=%s/%s",
            log_id,
            max_age,
            log.created_at,
            cutoff,
            log.student_phone,
            log.twilio_number,
        )
