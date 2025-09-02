from django.contrib import admin
from .models import UserDashboardSettings


@admin.register(UserDashboardSettings)
class UserDashboardSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for User Dashboard Settings
    """
    list_display = [
        'user',
        'user_role',
        'live_lessons_limit',
        'continue_learning_limit',
        'show_today_only',
        'theme_preference',
        'notifications_enabled',
        'updated_at'
    ]
    
    list_filter = [
        'show_today_only',
        'theme_preference',
        'notifications_enabled',
        'created_at',
        'updated_at'
    ]
    
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name'
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'id')
        }),
        ('Dashboard Display Settings', {
            'fields': (
                'live_lessons_limit',
                'continue_learning_limit',
                'show_today_only'
            ),
            'description': 'Configure how many items to show in each dashboard section'
        }),
        ('User Preferences', {
            'fields': (
                'theme_preference',
                'notifications_enabled'
            ),
            'description': 'User interface and notification preferences'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_role(self, obj):
        """Display the user's role"""
        return obj.user.role if hasattr(obj.user, 'role') else 'Unknown'
    user_role.short_description = 'User Role'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    def save_model(self, request, obj, form, change):
        """Custom save logic if needed"""
        super().save_model(request, obj, form, change)