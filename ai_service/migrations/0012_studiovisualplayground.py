from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0011_studiosysteminstructionplayground"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudioVisualPlayground",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(default="Studio visual", max_length=200)),
                (
                    "spoken_line",
                    models.TextField(help_text="The spoken beat, as the teacher would say it."),
                ),
                (
                    "on_screen",
                    models.TextField(help_text="The On screen drawing brief for that beat."),
                ),
                (
                    "generate_audio",
                    models.BooleanField(
                        default=False,
                        help_text="Off draws the picture only. On also records the spoken line with ElevenLabs so Play uses word times.",
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("succeeded", models.BooleanField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("result_json", models.JSONField(blank=True, null=True)),
                ("provider", models.CharField(blank=True, max_length=32)),
                ("model_id", models.CharField(blank=True, max_length=128)),
                (
                    "temperature",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=3, null=True
                    ),
                ),
                ("instruction_slug", models.CharField(blank=True, max_length=80)),
                ("raw_response_text", models.TextField(blank=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "prompt_config",
                    models.ForeignKey(
                        blank=True,
                        help_text="A Studio Visual Generator prompt. Blank uses the default. This run does not change the live default.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="studio_visual_playground_runs",
                        to="ai_service.aipromptconfiguration",
                    ),
                ),
            ],
            options={
                "verbose_name": "Studio Visual Playground",
                "verbose_name_plural": "Studio Visual Playgrounds",
                "ordering": ["-updated_at"],
            },
        ),
    ]
