"""Slack + log helpers for ai_service runners."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ai_service.exceptions import AIServiceError, from_exception

logger = logging.getLogger(__name__)


def log_run_model(
    *,
    service: str,
    provider: str,
    model_id: str,
    temperature: Optional[float] = None,
    extra: str = "",
) -> None:
    """INFO log every time an AI Service run uses a model (stdout via Django logging)."""
    temp = f" temperature={temperature}" if temperature is not None else ""
    suffix = f" {extra}" if extra else ""
    logger.info(
        "ai_service.run service=%s provider=%s model=%s%s%s",
        service,
        provider,
        model_id,
        temp,
        suffix,
    )


def notify_and_classify(
    exc: BaseException,
    *,
    context: str,
    user: Any = None,
    endpoint: str = "",
) -> AIServiceError:
    """
    Classify exception, log, and send throttled Slack alert to SLACK_ERROR_ALERTS.
    Marks slack_notified on the returned AIServiceError when alert ran (or was skipped intentionally).
    """
    ai_exc = from_exception(exc)
    if ai_exc.slack_notified:
        return ai_exc

    try:
        from error_alerts import notify_ai_failure

        notify_ai_failure(
            error_code=ai_exc.error_code,
            log_message=ai_exc.log_message,
            context=context,
            user=user,
            endpoint=endpoint,
            notify_admin=ai_exc.notify_admin,
        )
        ai_exc.slack_notified = True
    except Exception as notify_exc:
        logger.warning(
            "ai_service Slack notify failed context=%s: %s",
            context,
            notify_exc,
            exc_info=True,
        )
    return ai_exc
