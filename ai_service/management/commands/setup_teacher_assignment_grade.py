"""
Seed the teacher_assignment_grade AI Service (teacher Assignment AI Grade).

Default model is Gemini 2.5 Flash. No silent GeminiGrader fallback.

Usage:
  python manage.py setup_ai_models
  python manage.py setup_teacher_assignment_grade
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel, AIPromptConfiguration, AIService
from ai_service.runners.teacher_assignment_grade import (
    DEFAULT_INSTRUCTIONS,
    PROMPT_SLUG_DEFAULT,
    SERVICE_SLUG,
)


DEFAULT_GEMINI_MODEL_IDS = (
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
)


class Command(BaseCommand):
    help = "Seed teacher_assignment_grade AI Service (idempotent)."

    def handle(self, *args, **options):
        service, created = AIService.objects.update_or_create(
            slug=SERVICE_SLUG,
            defaults={
                "name": "Teacher Assignment Grade",
                "description": (
                    "AI grade for teacher Assignment grading UI (essay / fill-blank / "
                    "open short-answer). Model is switchable in Admin."
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
                "name": "Teacher Assignment Grade — Default",
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
