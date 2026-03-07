from django.apps import AppConfig


class TutorxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tutorx"

    def ready(self):
        import tutorx.signals  # noqa: F401 - register pre_delete for Lesson
