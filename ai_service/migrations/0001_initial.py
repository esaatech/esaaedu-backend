from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AIModel",
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
                    "provider",
                    models.CharField(
                        choices=[
                            ("gemini", "Google Gemini"),
                            ("openai", "OpenAI"),
                            ("deepseek", "DeepSeek"),
                        ],
                        default="gemini",
                        max_length=32,
                    ),
                ),
                (
                    "model_id",
                    models.CharField(
                        help_text="API model id (e.g. gemini-2.5-flash, gpt-4o-mini, deepseek-chat).",
                        max_length=128,
                    ),
                ),
                ("display_name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive models are hidden from admin dropdowns.",
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "default_temperature",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Suggested default when a prompt does not set temperature.",
                        max_digits=3,
                        null=True,
                        validators=[
                            MinValueValidator(0),
                            MaxValueValidator(2),
                        ],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "AI model",
                "verbose_name_plural": "AI models",
                "ordering": ["sort_order", "display_name"],
            },
        ),
        migrations.CreateModel(
            name="AIService",
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
                    "name",
                    models.CharField(
                        help_text="Human-readable name for the AI service",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="Code identifier (e.g. study_coach_deck)",
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Description of what this AI service does",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this service is currently available",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "AI Service",
                "verbose_name_plural": "AI Services",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="AIPromptConfiguration",
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
                    "name",
                    models.CharField(
                        help_text="Human-readable name for this prompt variant",
                        max_length=100,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="Code identifier for this variant (e.g. default)",
                    ),
                ),
                (
                    "system_prompt",
                    models.TextField(
                        help_text="System / instructions text sent to the model",
                    ),
                ),
                (
                    "temperature",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Sampling temperature (0–2). Blank = model or env default.",
                        max_digits=3,
                        null=True,
                        validators=[
                            MinValueValidator(0),
                            MaxValueValidator(2),
                        ],
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this prompt is currently active",
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this is the default prompt for this service",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ai_model",
                    models.ForeignKey(
                        blank=True,
                        help_text="Default model for runs using this prompt variant.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="prompt_configurations",
                        to="ai_service.aimodel",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        help_text="The AI service this prompt belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prompts",
                        to="ai_service.aiservice",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Prompt Configuration",
                "verbose_name_plural": "AI Prompt Configurations",
                "ordering": ["service", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="aimodel",
            constraint=models.UniqueConstraint(
                fields=("provider", "model_id"),
                name="ai_service_aimodel_provider_model_id_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="aipromptconfiguration",
            constraint=models.UniqueConstraint(
                fields=("service", "slug"),
                name="ai_service_aipromptconfiguration_service_slug_uniq",
            ),
        ),
    ]
