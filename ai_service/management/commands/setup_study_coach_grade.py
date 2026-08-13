"""
Seed the study_coach_grade AI Service (fast model for one-card Check).

Usage:
  python manage.py setup_ai_models
  python manage.py setup_study_coach_grade
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel, AIPromptConfiguration, AIService
from ai_service.runners.study_coach_grade import (
    DEFAULT_INSTRUCTIONS,
    PROMPT_SLUG_DEFAULT,
    SERVICE_SLUG,
)


FAST_MODEL_IDS = (
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
)


class Command(BaseCommand):
    help = "Seed study_coach_grade AI Service (idempotent)."

    def handle(self, *args, **options):
        service, created = AIService.objects.update_or_create(
            slug=SERVICE_SLUG,
            defaults={
                "name": "Study Coach Grade",
                "description": (
                    "Fast meaning-based grade for one Study Coach short-answer card. "
                    "Uses a lite model so Check stays quick."
                ),
                "is_active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} service {service.slug}")
        )

        fast_model = None
        for model_id in FAST_MODEL_IDS:
            fast_model = AIModel.objects.filter(
                provider=AIModel.Provider.GEMINI,
                model_id=model_id,
                is_active=True,
            ).first()
            if fast_model:
                break
        if fast_model is None:
            fast_model = (
                AIModel.objects.filter(
                    provider=AIModel.Provider.DEEPSEEK,
                    is_active=True,
                ).first()
                or AIModel.objects.filter(is_active=True).order_by("sort_order").first()
            )

        prompt, prompt_created = AIPromptConfiguration.objects.update_or_create(
            service=service,
            slug=PROMPT_SLUG_DEFAULT,
            defaults={
                "name": "Study Coach Grade — Fast",
                "system_prompt": DEFAULT_INSTRUCTIONS,
                "ai_model": fast_model,
                "temperature": 0.20,
                "is_active": True,
                "is_default": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if prompt_created else 'Updated'} prompt {prompt.slug} "
                f"(default, model={fast_model})"
            )
        )
