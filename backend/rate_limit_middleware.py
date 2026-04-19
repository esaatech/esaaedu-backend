"""
Global HTTP rate limiting (per client IP) using Django cache.

Skips exempt path prefixes (webhooks, health, static). On cache errors, fails
open so Redis outages do not take the API offline.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)

try:
    from django_redis.exceptions import ConnectionInterrupted
except ImportError:  # pragma: no cover
    ConnectionInterrupted = None  # type: ignore


def _cache_unreachable(exc: BaseException) -> bool:
    """True when Redis/django-redis cannot be reached (DNS, network, down)."""
    if ConnectionInterrupted is not None and isinstance(
        exc, ConnectionInterrupted
    ):
        return True
    try:
        from redis.exceptions import ConnectionError as RedisConnectionError
        from redis.exceptions import TimeoutError as RedisTimeoutError
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, (RedisConnectionError, RedisTimeoutError))


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "unknown"


def path_is_exempt(path: str) -> bool:
    prefixes = getattr(settings, "RATE_LIMIT_EXEMPT_PATH_PREFIXES", ())
    for prefix in prefixes:
        if path.startswith(prefix):
            return True
    return False


def fixed_window_allow(
    cache_key: str, limit: int, window_seconds: int
) -> bool:
    """
    Fixed-window counter. First request creates the key; further requests
    increment until limit is reached (same pattern as student IDE explain).
    """
    if limit <= 0:
        return True
    try:
        if cache.add(cache_key, 1, timeout=window_seconds):
            return True
        n = cache.get(cache_key, 0) or 0
        if n >= limit:
            return False
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=window_seconds)
        return True
    except Exception as e:
        if _cache_unreachable(e):
            # Unreachable Redis: fail open without log spam.
            logger.debug(
                "Rate limit skipped (cache unreachable, allowing request): %s",
                e,
            )
            return True
        logger.warning(
            "Rate limit cache error (failing open): %s", e, exc_info=True
        )
        return True


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return self.get_response(request)

        path = request.path
        if path_is_exempt(path):
            return self.get_response(request)

        limit = int(getattr(settings, "RATE_LIMIT_REQUESTS_PER_WINDOW", 500))
        window = int(getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60))
        identifier = get_client_ip(request)
        cache_key = f"rl:mw:v1:ip:{identifier}"

        if not fixed_window_allow(cache_key, limit, window):
            response = JsonResponse(
                {
                    "error": "Too many requests",
                    "detail": "Rate limit exceeded. Try again later.",
                },
                status=429,
            )
            response["Retry-After"] = str(window)
            return response

        return self.get_response(request)
