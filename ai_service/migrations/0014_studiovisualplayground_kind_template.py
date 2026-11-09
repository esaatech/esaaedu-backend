from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0013_studiovisualplayground_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="studiovisualplayground",
            name="kind",
            field=models.CharField(
                choices=[
                    ("intro", "Intro"),
                    ("wording", "Wording"),
                    ("template", "Template"),
                    ("concept", "Concept"),
                ],
                default="concept",
                help_text="Intro is a title card. Wording is kinetic text. Template is a guarded layout. Concept is an example, idea, or analogy drawn as SVG.",
                max_length=16,
            ),
        ),
    ]
