from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from .models import User, TeacherProfile, StudentProfile
from .validators import get_all_timezone_choices_cached

# Lazy import for StudentWeeklyPerformance to avoid errors if migration hasn't been run
try:
    from .models import StudentWeeklyPerformance
except Exception:
    StudentWeeklyPerformance = None


class UserAdminChangeForm(UserChangeForm):
    """Dropdown for admin calendar IANA timezone (optional)."""

    admin_calendar_timezone = forms.ChoiceField(
        choices=get_all_timezone_choices_cached(),
        required=False,
        label="Admin calendar timezone",
        help_text=(
            "IANA zone for the admin dashboard class timetable. "
            "Leave blank to use System Settings calendar timezone (or Django TIME_ZONE)."
        ),
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.admin_calendar_timezone:
            current = self.instance.admin_calendar_timezone
            choices = list(self.fields["admin_calendar_timezone"].choices)
            if not any(c[0] == current for c in choices if c[0]):
                self.fields["admin_calendar_timezone"].choices = [
                    ("", "---------"),
                    (current, current),
                ] + [c for c in choices if c[0]]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminChangeForm
    list_display = ['email', 'public_handle', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['email', 'public_handle', 'first_name', 'last_name', 'firebase_uid']
    ordering = ['-date_joined']
    
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password', 'firebase_uid')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'username', 'public_handle')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Admin calendar', {
            'classes': ('collapse',),
            'fields': ('admin_calendar_timezone',),
            'description': (
                'Timezone for the Django admin dashboard timetable (staff). '
                'Empty means: System Settings calendar timezone, then Django TIME_ZONE.'
            ),
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'last_login_at')
        }),
    )
    
    add_fieldsets = (
        ('Create User', {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'firebase_uid', 'role', 'first_name', 'last_name', 'public_handle'),
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


class StudentProfileAdminForm(forms.ModelForm):
    """Use a dropdown for timezone in admin (all IANA timezones)."""
    timezone = forms.ChoiceField(
        choices=get_all_timezone_choices_cached(),
        required=False,
        label='Timezone',
    )

    class Meta:
        model = StudentProfile
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If instance has a timezone not in the list (e.g. deprecated IANA name), include it
        if self.instance and self.instance.pk and self.instance.timezone:
            current = self.instance.timezone
            choices = list(self.fields['timezone'].choices)
            if not any(c[0] == current for c in choices if c[0]):
                self.fields['timezone'].choices = [('', '---------'), (current, current)] + [
                    c for c in choices if c[0]
                ]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    form = StudentProfileAdminForm
    list_display = [
        'user', 'child_first_name', 'child_last_name', 'child_phone', 'parent_phone',
        'parent_email', 'grade_level', 'timezone',
        'overall_quiz_average_score', 'overall_assignment_average_score',
        'overall_average_score', 'age', 'created_at'
    ]
    list_filter = ['grade_level', 'notifications_enabled', 'created_at']
    search_fields = [
        'user__email', 'child_first_name', 'child_last_name', 'parent_name', 'parent_email',
        'child_phone', 'parent_phone',
    ]
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
                      'grade_level', 'date_of_birth', 'profile_image'),
            'description': (
                'Teacher SMS to the student uses child_phone only when that channel is chosen in the app; '
                'parent_phone is separate. API send may pass target_phone matching either normalized number.'
            ),
        }),
        ('Parent/Guardian Info', {
            'fields': ('parent_name', 'parent_email', 'parent_phone', 'emergency_contact'),
            'description': 'parent_email and parent_phone control parent-directed messaging reachability in teacher tools.',
        }),
        ('Learning & Preferences', {
            'fields': ('learning_goals', 'interests', 'notifications_enabled', 'email_notifications', 'timezone')
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


if StudentWeeklyPerformance:
    @admin.register(StudentWeeklyPerformance)
    class StudentWeeklyPerformanceAdmin(admin.ModelAdmin):
        list_display = [
            'student_profile', 'year', 'week_number', 'week_start_date',
            'overall_average', 'quiz_average', 'assignment_average',
            'quiz_count', 'assignment_count', 'updated_at'
        ]
        list_filter = ['year', 'week_number', 'updated_at']
        search_fields = ['student_profile__user__email', 'student_profile__child_first_name', 'student_profile__child_last_name']
        readonly_fields = ['created_at', 'updated_at']
        ordering = ['-year', '-week_number']
        
        fieldsets = (
            ('Student & Week', {
                'fields': ('student_profile', 'year', 'week_number', 'week_start_date')
            }),
            ('Weekly Performance', {
                'fields': (
                    'quiz_average', 'quiz_count',
                    'assignment_average', 'assignment_count',
                    'overall_average'
                ),
                'description': 'Weekly performance aggregates (automatically calculated)'
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        )
