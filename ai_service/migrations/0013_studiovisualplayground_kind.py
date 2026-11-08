from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0012_studiovisualplayground"),
    ]

    operations = [
        migrations.AddField(
            model_name="studiovisualplayground",
            name="kind",
            field=models.CharField(
                choices=[
                    ("intro", "Intro"),
                    ("wording", "Wording"),
                    ("concept", "Concept"),
                ],
                default="concept",
                help_text="Intro is a title card. Wording is kinetic text of the language. Concept is a drawing of the idea.",
                max_length=16,
            ),
        ),
    ]
