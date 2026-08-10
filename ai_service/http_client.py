"""Shared httpx client for Pydantic AI providers (Phase 1).

HTTP transport retries can be tightened in Phase 5 (tenacity / AsyncTenacityTransport).
Phase 1 focuses on a shared client + sensible timeouts.
"""

from __future__ import annotations

from typing import Optional

import httpx

_client: Optional[httpx.AsyncClient] = None


def get_retrying_http_client() -> httpx.AsyncClient:
    """Lazy singleton AsyncClient reused across provider Model instances."""
    global _client
    if _client is not None:
        return _client

    _client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
    )
    return _client


def reset_http_client() -> None:
    """Test helper to drop the singleton."""
    global _client
    _client = None
