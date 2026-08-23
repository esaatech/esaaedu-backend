"""Shared helpers for AI Service runners (timeouts, ModelSettings)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any, Optional

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


class AIServiceRunTimeout(TimeoutError):
    """Raised when an agent.run exceeds the wall-clock deadline."""


def request_model_settings(*, temperature: float) -> Any:
    """
    Build pydantic-ai ModelSettings with temperature + per-request timeout.
    Falls back to a plain dict if ModelSettings import fails.
    """
    from ai_service.config import http_timeout_seconds

    request_timeout = http_timeout_seconds()
    try:
        from pydantic_ai.settings import ModelSettings

        return ModelSettings(temperature=temperature, timeout=request_timeout)
    except Exception:
        return {"temperature": temperature, "timeout": request_timeout}


def _ensure_ai_loop() -> asyncio.AbstractEventLoop:
    """
    One process-wide asyncio loop for pydantic-ai + the shared httpx AsyncClient.

    Grade calls the model several times in one Django request. A new thread
    (and loop) per call reuses the singleton client and raises
    "Event is bound to a different event loop".
    """
    global _loop
    with _loop_lock:
        if _loop is not None and _loop.is_running():
            return _loop

        loop = asyncio.new_event_loop()

        def _runner() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(
            target=_runner,
            name="ai-service-loop",
            daemon=True,
        )
        thread.start()
        _loop = loop
        try:
            from ai_service.http_client import reset_http_client

            reset_http_client()
        except Exception:
            pass
        return loop


def run_agent_sync(
    agent: Any,
    user_prompt: str,
    *,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """
    Run ``agent.run`` on the shared AI event loop with a wall-clock deadline.

    Raises AIServiceRunTimeout when the overall run exceeds the budget
    (covers multi-step / output retries that a single HTTP timeout wouldn't).
    """
    from ai_service.config import run_timeout_seconds

    seconds = float(timeout_seconds if timeout_seconds is not None else run_timeout_seconds())
    loop = _ensure_ai_loop()

    async def _run() -> Any:
        return await agent.run(user_prompt)

    future = asyncio.run_coroutine_threadsafe(_run(), loop)
    try:
        if seconds <= 0:
            return future.result()
        return future.result(timeout=seconds)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise AIServiceRunTimeout(
            f"AI Service run exceeded wall-clock timeout of {seconds:.0f}s"
        ) from exc
