"""
Seed the tutorx_assignment_grade AI Service (TutorX auto-grade).

Default model is Gemini 2.5 Flash from the shared AIModel catalog.
There is no silent fallback — production must have this default prompt.

Usage:
  python manage.py setup_ai_models
  python manage.py setup_tutorx_assignment_grade
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel, AIPromptConfiguration, AIService
from ai_service.runners.tutorx_assignment_grade import (
    DEFAULT_INSTRUCTIONS,
    PROMPT_SLUG_DEFAULT,
    SERVICE_SLUG,
)


# Prefer the production Gemini default; fall back to other Gemini ids if needed.
DEFAULT_GEMINI_MODEL_IDS = (
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
)


class Command(BaseCommand):
    help = "Seed tutorx_assignment_grade AI Service (idempotent)."

    def handle(self, *args, **options):
        service, created = AIService.objects.update_or_create(
            slug=SERVICE_SLUG,
            defaults={
                "name": "TutorX Assignment Grade",
                "description": (
                    "AI grade for TutorX assignment essay / fill-blank / open short-answer "
                    "questions. Used by Cloud Tasks auto-grade and the Admin playground."
                ),
                "is_active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} service {service.slug}")
        )

        gemini_model = None
        for model_id in DEFAULT_GEMINI_MODEL_IDS:
            gemini_model = AIModel.objects.filter(
                provider=AIModel.Provider.GEMINI,
                model_id=model_id,
                is_active=True,
            ).first()
            if gemini_model:
                break

        if gemini_model is None:
            raise SystemExit(
                "No active Gemini AIModel found. Run: python manage.py setup_ai_models"
            )

        prompt, prompt_created = AIPromptConfiguration.objects.update_or_create(
            service=service,
            slug=PROMPT_SLUG_DEFAULT,
            defaults={
                "name": "TutorX Assignment Grade — Default",
                "system_prompt": DEFAULT_INSTRUCTIONS,
                "ai_model": gemini_model,
                "temperature": 0.30,
                "is_active": True,
                "is_default": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if prompt_created else 'Updated'} prompt {prompt.slug} "
                f"(default, model={gemini_model})"
            )
        )
