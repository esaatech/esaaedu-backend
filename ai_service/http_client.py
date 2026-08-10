"""Shared httpx client for Pydantic AI providers.

Retries 429 / 5xx (and connect failures) with exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryAsyncTransport(httpx.AsyncBaseTransport):
    """Wrap AsyncHTTPTransport with limited retries for transient provider errors."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_base: float = 0.5,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._transport = transport or httpx.AsyncHTTPTransport()
        self._max_attempts = max(1, int(max_attempts))
        self._backoff_base = max(0.05, float(backoff_base))

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        last_exc: Optional[BaseException] = None
        response: Optional[httpx.Response] = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._transport.handle_async_request(request)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_exc = exc
                if attempt >= self._max_attempts:
                    raise
                delay = self._backoff_for(attempt, retry_after=None)
                logger.warning(
                    "ai_service.http retry attempt=%s/%s reason=%s delay=%.2fs",
                    attempt,
                    self._max_attempts,
                    exc.__class__.__name__,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code not in _RETRY_STATUS or attempt >= self._max_attempts:
                return response

            retry_after = _retry_after_seconds(response)
            # Drain body so the connection can be reused / closed cleanly.
            await response.aread()
            await response.aclose()

            delay = self._backoff_for(attempt, retry_after=retry_after)
            logger.warning(
                "ai_service.http retry attempt=%s/%s status=%s delay=%.2fs",
                attempt,
                self._max_attempts,
                response.status_code,
                delay,
            )
            await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc
        assert response is not None
        return response

    async def aclose(self) -> None:
        await self._transport.aclose()

    def _backoff_for(self, attempt: int, *, retry_after: Optional[float]) -> float:
        if retry_after is not None:
            return min(max(retry_after, 0.1), 30.0)
        return min(self._backoff_base * (2 ** (attempt - 1)), 8.0)


def _retry_after_seconds(response: httpx.Response) -> Optional[float]:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_retrying_http_client() -> httpx.AsyncClient:
    """Lazy singleton AsyncClient reused across provider Model instances."""
    global _client
    if _client is not None:
        return _client

    from ai_service.config import (
        http_connect_timeout_seconds,
        http_retry_attempts,
        http_timeout_seconds,
    )

    attempts = max(1, http_retry_attempts())
    timeout = httpx.Timeout(
        http_timeout_seconds(),
        connect=http_connect_timeout_seconds(),
    )
    _client = httpx.AsyncClient(
        timeout=timeout,
        transport=RetryAsyncTransport(max_attempts=attempts),
    )
    return _client


def reset_http_client() -> None:
    """Test helper to drop the singleton."""
    global _client
    _client = None
