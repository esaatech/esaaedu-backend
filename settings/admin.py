from django.contrib import admin
from .models import UserDashboardSettings, CourseSettings


@admin.register(CourseSettings)
class CourseSettingsAdmin(admin.ModelAdmin):
    """Admin interface for CourseSettings"""
    list_display = (
        'monthly_price_markup_percentage',
        'who_sets_price',
        'max_students_per_course',
        'default_course_duration_weeks',
        'enable_trial_period',
        'trial_period_days',
        'updated_at'
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Billing Settings', {
            'fields': ('monthly_price_markup_percentage', 'who_sets_price'),
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
        'user_type',
        'theme_preference',
        'notifications_enabled',
        'default_quiz_points',
        'default_assignment_points',
        'updated_at'
    )
    list_filter = ('user_type', 'theme_preference', 'notifications_enabled', 'auto_grade_multiple_choice', 'show_correct_answers_by_default')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'user_type'),
            'description': 'User and account type information'
        }),
        ('Display Settings', {
            'fields': (
                'live_lessons_limit',
                'continue_learning_limit',
                'show_today_only'
            ),
            'description': 'Dashboard display preferences'
        }),
        ('UI Preferences', {
            'fields': (
                'theme_preference',
                'notifications_enabled'
            ),
            'description': 'User interface and notification preferences'
        }),
        ('Teacher Settings', {
            'fields': (
                'default_quiz_points',
                'default_assignment_points',
                'default_course_passing_score',
                'default_quiz_time_limit',
                'auto_grade_multiple_choice',
                'show_correct_answers_by_default'
            ),
            'description': 'Default values for teachers when creating questions and courses',
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_fieldsets(self, request, obj=None):
        """Show teacher fields only for teacher users"""
        fieldsets = list(super().get_fieldsets(request, obj))
        
        # If editing an existing object and user is not a teacher, hide teacher fields
        if obj and obj.user_type != 'teacher':
            # Remove teacher settings fieldset
            fieldsets = [fs for fs in fieldsets if fs[0] != 'Teacher Settings']
        
        return fieldsets
    
    def get_readonly_fields(self, request, obj=None):
        """Make user_type readonly after creation"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:  # Editing existing object
            readonly_fields.append('user_type')
        return readonly_fields