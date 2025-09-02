from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class UserDashboardSettings(models.Model):
    """
    User-specific dashboard configuration settings
    Allows both students and teachers to customize their dashboard experience
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_settings'
    )
    
    # Dashboard Display Settings
    live_lessons_limit = models.PositiveIntegerField(
        default=3,
        help_text="Number of live lessons to show in upcoming events section"
    )
    
    continue_learning_limit = models.PositiveIntegerField(
        default=25,
        help_text="Number of lessons to show in continue learning section"
    )
    
    show_today_only = models.BooleanField(
        default=True,
        help_text="If True: show only today's events, If False: show all upcoming events"
    )
    
    # Additional Settings (for future expansion)
    theme_preference = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light Theme'),
            ('dark', 'Dark Theme'),
            ('auto', 'Auto (System)'),
        ],
        default='auto',
        help_text="Dashboard theme preference"
    )
    
    notifications_enabled = models.BooleanField(
        default=True,
        help_text="Enable dashboard notifications"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Dashboard Settings"
        verbose_name_plural = "User Dashboard Settings"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Dashboard Settings for {self.user.email}"
    
    @classmethod
    def get_or_create_settings(cls, user):
        """
        Get or create dashboard settings for a user
        Returns the settings object
        """
        settings, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'live_lessons_limit': 3,
                'continue_learning_limit': 25,
                'show_today_only': True,
                'theme_preference': 'auto',
                'notifications_enabled': True,
            }
        )
        return settings
    
    def get_dashboard_config(self):
        """
        Return dashboard configuration as a dictionary
        """
        return {
            'live_lessons_limit': self.live_lessons_limit,
            'continue_learning_limit': self.continue_learning_limit,
            'show_today_only': self.show_today_only,
            'theme_preference': self.theme_preference,
            'notifications_enabled': self.notifications_enabled,
        }