from django.db import migrations, models

# Seeded defaults that were never user-chosen overrides; blank means use GEMINI_MODEL env.
SEEDED_MODEL_NAMES = (
    "gemini-2.0-flash-001",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite-001",
    "gemini-2.0-flash-lite",
)


def clear_seeded_model_names(apps, schema_editor):
    AIPromptTemplate = apps.get_model("ai", "AIPromptTemplate")
    AIPromptTemplate.objects.filter(model_name__in=SEEDED_MODEL_NAMES).update(model_name="")


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0005_remove_aiprompttemplate_default_system_instruction_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aiprompttemplate",
            name="model_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional Gemini model override. Leave blank to use GEMINI_MODEL env.",
                max_length=100,
            ),
        ),
        migrations.RunPython(clear_seeded_model_names, migrations.RunPython.noop),
    ]
