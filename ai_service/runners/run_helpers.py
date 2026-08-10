"""Shared helpers for AI Service runners (timeouts, ModelSettings)."""

from __future__ import annotations

import concurrent.futures
from typing import Any, Optional


class AIServiceRunTimeout(TimeoutError):
    """Raised when an agent.run_sync exceeds the wall-clock deadline."""


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


def run_agent_sync(
    agent: Any,
    user_prompt: str,
    *,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """
    Run ``agent.run_sync`` with a wall-clock deadline.

    Raises AIServiceRunTimeout when the overall run exceeds the budget
    (covers multi-step / output retries that a single HTTP timeout wouldn't).
    """
    from ai_service.config import run_timeout_seconds

    seconds = float(timeout_seconds if timeout_seconds is not None else run_timeout_seconds())
    if seconds <= 0:
        return agent.run_sync(user_prompt)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(agent.run_sync, user_prompt)
        try:
            return future.result(timeout=seconds)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise AIServiceRunTimeout(
                f"AI Service run exceeded wall-clock timeout of {seconds:.0f}s"
            ) from exc
