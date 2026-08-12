"""
Seed AIService + Study Coach prompt variants.

Does not overwrite the original `default` prompt text if it already exists.
Creates/updates `math_display` and marks it as the active default.

Usage:
  python manage.py setup_ai_models
  python manage.py setup_study_coach_deck
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel, AIPromptConfiguration, AIService
from ai_service.runners.study_coach_deck import (
    DEFAULT_INSTRUCTIONS_V1,
    MATH_DISPLAY_INSTRUCTIONS,
    PROMPT_SLUG_MATH_DISPLAY,
    PROMPT_SLUG_V1,
    SERVICE_SLUG,
)


class Command(BaseCommand):
    help = "Seed study_coach_deck AI Service and prompt variants (idempotent)."

    def handle(self, *args, **options):
        service, created = AIService.objects.update_or_create(
            slug=SERVICE_SLUG,
            defaults={
                "name": "Study Coach Deck",
                "description": (
                    "Generate Quizlet-style quiz cards with Socratic hints "
                    "for student Study Coach sessions."
                ),
                "is_active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} service {service.slug}")
        )

        default_model = (
            AIModel.objects.filter(
                provider=AIModel.Provider.GEMINI,
                model_id="gemini-2.5-flash",
                is_active=True,
            ).first()
            or AIModel.objects.filter(is_active=True).order_by("sort_order").first()
        )

        prompt_v1, v1_created = AIPromptConfiguration.objects.get_or_create(
            service=service,
            slug=PROMPT_SLUG_V1,
            defaults={
                "name": "Default Study Coach Deck",
                "system_prompt": DEFAULT_INSTRUCTIONS_V1,
                "ai_model": default_model,
                "temperature": 0.45,
                "is_active": True,
                "is_default": False,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if v1_created else 'Left unchanged'} prompt {prompt_v1.slug}"
            )
        )

        prompt_v2, v2_created = AIPromptConfiguration.objects.update_or_create(
            service=service,
            slug=PROMPT_SLUG_MATH_DISPLAY,
            defaults={
                "name": "Study Coach Deck — Math display",
                "system_prompt": MATH_DISPLAY_INSTRUCTIONS,
                "ai_model": default_model,
                "temperature": 0.45,
                "is_active": True,
                "is_default": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if v2_created else 'Updated'} prompt {prompt_v2.slug} "
                f"(now default, model={default_model})"
            )
        )
