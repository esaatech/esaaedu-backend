from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0010_aigradingjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudioSystemInstructionPlayground",
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
                ("title", models.CharField(default="Studio system instruction", max_length=200)),
                (
                    "target_service",
                    models.CharField(
                        choices=[
                            ("studio_script_drafter", "Studio script drafter"),
                            ("studio_visual_generator", "Studio visual generator"),
                        ],
                        default="studio_script_drafter",
                        help_text="Which Studio system prompt to rewrite.",
                        max_length=50,
                    ),
                ),
                (
                    "current_prompt",
                    models.TextField(
                        blank=True,
                        help_text="Leave blank to load the target service's current Admin prompt.",
                    ),
                ),
                (
                    "change_request",
                    models.TextField(help_text="What to change in that system instruction."),
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
                        help_text="Blank uses the default prompt for slug studio_system_instruction.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="studio_system_instruction_playground_runs",
                        to="ai_service.aipromptconfiguration",
                    ),
                ),
            ],
            options={
                "verbose_name": "Studio System Instruction Playground",
                "verbose_name_plural": "Studio System Instruction Playgrounds",
                "ordering": ["-updated_at"],
            },
        ),
    ]
