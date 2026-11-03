"""
Seed Studio AI Services: script drafter, visual generator, system-instruction rewriter.

Does not overwrite an existing prompt's system_prompt (Admin edits stay).

Usage:
  python manage.py setup_ai_models
  python manage.py setup_studio_ai
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel, AIPromptConfiguration, AIService
from ai_service.studio_prompts import (
    PROMPT_SLUG_DEFAULT,
    SCRIPT_DRAFTER_PROMPT,
    SCRIPT_DRAFTER_SLUG,
    SYSTEM_INSTRUCTION_PROMPT,
    SYSTEM_INSTRUCTION_SLUG,
    VISUAL_GENERATOR_PROMPT,
    VISUAL_GENERATOR_SLUG,
)

SERVICES = (
    {
        "slug": SCRIPT_DRAFTER_SLUG,
        "name": "Studio Script Drafter",
        "description": (
            "Drafts spoken Lesson Studio beats. Admin prompt and model are pushed "
            "to lesson-studio PUT /v1/settings."
        ),
        "system_prompt": SCRIPT_DRAFTER_PROMPT,
        "temperature": 0.40,
    },
    {
        "slug": VISUAL_GENERATOR_SLUG,
        "name": "Studio Visual Generator",
        "description": (
            "Chooses one drawing component per Studio beat. Admin prompt and model "
            "are pushed to lesson-studio PUT /v1/settings."
        ),
        "system_prompt": VISUAL_GENERATOR_PROMPT,
        "temperature": 0.20,
    },
    {
        "slug": SYSTEM_INSTRUCTION_SLUG,
        "name": "Studio System Instruction",
        "description": (
            "Rewrites a Studio script or visual system prompt from a staff request. "
            "Apply the result onto the target prompt, then push to Studio."
        ),
        "system_prompt": SYSTEM_INSTRUCTION_PROMPT,
        "temperature": 0.30,
    },
)


class Command(BaseCommand):
    help = "Seed Studio AI Services and default prompts (idempotent)."

    def handle(self, *args, **options):
        preferred_ids = (
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-2.5-flash",
        )
        model = None
        for model_id in preferred_ids:
            model = AIModel.objects.filter(
                provider=AIModel.Provider.GEMINI,
                model_id=model_id,
                is_active=True,
            ).first()
            if model:
                break
        if model is None:
            model = AIModel.objects.filter(is_active=True).order_by("sort_order").first()

        for spec in SERVICES:
            service, created = AIService.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "is_active": True,
                },
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} service {service.slug}"
                )
            )

            prompt, prompt_created = AIPromptConfiguration.objects.get_or_create(
                service=service,
                slug=PROMPT_SLUG_DEFAULT,
                defaults={
                    "name": f"{spec['name']} — Default",
                    "system_prompt": spec["system_prompt"],
                    "ai_model": model,
                    "temperature": spec["temperature"],
                    "is_active": True,
                    "is_default": True,
                },
            )
            if prompt_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created prompt {prompt.slug} (default, model={model})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Left unchanged prompt {prompt.slug} for {service.slug}"
                    )
                )
