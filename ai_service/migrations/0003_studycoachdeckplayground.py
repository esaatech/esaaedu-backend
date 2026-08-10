from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ai_service", "0002_aigatewayplayground"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyCoachDeckPlayground",
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
                (
                    "title",
                    models.CharField(default="Study Coach deck probe", max_length=200),
                ),
                ("lesson_title", models.CharField(default="Sample Lesson", max_length=300)),
                (
                    "grounding_text",
                    models.TextField(
                        blank=True,
                        help_text="Optional lesson body. Blank = title-only generation.",
                    ),
                ),
                (
                    "difficulty_mode",
                    models.CharField(
                        choices=[
                            ("easy", "Easy"),
                            ("hard", "Hard"),
                            ("auto", "Auto"),
                        ],
                        default="easy",
                        max_length=16,
                    ),
                ),
                ("card_count", models.PositiveSmallIntegerField(default=6)),
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
                ("grounding_mode", models.CharField(blank=True, max_length=16)),
                ("raw_response_text", models.TextField(blank=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "prompt_config",
                    models.ForeignKey(
                        blank=True,
                        help_text="Blank uses the default prompt for slug study_coach_deck.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="study_coach_deck_playground_runs",
                        to="ai_service.aipromptconfiguration",
                    ),
                ),
            ],
            options={
                "verbose_name": "Study Coach Deck Playground",
                "verbose_name_plural": "Study Coach Deck Playgrounds",
                "ordering": ["-updated_at"],
            },
        ),
    ]
