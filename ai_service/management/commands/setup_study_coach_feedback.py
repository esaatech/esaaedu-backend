"""
Seed the study_coach_feedback AI Service (session coaching after Grade).

Usage:
  python manage.py setup_ai_models
  python manage.py setup_study_coach_feedback
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel, AIPromptConfiguration, AIService
from ai_service.runners.study_coach_feedback import (
    DEFAULT_INSTRUCTIONS,
    PROMPT_SLUG_DEFAULT,
    SERVICE_SLUG,
)


FAST_MODEL_IDS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
)


class Command(BaseCommand):
    help = "Seed study_coach_feedback AI Service (idempotent)."

    def handle(self, *args, **options):
        service, created = AIService.objects.update_or_create(
            slug=SERVICE_SLUG,
            defaults={
                "name": "Study Coach Feedback",
                "description": (
                    "After a Study Coach quiz is graded, write coaching copy and a "
                    "structured next mix / study-page task."
                ),
                "is_active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} service {service.slug}")
        )

        model = None
        for model_id in FAST_MODEL_IDS:
            model = AIModel.objects.filter(
                provider=AIModel.Provider.GEMINI,
                model_id=model_id,
                is_active=True,
            ).first()
            if model:
                break
        if model is None:
            model = (
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
                "name": "Study Coach Feedback — Default",
                "system_prompt": DEFAULT_INSTRUCTIONS,
                "ai_model": model,
                "temperature": 0.35,
                "is_active": True,
                "is_default": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if prompt_created else 'Updated'} prompt {prompt.slug} "
                f"(default, model={model})"
            )
        )
