"""
Post-inbound SMS processing (AI routing, Conversation/Message, FCM).

Phase 1: stub. Phase 2: Cloud Task worker + LIFO/AI + admin path.
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def process_inbound_sms_routing(log_id: uuid.UUID) -> None:
    """Called after an inbound row is stored (inline or from Cloud Tasks)."""
    logger.info("Inbound SMS routing stub for log_id=%s (not yet implemented)", log_id)
