from django.contrib import admin
from .models import UserDashboardSettings, CourseSettings


@admin.register(CourseSettings)
class CourseSettingsAdmin(admin.ModelAdmin):
    """Admin interface for CourseSettings"""
    list_display = (
        'monthly_price_markup_percentage',
        'max_students_per_course',
        'default_course_duration_weeks',
        'enable_trial_period',
        'trial_period_days',
        'updated_at'
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Billing Settings', {
            'fields': ('monthly_price_markup_percentage',),
            'description': 'Configure course billing and pricing settings'
        }),
        ('Course Defaults', {
            'fields': ('max_students_per_course', 'default_course_duration_weeks'),
            'description': 'Default values for new courses'
        }),
        ('Trial Period Settings', {
            'fields': ('enable_trial_period', 'trial_period_days'),
            'description': 'Configure trial period for all courses'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        # Only allow adding if no settings exist
        return not CourseSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False


@admin.register(UserDashboardSettings)
class UserDashboardSettingsAdmin(admin.ModelAdmin):
    """Admin interface for UserDashboardSettings"""
    list_display = (
        'user',
        'theme_preference',
        'notifications_enabled',
        'updated_at'
    )
    list_filter = ('theme_preference', 'notifications_enabled')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Display Settings', {
            'fields': (
                'live_lessons_limit',
                'continue_learning_limit',
                'show_today_only'
            )
        }),
        ('Preferences', {
            'fields': (
                'theme_preference',
                'notifications_enabled'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )