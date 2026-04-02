import uuid
from string import Formatter

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class SmsRoutingLog(models.Model):
    """
    SMS delivery/routing memory for masked Twilio number flows.
    Outbound rows support reply matching; inbound rows record student texts.
    """

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    class InboundRouting(models.TextChoices):
        PENDING = "pending", "Pending"
        ROUTED = "routed", "Routed"
        GENERIC_ADMIN = "generic_admin", "Generic / admin"

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
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_routing_logs",
        help_text="Course context for outbound and routed inbound.",
    )
    course_class = models.ForeignKey(
        "courses.Class",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_routing_logs",
    )
    inbound_routing = models.CharField(
        max_length=20,
        choices=InboundRouting.choices,
        null=True,
        blank=True,
        help_text="Inbound only: pending until routing runs; routed if matched to prior outbound; generic_admin otherwise. Null for outbound.",
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


class MessageTemplate(models.Model):
    """
    Reusable outbound copy per channel (SMS, email, WhatsApp, …).
    body_template uses Python format placeholders, e.g. {course_title} for Course.title.
    """

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    CHANNEL_ALLOWED_VARIABLES = {
        Channel.SMS: ("course_title", "student_name"),
        Channel.EMAIL: ("course_title", "student_name"),
        Channel.WHATSAPP: ("course_title", "student_name"),
    }

    channel = models.CharField(max_length=20, choices=Channel.choices, db_index=True)
    slug = models.SlugField(
        max_length=80,
        help_text="Stable id per channel (e.g. class-started).",
    )
    label = models.CharField(max_length=200, help_text="Short title in teacher/admin UI.")
    body_template = models.TextField(
        help_text="Body with placeholders, e.g. Hello — {course_title} has started.",
    )
    subject_template = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optional; used when channel is email.",
    )
    variables = models.JSONField(
        default=list,
        help_text='List of placeholder names the client must supply, e.g. ["course_title"].',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first in lists.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "message_templates"
        ordering = ["channel", "sort_order", "label"]
        unique_together = [["channel", "slug"]]
        indexes = [
            models.Index(fields=["channel", "is_active", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.get_channel_display()}: {self.label} ({self.slug})"

    @classmethod
    def allowed_variables_for_channel(cls, channel: str) -> tuple[str, ...]:
        return cls.CHANNEL_ALLOWED_VARIABLES.get(channel, ())

    def _extract_variables(self) -> list[str]:
        vars_found: set[str] = set()
        for _, field_name, _, _ in Formatter().parse(self.body_template or ""):
            if not field_name:
                continue
            # Keep simple names only. Attribute/index expressions are unsupported.
            cleaned = field_name.strip()
            if cleaned:
                vars_found.add(cleaned)
        return sorted(vars_found)

    def clean(self):
        extracted = self._extract_variables()
        allowed = set(self.allowed_variables_for_channel(self.channel))
        unknown = sorted(v for v in extracted if v not in allowed)
        if unknown:
            raise ValidationError(
                {
                    "body_template": (
                        f"Unsupported variables: {', '.join(unknown)}. "
                        f"Allowed variables: {', '.join(sorted(allowed))}."
                    )
                }
            )
        # Derived from template body to avoid manual drift.
        self.variables = extracted

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify((self.label or "").strip())[:80] or "template"
            candidate = base
            i = 2
            while MessageTemplate.objects.filter(channel=self.channel, slug=candidate).exclude(
                pk=self.pk
            ).exists():
                suffix = f"-{i}"
                candidate = f"{base[: max(1, 80 - len(suffix))]}{suffix}"
                i += 1
            self.slug = candidate
        self.full_clean()
        return super().save(*args, **kwargs)
