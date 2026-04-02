"""
Post-inbound SMS processing (AI routing, Conversation/Message, FCM).

Correlates inbound SMS to the latest outbound to the same student/from number (reply thread).
"""

from __future__ import annotations

import logging
import uuid

from communication.models import SmsRoutingLog

logger = logging.getLogger(__name__)


def process_inbound_sms_routing(log_id: uuid.UUID) -> None:
    """Match inbound to prior outbound on same student_phone + our twilio_number; else generic_admin."""
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

    prior = (
        SmsRoutingLog.objects.filter(
            direction=SmsRoutingLog.Direction.OUTBOUND,
            student_phone=log.student_phone,
            twilio_number=log.twilio_number,
        )
        .order_by("-created_at")
        .first()
    )

    if prior:
        SmsRoutingLog.objects.filter(pk=log_id).update(
            teacher_id=prior.teacher_id,
            course_id=prior.course_id,
            course_class_id=prior.course_class_id,
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        logger.info("Inbound SMS log_id=%s correlated to outbound sid=%s", log_id, prior.twilio_message_sid)
    else:
        SmsRoutingLog.objects.filter(pk=log_id).update(
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        logger.info("Inbound SMS log_id=%s marked generic_admin (no prior outbound match)", log_id)
