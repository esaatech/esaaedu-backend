from django.apps import AppConfig


class SettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'settings'
    verbose_name = 'User Settings'
    
    def ready(self):
        """
        Import signal handlers when the app is ready
        """
        pass