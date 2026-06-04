"""
DRF response helper for AI endpoints — generic user message, detailed logs + admin alerts.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.response import Response

from error_alerts import notify_ai_failure
from ai.exceptions import GeminiServiceError, USER_FACING_AI_ERROR, from_exception

logger = logging.getLogger(__name__)


def ai_error_response(
    exc: BaseException,
    *,
    context: str = "AI generation",
    user: Any = None,
    endpoint: str = "",
) -> Response:
    """
    Return a user-safe error response for AI failures.

    - ValueError: pass through as 400 (user-fixable validation)
    - DEBUG=True: return technical error + error_code (for local testing)
    - DEBUG=False: return generic USER_FACING_AI_ERROR only
    - Always logs and sends throttled Slack alert when configured
    """
    if isinstance(exc, ValueError):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    gemini_exc = from_exception(exc)

    try:
        notify_ai_failure(
            error_code=gemini_exc.error_code,
            log_message=gemini_exc.log_message,
            context=context,
            user=user,
            endpoint=endpoint,
            notify_admin=gemini_exc.notify_admin,
        )
    except Exception as notify_exc:
        logger.warning("AI failure notify step failed: %s", notify_exc, exc_info=True)

    if isinstance(exc, ImproperlyConfigured) or not isinstance(exc, GeminiServiceError):
        logger.exception("AI failure in %s", context)

    http_status = gemini_exc.status_code
    if http_status == 429:
        drf_status = status.HTTP_429_TOO_MANY_REQUESTS
    elif http_status == 502:
        drf_status = status.HTTP_502_BAD_GATEWAY
    elif http_status == 503:
        drf_status = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        drf_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    if settings.DEBUG:
        return Response(
            {
                "error": gemini_exc.log_message,
                "error_code": gemini_exc.error_code,
            },
            status=drf_status,
        )

    return Response({"error": USER_FACING_AI_ERROR}, status=drf_status)
