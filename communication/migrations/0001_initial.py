# Generated manually for communication.SmsRoutingLog

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("courses", "0064_courseassessmentsubmission_return_feedback"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SmsRoutingLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "twilio_number",
                    models.CharField(
                        help_text="Our Twilio number (To on inbound, From on outbound) in E.164.",
                        max_length=20,
                    ),
                ),
                (
                    "student_phone",
                    models.CharField(
                        db_index=True,
                        help_text="Family/student number (From on inbound, To on outbound), E.164.",
                        max_length=20,
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[("inbound", "Inbound"), ("outbound", "Outbound")],
                        max_length=10,
                    ),
                ),
                (
                    "body",
                    models.TextField(
                        help_text="Message text as sent/received (after branding for outbound)."
                    ),
                ),
                (
                    "twilio_message_sid",
                    models.CharField(
                        blank=True,
                        help_text="Twilio Message SID for idempotency and support.",
                        max_length=34,
                        null=True,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "course_class",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_routing_logs",
                        to="courses.class",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"role": "teacher"},
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sms_routing_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "sms_routing_logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="smsroutinglog",
            index=models.Index(
                fields=["student_phone", "-created_at"],
                name="sms_routing_student_0f3b0a_idx",
            ),
        ),
    ]
