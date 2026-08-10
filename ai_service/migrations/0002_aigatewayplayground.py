from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ai_service", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIGatewayPlayground",
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
                ("title", models.CharField(default="Gateway probe", max_length=200)),
                (
                    "user_message",
                    models.TextField(
                        blank=True,
                        default="Reply briefly confirming the gateway works.",
                        help_text="User message sent to the probe agent.",
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
                        help_text="Optional prompt config (model + system prompt). Blank uses env defaults.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gateway_playground_runs",
                        to="ai_service.aipromptconfiguration",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Gateway Playground",
                "verbose_name_plural": "AI Gateway Playgrounds",
                "ordering": ["-updated_at"],
            },
        ),
    ]
