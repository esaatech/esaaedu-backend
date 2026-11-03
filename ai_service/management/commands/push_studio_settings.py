"""Push Admin Studio prompts and models to lesson-studio."""

from django.core.management.base import BaseCommand, CommandError

from ai_service.studio_settings import push_studio_settings


class Command(BaseCommand):
    help = "PUT default Studio script and visual prompts to LESSON_STUDIO_URL /v1/settings."

    def handle(self, *args, **options):
        result = push_studio_settings()
        if result.skipped:
            raise CommandError(result.error)
        if not result.ok:
            raise CommandError(result.error)
        self.stdout.write(self.style.SUCCESS("Pushed Studio settings."))
