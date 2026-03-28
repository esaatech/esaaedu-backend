# Generated manually for SystemSettings singleton

import uuid

from django.db import migrations, models

import users.validators


class Migration(migrations.Migration):

    dependencies = [
        ("settings", "0008_usertutorxinstruction"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemSettings",
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
                    "calendar_timezone",
                    models.CharField(
                        default="UTC",
                        help_text=(
                            "IANA timezone for weekly class slots and admin timetable when no "
                            "browser cookie is set (e.g. America/New_York, Africa/Lagos). "
                            "Overrides ADMIN_CALENDAR_TIMEZONE from the environment."
                        ),
                        max_length=63,
                        validators=[users.validators.validate_iana_timezone],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "System Settings",
                "verbose_name_plural": "System Settings",
            },
        ),
    ]
