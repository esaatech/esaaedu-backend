from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from django.utils import timezone


def compute_assessment_deadline(submission: Any) -> Optional[timezone.datetime]:
    """Return absolute deadline for a timed assessment submission."""
    limit_minutes = getattr(submission, "time_limit_minutes", None)
    started_at = getattr(submission, "started_at", None)
    if not limit_minutes or not started_at:
        return None
    return started_at + timedelta(minutes=limit_minutes)


def compute_remaining_seconds(submission: Any, now: Optional[timezone.datetime] = None) -> Optional[int]:
    """Compute remaining seconds from server time; returns None for untimed submissions."""
    deadline = compute_assessment_deadline(submission)
    if deadline is None:
        return None

    now_ts = now or timezone.now()
    delta_seconds = int((deadline - now_ts).total_seconds())
    return max(0, delta_seconds)


def is_submission_expired(submission: Any, now: Optional[timezone.datetime] = None) -> bool:
    """Check whether a timed submission has exceeded its deadline."""
    deadline = compute_assessment_deadline(submission)
    if deadline is None:
        return False
    now_ts = now or timezone.now()
    return now_ts >= deadline


def expire_submission_if_needed(submission: Any, now: Optional[timezone.datetime] = None) -> bool:
    """
    Idempotently finalize an expired in-progress submission as auto_submitted.

    Returns True when a state transition happened.
    """
    if getattr(submission, "status", None) != "in_progress":
        return False
    if not is_submission_expired(submission, now=now):
        return False

    now_ts = now or timezone.now()
    submission.status = "auto_submitted"
    submission.submitted_at = submission.submitted_at or now_ts
    submission.time_remaining_seconds = 0
    submission.save(update_fields=["status", "submitted_at", "time_remaining_seconds"])
    return True


def build_timing_payload(submission: Any, now: Optional[timezone.datetime] = None) -> Dict[str, Any]:
    """Build canonical server timing metadata for API responses."""
    now_ts = now or timezone.now()
    deadline = compute_assessment_deadline(submission)
    remaining_seconds = compute_remaining_seconds(submission, now=now_ts)

    return {
        "server_now": now_ts.isoformat(),
        "ends_at": deadline.isoformat() if deadline else None,
        "time_remaining_seconds": remaining_seconds,
        "is_expired": bool(deadline and now_ts >= deadline),
    }
