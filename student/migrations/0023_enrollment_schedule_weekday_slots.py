from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0022_enrollment_schedule_repeat_weekly_custom_slots'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollmentschedule',
            name='weekday_slots',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'When repeat_weekly is True: optional per-weekday times '
                    '[{weekday: 0-6, start_time: HH:MM:SS, end_time: HH:MM:SS}, …]. '
                    'When empty, shared start_time/end_time apply to all weekdays.'
                ),
            ),
        ),
    ]
