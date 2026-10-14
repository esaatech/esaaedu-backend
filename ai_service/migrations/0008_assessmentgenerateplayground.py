from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0007_aigenerationjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentGeneratePlayground",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="Assessment generate probe", max_length=200)),
                ("lesson_title", models.CharField(default="Introduction to Python", max_length=300)),
                (
                    "content",
                    models.TextField(
                        default=(
                            "Python is a high-level programming language known for its simplicity.\n"
                            "Variables store data values. Use print() to display output."
                        ),
                        help_text="Lesson material text used to ground the assessment.",
                    ),
                ),
                ("total_questions", models.PositiveSmallIntegerField(default=4)),
                ("multiple_choice_count", models.PositiveSmallIntegerField(default=2)),
                ("true_false_count", models.PositiveSmallIntegerField(default=1)),
                ("fill_blank_count", models.PositiveSmallIntegerField(default=0)),
                ("short_answer_count", models.PositiveSmallIntegerField(default=0)),
                ("essay_count", models.PositiveSmallIntegerField(default=1)),
                ("code_count", models.PositiveSmallIntegerField(default=0)),
                (
                    "system_instruction",
                    models.TextField(
                        blank=True,
                        help_text="Optional override. Blank uses the prompt config system prompt.",
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("succeeded", models.BooleanField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("result_json", models.JSONField(blank=True, null=True)),
                ("provider", models.CharField(blank=True, max_length=32)),
                ("model_id", models.CharField(blank=True, max_length=128)),
                ("temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True)),
                ("instruction_slug", models.CharField(blank=True, max_length=80)),
                ("raw_response_text", models.TextField(blank=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "prompt_config",
                    models.ForeignKey(
                        blank=True,
                        help_text="Blank uses the default prompt for slug assessment_generate.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assessment_generate_playground_runs",
                        to="ai_service.aipromptconfiguration",
                    ),
                ),
            ],
            options={
                "verbose_name": "Assessment Generate Playground",
                "verbose_name_plural": "Assessment Generate Playgrounds",
                "ordering": ["-updated_at"],
            },
        ),
    ]
