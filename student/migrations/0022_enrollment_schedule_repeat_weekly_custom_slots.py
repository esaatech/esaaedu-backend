# Generated manually for repeat_weekly + custom_slots on EnrollmentSchedule

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("student", "0021_classsession_all_day_enrollment_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollmentschedule",
            name="custom_slots",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "When repeat_weekly is False: list of "
                    "{date: YYYY-MM-DD, start_time: HH:MM:SS, end_time: HH:MM:SS}."
                ),
            ),
        ),
        migrations.AddField(
            model_name="enrollmentschedule",
            name="repeat_weekly",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "When True (default), the selected weekdays/times repeat until the course ends. "
                    "When False, use custom_slots for specific date/time picks."
                ),
            ),
        ),
    ]
