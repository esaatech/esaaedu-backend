import uuid

from django.conf import settings
from django.db import models


class SmsRoutingLog(models.Model):
    """
    SMS delivery/routing memory for masked Twilio number flows.
    Outbound rows support reply matching; inbound rows record student texts.
    """

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    twilio_number = models.CharField(
        max_length=20,
        help_text="Our Twilio number (To on inbound, From on outbound) in E.164.",
    )
    student_phone = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Family/student number (From on inbound, To on outbound), E.164.",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sms_routing_logs",
        limit_choices_to={"role": "teacher"},
        null=True,
        blank=True,
        help_text="Teacher on outbound; set on inbound after routing (optional until processed).",
    )
    course_class = models.ForeignKey(
        "courses.Class",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_routing_logs",
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    body = models.TextField(help_text="Message text as sent/received (after branding for outbound).")
    twilio_message_sid = models.CharField(
        max_length=34,
        unique=True,
        null=True,
        blank=True,
        help_text="Twilio Message SID for idempotency and support.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sms_routing_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student_phone", "-created_at"]),
        ]

    def __str__(self):
        return f"SMS {self.direction} {self.student_phone} @ {self.created_at}"
