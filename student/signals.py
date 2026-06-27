"""
Signals for the student app.

Sends a Slack notification to the enrollments channel whenever a new
EnrolledCourse is created, regardless of which path created it (Stripe,
free/admin util, self-enroll endpoint, Django admin).
"""
import logging
import threading
from contextlib import contextmanager

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EnrolledCourse

logger = logging.getLogger(__name__)

# Thread-local flag so bulk/seed inserts can opt out of notifications.
_suppression = threading.local()


def _notifications_suppressed():
    return getattr(_suppression, "active", False)


@contextmanager
def suppress_enrollment_notifications():
    """
    Context manager to temporarily disable enrollment Slack notifications
    (e.g. when generating sample/seed data).
    """
    previous = getattr(_suppression, "active", False)
    _suppression.active = True
    try:
        yield
    finally:
        _suppression.active = previous


@receiver(post_save, sender=EnrolledCourse, dispatch_uid="enrollment_slack_notification")
def notify_enrollment_created(sender, instance, created, **kwargs):
    """Send a Slack notification after a new enrollment commits."""
    if not created or _notifications_suppressed():
        return

    def _send():
        try:
            from slack_notifications import send_enrollment_notification
            send_enrollment_notification(instance)
        except Exception as exc:
            # Never let a notification failure affect the enrollment flow.
            logger.warning("Failed to send enrollment Slack notification: %s", exc, exc_info=True)

    # Only fire once the (often atomic) enrollment transaction has committed.
    transaction.on_commit(_send)
