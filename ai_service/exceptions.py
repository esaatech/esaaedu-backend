"""
AI Service errors for classification, logs, and Slack alerts (SLACK_ERROR_ALERTS).
"""

from __future__ import annotations

from typing import Optional


USER_FACING_AI_SERVICE_ERROR = (
    "We couldn't complete that AI request right now. Please try again."
)


class AIServiceGatewayError(Exception):
    """Raised when a model cannot be constructed (missing keys, bad provider, etc.)."""


class AIServiceError(Exception):
    """Internal AI Service failure with classification for logs and admin alerts."""

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


def configuration_error(message: str) -> AIServiceError:
    return AIServiceError(
        error_code="ai_not_configured",
        log_message=message,
        status_code=503,
        notify_admin=True,
    )


def rate_limited_error(message: str, *, cause: Optional[BaseException] = None) -> AIServiceError:
    """429 / quota exceeded — notify Slack for ops visibility."""
    return AIServiceError(
        error_code="rate_limited",
        log_message=message,
        status_code=429,
        notify_admin=True,
        cause=cause,
    )


def service_unavailable_error(
    message: str, *, cause: Optional[BaseException] = None
) -> AIServiceError:
    return AIServiceError(
        error_code="service_unavailable",
        log_message=message,
        status_code=503,
        notify_admin=True,
        cause=cause,
    )


def generation_failed_error(
    message: str, *, cause: Optional[BaseException] = None, notify_admin: bool = True
) -> AIServiceError:
    return AIServiceError(
        error_code="generation_failed",
        log_message=message,
        status_code=500,
        notify_admin=notify_admin,
        cause=cause,
    )


def from_exception(exc: BaseException) -> AIServiceError:
    """Normalize provider/HTTP/SDK exceptions into AIServiceError."""
    if isinstance(exc, AIServiceError):
        return exc

    if isinstance(exc, AIServiceGatewayError):
        return configuration_error(str(exc))

    # Avoid circular import at module load; timeout helper lives with runners.
    try:
        from ai_service.runners.run_helpers import AIServiceRunTimeout

        if isinstance(exc, AIServiceRunTimeout):
            return service_unavailable_error(str(exc), cause=exc)
    except ImportError:
        pass

    message = str(exc) or exc.__class__.__name__
    lower = message.lower()
    status = _extract_status_code(exc)

    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            return _from_http_status(int(exc.response.status_code), message, exc)
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return service_unavailable_error(message, cause=exc)
    except ImportError:
        pass

    if status == 429 or any(
        token in lower
        for token in (
            "429",
            "rate limit",
            "rate_limit",
            "ratelimit",
            "quota exceeded",
            "resource_exhausted",
            "resource exhausted",
            "too many requests",
        )
    ):
        return rate_limited_error(message, cause=exc)

    if status in (503, 504) or any(
        token in lower
        for token in ("unavailable", "deadline exceeded", "timed out", "timeout")
    ):
        return service_unavailable_error(message, cause=exc)

    if status in (401, 403) or any(
        token in lower for token in ("unauthorized", "permission denied", "forbidden", "api key")
    ):
        return AIServiceError(
            error_code="permission_denied",
            log_message=message,
            status_code=503,
            notify_admin=True,
            cause=exc,
        )

    if status is not None:
        return _from_http_status(status, message, exc)

    return generation_failed_error(message, cause=exc)


def _from_http_status(status: int, message: str, cause: BaseException) -> AIServiceError:
    if status == 429:
        return rate_limited_error(message, cause=cause)
    if status in (503, 504):
        return service_unavailable_error(message, cause=cause)
    if status in (401, 403):
        return AIServiceError(
            error_code="permission_denied",
            log_message=message,
            status_code=503,
            notify_admin=True,
            cause=cause,
        )
    return generation_failed_error(message, cause=cause)


def _extract_status_code(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "code", "status"):
        val = getattr(exc, attr, None)
        if val is None:
            continue
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if code is not None:
            try:
                return int(code)
            except (TypeError, ValueError):
                pass
    return None
