"""
Gemini / Vertex AI error types for internal classification and admin alerts.

End users always see USER_FACING_AI_ERROR — never raw Google API messages.
"""
from __future__ import annotations

from typing import Optional

from django.core.exceptions import ImproperlyConfigured
from google.api_core import exceptions as google_exceptions

USER_FACING_AI_ERROR = (
    "We couldn't generate content right now. Please try again."
)


class GeminiServiceError(Exception):
    """Internal Gemini failure with classification for logs and admin alerts."""

    def __init__(
        self,
        *,
        error_code: str,
        log_message: str,
        status_code: int = 500,
        notify_admin: bool = True,
        cause: Optional[BaseException] = None,
        slack_notified: bool = False,
    ):
        self.error_code = error_code
        self.log_message = log_message
        self.status_code = status_code
        self.notify_admin = notify_admin
        self.slack_notified = slack_notified
        super().__init__(log_message)
        self.__cause__ = cause


def configuration_error(message: str) -> GeminiServiceError:
    return GeminiServiceError(
        error_code="ai_not_configured",
        log_message=message,
        status_code=503,
        notify_admin=True,
    )


def invalid_response_error(message: str, *, cause: Optional[BaseException] = None) -> GeminiServiceError:
    return GeminiServiceError(
        error_code="invalid_response",
        log_message=message,
        status_code=502,
        notify_admin=False,
        cause=cause,
    )


def from_google_api_error(exc: google_exceptions.GoogleAPIError) -> GeminiServiceError:
    """Map a Google API error to an internal GeminiServiceError."""
    message = str(exc)
    lower = message.lower()
    code = getattr(exc, "code", None)
    code_int = int(code) if code is not None else None

    if isinstance(exc, google_exceptions.NotFound) or code_int == 404 or "not found" in lower:
        return GeminiServiceError(
            error_code="model_unavailable",
            log_message=message,
            status_code=503,
            notify_admin=True,
            cause=exc,
        )

    if isinstance(exc, google_exceptions.PermissionDenied) or code_int == 403:
        return GeminiServiceError(
            error_code="permission_denied",
            log_message=message,
            status_code=503,
            notify_admin=True,
            cause=exc,
        )

    if isinstance(exc, google_exceptions.ResourceExhausted) or code_int == 429:
        return GeminiServiceError(
            error_code="rate_limited",
            log_message=message,
            status_code=429,
            notify_admin=False,
            cause=exc,
        )

    if (
        isinstance(exc, (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded))
        or code_int in (503, 504)
        or "deadline exceeded" in lower
        or "unavailable" in lower
    ):
        return GeminiServiceError(
            error_code="service_unavailable",
            log_message=message,
            status_code=503,
            notify_admin=False,
            cause=exc,
        )

    return GeminiServiceError(
        error_code="generation_failed",
        log_message=message,
        status_code=500,
        notify_admin=True,
        cause=exc,
    )


def from_exception(exc: BaseException) -> GeminiServiceError:
    """Normalize any exception into a GeminiServiceError."""
    if isinstance(exc, GeminiServiceError):
        return exc

    if isinstance(exc, ImproperlyConfigured):
        return configuration_error(str(exc))

    if isinstance(exc, google_exceptions.GoogleAPIError):
        return from_google_api_error(exc)

    if isinstance(exc, ValueError) and "invalid json response from ai" in str(exc).lower():
        return invalid_response_error(str(exc), cause=exc)

    return GeminiServiceError(
        error_code="generation_failed",
        log_message=str(exc),
        status_code=500,
        notify_admin=True,
        cause=exc if isinstance(exc, Exception) else None,
    )
