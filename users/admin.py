from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, TeacherProfile, StudentProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'firebase_uid']
    ordering = ['-date_joined']
    
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password', 'firebase_uid')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'username')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'last_login_at')
        }),
    )
    
    add_fieldsets = (
        ('Create User', {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'firebase_uid', 'role', 'first_name', 'last_name'),
        }),
    )
    
    readonly_fields = ['date_joined', 'last_login']


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'years_of_experience', 'created_at']
    list_filter = ['department', 'years_of_experience', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'bio', 'department']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Info', {
            'fields': ('user',)
        }),
        ('Professional Info', {
            'fields': ('bio', 'qualifications', 'department', 'specializations', 'years_of_experience')
        }),
        ('Contact & Social', {
            'fields': ('phone_number', 'linkedin_url', 'twitter_url', 'profile_image')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'child_first_name', 'child_last_name', 'grade_level', 
        'overall_quiz_average_score', 'overall_assignment_average_score', 
        'overall_average_score', 'age', 'created_at'
    ]
    list_filter = ['grade_level', 'notifications_enabled', 'created_at']
    search_fields = ['user__email', 'child_first_name', 'child_last_name', 'parent_name', 'parent_email']
    readonly_fields = [
        'created_at', 'updated_at', 'age', 'last_performance_update',
        'total_quizzes_completed', 'total_assignments_completed',
        'overall_quiz_average_score', 'overall_assignment_average_score', 'overall_average_score'
    ]
    
    fieldsets = (
        ('User Account', {
            'fields': ('user',)
        }),
        ('Child Information', {
            'fields': ('child_first_name', 'child_last_name', 'child_email', 'child_phone', 
                      'grade_level', 'date_of_birth', 'profile_image')
        }),
        ('Parent/Guardian Info', {
            'fields': ('parent_name', 'parent_email', 'parent_phone', 'emergency_contact')
        }),
        ('Learning & Preferences', {
            'fields': ('learning_goals', 'interests', 'notifications_enabled', 'email_notifications')
        }),
        ('Performance Aggregates', {
            'fields': (
                'total_quizzes_completed',
                'total_assignments_completed',
                'overall_quiz_average_score',
                'overall_assignment_average_score',
                'overall_average_score',
                'last_performance_update'
            ),
            'description': 'Overall performance statistics across all courses (automatically updated)'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'age'),
            'classes': ('collapse',)
        }),
    )
