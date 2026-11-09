from django.db import migrations, models


def template_becomes_concept(apps, schema_editor):
    Playground = apps.get_model("ai_service", "StudioVisualPlayground")
    Playground.objects.filter(kind="template").update(kind="concept")


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0014_studiovisualplayground_kind_template"),
    ]

    operations = [
        migrations.RunPython(template_becomes_concept, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="studiovisualplayground",
            name="kind",
            field=models.CharField(
                choices=[
                    ("intro", "Intro"),
                    ("wording", "Wording"),
                    ("concept", "Concept"),
                ],
                default="concept",
                help_text="Intro is a title card. Wording is kinetic text. Concept is a relationship picture: a group, a comparison, steps, parts, cause and effect, a number line, or a cycle.",
                max_length=16,
            ),
        ),
    ]
