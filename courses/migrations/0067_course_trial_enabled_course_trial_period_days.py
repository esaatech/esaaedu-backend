from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0066_course_promo_video_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="trial_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Whether this paid course offers a free trial period. When enabled, students can enroll without paying and are given access for the trial duration.",
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="trial_period_days",
            field=models.PositiveIntegerField(
                default=14,
                help_text="Length of the free trial in days (used when trial is enabled).",
            ),
        ),
    ]
