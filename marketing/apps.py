from django.apps import AppConfig


class MarketingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketing'
    
    def ready(self):
        """Import signals when app is ready."""
        import marketing.signals  # noqa
    verbose_name = 'Marketing'

