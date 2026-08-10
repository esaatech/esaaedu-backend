"""
Seed AIService + default AIPromptConfiguration for study_coach_deck.

Usage:
  python manage.py setup_ai_models
  python manage.py setup_study_coach_deck
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel, AIPromptConfiguration, AIService
from ai_service.runners.study_coach_deck import DEFAULT_INSTRUCTIONS, SERVICE_SLUG


class Command(BaseCommand):
    help = "Seed study_coach_deck AI Service and default prompt (idempotent)."

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

        prompt, p_created = AIPromptConfiguration.objects.update_or_create(
            service=service,
            slug="default",
            defaults={
                "name": "Default Study Coach Deck",
                "system_prompt": DEFAULT_INSTRUCTIONS,
                "ai_model": default_model,
                "temperature": 0.45,
                "is_active": True,
                "is_default": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if p_created else 'Updated'} prompt {prompt.slug} "
                f"(model={default_model})"
            )
        )
