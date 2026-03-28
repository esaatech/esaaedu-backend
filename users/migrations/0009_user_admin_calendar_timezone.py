from django.db import migrations, models

import users.validators


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_add_public_handle"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="admin_calendar_timezone",
            field=models.CharField(
                blank=True,
                default="",
                help_text="IANA timezone for Django admin dashboard calendar/timetable (e.g. America/Toronto). Empty = use cookie or system default.",
                max_length=63,
                validators=[users.validators.validate_iana_timezone],
            ),
        ),
    ]
