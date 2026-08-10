from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class AIModel(models.Model):
    """Catalog of provider model ids (e.g. Gemini 2.5 Flash) for prompts and runs."""

    class Provider(models.TextChoices):
        GEMINI = "gemini", "Google Gemini"
        OPENAI = "openai", "OpenAI"
        DEEPSEEK = "deepseek", "DeepSeek"

    provider = models.CharField(
        max_length=32,
        choices=Provider.choices,
        default=Provider.GEMINI,
    )
    model_id = models.CharField(
        max_length=128,
        help_text="API model id (e.g. gemini-2.5-flash, gpt-4o-mini, deepseek-chat).",
    )
    display_name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive models are hidden from admin dropdowns.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    default_temperature = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(2)],
        help_text="Suggested default when a prompt does not set temperature.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "display_name"]
        verbose_name = "AI model"
        verbose_name_plural = "AI models"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "model_id"],
                name="ai_service_aimodel_provider_model_id_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.model_id})"


class AIService(models.Model):
    """A product capability that has its own prompt(s), e.g. study_coach_deck."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Human-readable name for the AI service",
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Code identifier (e.g. study_coach_deck)",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this AI service does",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this service is currently available",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "AI Service"
        verbose_name_plural = "AI Services"

    def __str__(self) -> str:
        return self.name

    def get_default_prompt(self):
        """Return the default active prompt for this service, if any."""
        return self.prompts.filter(is_default=True, is_active=True).first()


class AIPromptConfiguration(models.Model):
    """System prompt + model settings for one AI Service variant."""

    service = models.ForeignKey(
        AIService,
        on_delete=models.CASCADE,
        related_name="prompts",
        help_text="The AI service this prompt belongs to",
    )
    name = models.CharField(
        max_length=100,
        help_text="Human-readable name for this prompt variant",
    )
    slug = models.SlugField(
        max_length=50,
        help_text="Code identifier for this variant (e.g. default)",
    )
    system_prompt = models.TextField(
        help_text="System / instructions text sent to the model",
    )
    ai_model = models.ForeignKey(
        AIModel,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prompt_configurations",
        help_text="Default model for runs using this prompt variant.",
    )
    temperature = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(2)],
        help_text="Sampling temperature (0–2). Blank = model or env default.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this prompt is currently active",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default prompt for this service",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["service", "slug"],
                name="ai_service_aipromptconfiguration_service_slug_uniq",
            ),
        ]
        ordering = ["service", "name"]
        verbose_name = "AI Prompt Configuration"
        verbose_name_plural = "AI Prompt Configurations"

    def __str__(self) -> str:
        return f"{self.service.name} - {self.name}"

    def save(self, *args, **kwargs):
        """Ensure only one default prompt per service."""
        if self.is_default:
            AIPromptConfiguration.objects.filter(
                service=self.service,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)



class AIGatewayPlayground(models.Model):
    """
    Admin playground to probe the Pydantic AI gateway.

    Run uses the same resolve_model() path product runners will use.
    Phase 3+ service playgrounds follow this same Admin Run pattern.
    """

    title = models.CharField(max_length=200, default="Gateway probe")
    prompt_config = models.ForeignKey(
        AIPromptConfiguration,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gateway_playground_runs",
        help_text="Optional prompt config (model + system prompt). Blank uses env defaults.",
    )
    user_message = models.TextField(
        blank=True,
        default="Reply briefly confirming the gateway works.",
        help_text="User message sent to the probe agent.",
    )
    notes = models.TextField(blank=True)

    # Last run snapshots
    succeeded = models.BooleanField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    result_json = models.JSONField(null=True, blank=True)
    provider = models.CharField(max_length=32, blank=True)
    model_id = models.CharField(max_length=128, blank=True)
    temperature = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
    )
    instruction_slug = models.CharField(max_length=80, blank=True)
    raw_response_text = models.TextField(blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "AI Gateway Playground"
        verbose_name_plural = "AI Gateway Playgrounds"

    def __str__(self) -> str:
        return self.title or f"Gateway playground #{self.pk}"



class StudyCoachDeckPlayground(models.Model):
    """Admin playground for the study_coach_deck AI Service."""

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("hard", "Hard"),
        ("auto", "Auto"),
    ]

    title = models.CharField(max_length=200, default="Study Coach deck probe")
    prompt_config = models.ForeignKey(
        AIPromptConfiguration,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="study_coach_deck_playground_runs",
        help_text="Blank uses the default prompt for slug study_coach_deck.",
    )
    lesson_title = models.CharField(max_length=300, default="Sample Lesson")
    grounding_text = models.TextField(
        blank=True,
        help_text="Optional lesson body. Blank = title-only generation.",
    )
    difficulty_mode = models.CharField(
        max_length=16,
        choices=DIFFICULTY_CHOICES,
        default="easy",
    )
    card_count = models.PositiveSmallIntegerField(default=6)
    notes = models.TextField(blank=True)

    succeeded = models.BooleanField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    result_json = models.JSONField(null=True, blank=True)
    provider = models.CharField(max_length=32, blank=True)
    model_id = models.CharField(max_length=128, blank=True)
    temperature = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    instruction_slug = models.CharField(max_length=80, blank=True)
    grounding_mode = models.CharField(max_length=16, blank=True)
    raw_response_text = models.TextField(blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Study Coach Deck Playground"
        verbose_name_plural = "Study Coach Deck Playgrounds"

    def __str__(self) -> str:
        return self.title or f"Study Coach playground #{self.pk}"
