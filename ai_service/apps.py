from django.apps import AppConfig


class AiServiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_service"
    verbose_name = "AI Service"

    def ready(self) -> None:
        from . import admin  # noqa: F401 — ensure admin registrations load
