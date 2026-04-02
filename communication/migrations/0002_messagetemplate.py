# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("sms", "SMS"),
                            ("email", "Email"),
                            ("whatsapp", "WhatsApp"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="Stable id per channel (e.g. class-started).",
                        max_length=80,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text="Short title in teacher/admin UI.",
                        max_length=200,
                    ),
                ),
                (
                    "body_template",
                    models.TextField(
                        help_text="Body with placeholders, e.g. Hello — {course_title} has started.",
                    ),
                ),
                (
                    "subject_template",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Optional; used when channel is email.",
                        max_length=200,
                    ),
                ),
                (
                    "variables",
                    models.JSONField(
                        default=list,
                        help_text='List of placeholder names the client must supply, e.g. ["course_title"].',
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "sort_order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Lower numbers appear first in lists.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "message_templates",
                "ordering": ["channel", "sort_order", "label"],
                "unique_together": [("channel", "slug")],
            },
        ),
        migrations.AddIndex(
            model_name="messagetemplate",
            index=models.Index(
                fields=["channel", "is_active", "sort_order"],
                name="message_temp_channel_0b7b2d_idx",
            ),
        ),
    ]
