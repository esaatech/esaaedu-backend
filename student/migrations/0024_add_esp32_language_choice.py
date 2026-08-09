from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("student", "0023_enrollment_schedule_weekday_slots"),
    ]

    operations = [
        migrations.AlterField(
            model_name="codesnippet",
            name="language",
            field=models.CharField(
                choices=[
                    ("python", "Python"),
                    ("javascript", "JavaScript"),
                    ("html", "HTML"),
                    ("css", "CSS"),
                    ("text", "Plain text"),
                    ("json", "JSON"),
                    ("flask", "Flask"),
                    ("esp32", "ESP32"),
                    ("java", "Java"),
                    ("cpp", "C++"),
                    ("c", "C"),
                    ("other", "Other"),
                ],
                default="python",
                help_text="Programming language",
                max_length=50,
            ),
        ),
    ]
