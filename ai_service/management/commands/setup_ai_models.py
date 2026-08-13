"""
Seed catalog AIModel rows for Gemini / OpenAI / DeepSeek.

Usage:
  python manage.py setup_ai_models
"""

from django.core.management.base import BaseCommand

from ai_service.models import AIModel


DEFAULT_MODELS = [
    {
        "provider": AIModel.Provider.GEMINI,
        "model_id": "gemini-2.5-flash-lite",
        "display_name": "Gemini 2.5 Flash Lite",
        "description": "Fastest Gemini for single-question grading and other low-latency checks.",
        "sort_order": 5,
        "default_temperature": 0.20,
    },
    {
        "provider": AIModel.Provider.GEMINI,
        "model_id": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "description": "Fast default for structured generation (Vertex or API key).",
        "sort_order": 10,
        "default_temperature": 0.40,
    },
    {
        "provider": AIModel.Provider.GEMINI,
        "model_id": "gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro",
        "description": "Higher-quality Gemini for harder generation tasks.",
        "sort_order": 20,
        "default_temperature": 0.35,
    },
    {
        "provider": AIModel.Provider.OPENAI,
        "model_id": "gpt-4o-mini",
        "display_name": "GPT-4o mini",
        "description": "OpenAI default for cost-efficient structured output.",
        "sort_order": 30,
        "default_temperature": 0.40,
    },
    {
        "provider": AIModel.Provider.OPENAI,
        "model_id": "gpt-4o",
        "display_name": "GPT-4o",
        "description": "Stronger OpenAI model when quality matters more than cost.",
        "sort_order": 40,
        "default_temperature": 0.35,
    },
    {
        "provider": AIModel.Provider.DEEPSEEK,
        "model_id": "deepseek-chat",
        "display_name": "DeepSeek Chat",
        "description": "DeepSeek OpenAI-compatible chat model.",
        "sort_order": 50,
        "default_temperature": 0.40,
    },
]


class Command(BaseCommand):
    help = "Seed AIModel catalog entries (idempotent update_or_create)."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for row in DEFAULT_MODELS:
            obj, created = AIModel.objects.update_or_create(
                provider=row["provider"],
                model_id=row["model_id"],
                defaults={
                    "display_name": row["display_name"],
                    "description": row["description"],
                    "sort_order": row["sort_order"],
                    "default_temperature": row["default_temperature"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created {obj}"))
            else:
                updated_count += 1
                self.stdout.write(f"Updated {obj}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created_count} updated={updated_count}"
            )
        )
