from django.contrib import admin
from .models import Course, Lesson, LessonMaterial, Quiz, Question, QuizAttempt, Class, ClassSession, ClassEvent, CourseReview, CourseCategory, Project, ProjectSubmission, Assignment, AssignmentQuestion, AssignmentSubmission, ProjectPlatform


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'category', 'level', 'status', 'featured', 'popular', 'enrolled_students_count', 'created_at']
    list_filter = ['status', 'level', 'category', 'featured', 'popular', 'created_at']
    search_fields = ['title', 'description', 'teacher__email', 'teacher__first_name', 'teacher__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'total_lessons', 'enrolled_students_count']
    actions = ['approve_courses', 'feature_courses', 'unfeature_courses']
    
    def approve_courses(self, request, queryset):
        updated = queryset.filter(status='draft').update(status='published')
        self.message_user(request, f'{updated} courses were approved and published.')
    approve_courses.short_description = "Approve selected draft courses"
    
    def feature_courses(self, request, queryset):
        updated = queryset.update(featured=True)
        self.message_user(request, f'{updated} courses were marked as featured.')
    feature_courses.short_description = "Mark selected courses as featured"
    
    def unfeature_courses(self, request, queryset):
        updated = queryset.update(featured=False)
        self.message_user(request, f'{updated} courses were unmarked as featured.')
    unfeature_courses.short_description = "Remove featured status from selected courses"
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'long_description', 'teacher', 'category')
        }),
        ('Course Details', {
            'fields': ('age_range', 'level', 'price', 'features')
        }),
        ('Introduction/Detailed Info', {
            'fields': ('overview', 'learning_objectives', 'prerequisites_text', 
                      'duration_weeks', 'sessions_per_week', 'total_projects', 'value_propositions'),
            'classes': ('collapse',)
        }),
        ('Display & Marketing', {
            'fields': ('featured', 'popular', 'color', 'icon', 'image')
        }),
        ('Settings', {
            'fields': ('max_students', 'schedule', 'certificate', 'status')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'total_lessons', 'enrolled_students_count'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'type', 'duration', 'created_at']
    list_filter = ['type', 'course__category', 'created_at']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('course', 'title', 'description', 'order', 'duration')
        }),
        ('Lesson Content', {
            'fields': ('type', 'text_content', 'video_url', 'audio_url', 'live_class_date', 'live_class_status', 'content')
        }),
        ('Materials', {
            'fields': ('materials',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LessonMaterial)
class LessonMaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'material_type', 'is_required', 'order', 'created_at']
    list_filter = ['material_type', 'is_required', 'is_downloadable', 'created_at']
    search_fields = ['title', 'description', 'lesson__title', 'lesson__course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lesson', 'title', 'description', 'material_type')
        }),
        ('File/Resource', {
            'fields': ('file_url', 'file_size', 'file_extension')
        }),
        ('Settings', {
            'fields': ('is_required', 'is_downloadable', 'order')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lesson', 'lesson__course')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'passing_score', 'max_attempts', 'question_count', 'created_at']
    list_filter = ['passing_score', 'max_attempts', 'show_correct_answers', 'created_at']
    search_fields = ['title', 'description', 'lesson__title']
    readonly_fields = ['id', 'question_count', 'total_points', 'created_at', 'updated_at']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text_short', 'quiz', 'order', 'type', 'points', 'created_at']
    list_filter = ['type', 'points', 'created_at']
    search_fields = ['question_text', 'quiz__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'






@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'attempt_number', 'score', 'passed', 'completed_at']
    list_filter = ['passed', 'completed_at']
    search_fields = ['student__email', 'quiz__title']
    readonly_fields = ['id', 'started_at']


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'teacher', 'student_count', 'max_capacity', 'session_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'course__category', 'created_at']
    search_fields = ['name', 'course__title', 'teacher__email', 'description']
    readonly_fields = ['id', 'student_count', 'is_full', 'available_spots', 'session_count', 'formatted_schedule', 'created_at', 'updated_at']
    filter_horizontal = ['students']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'course', 'teacher')
        }),
        ('Class Configuration', {
            'fields': ('max_capacity', 'meeting_link')
        }),
        ('Schedule', {
            'fields': ('formatted_schedule', 'session_count'),
            'classes': ('collapse',)
        }),
        ('Students', {
            'fields': ('students',)
        }),
        ('Status & Dates', {
            'fields': ('is_active', 'start_date', 'end_date')
        }),
        ('Metadata', {
            'fields': ('id', 'student_count', 'is_full', 'available_spots', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def student_count(self, obj):
        return obj.student_count
    student_count.short_description = 'Students'


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'class_instance', 'day_of_week', 'start_time', 'end_time', 'session_number', 'is_active']
    list_filter = ['day_of_week', 'is_active', 'class_instance__course__category']
    search_fields = ['name', 'class_instance__name', 'class_instance__course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'class_instance', 'session_number')
        }),
        ('Schedule', {
            'fields': ('day_of_week', 'start_time', 'end_time')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ClassEvent)
class ClassEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'class_instance', 'event_type', 'lesson_type', 'project', 'project_platform', 'due_date', 'start_time', 'end_time', 'duration_minutes', 'created_at']
    list_filter = ['event_type', 'lesson_type', 'project_platform', 'submission_type', 'start_time', 'class_instance__course__category', 'created_at']
    search_fields = ['title', 'description', 'class_instance__name', 'class_instance__course__title', 'project__title', 'project_title']
    readonly_fields = ['id', 'duration_minutes', 'created_at', 'updated_at']
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'class_instance', 'event_type', 'lesson_type')
        }),
        ('Schedule', {
            'fields': ('start_time', 'end_time', 'duration_minutes'),
            'description': 'Required for lesson/meeting/break events. Leave empty for project events.'
        }),
        ('Project Details', {
            'fields': ('due_date', 'project_title', 'submission_type'),
            'description': 'Required for project events. Leave empty for other event types.',
            'classes': ('collapse',)
        }),
        ('Event Content', {
            'fields': ('lesson', 'project', 'project_platform'),
            'description': 'Select lesson for lesson events, or project + platform for project events'
        }),
        ('Meeting Details (for Live Lessons)', {
            'fields': ('meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password'),
            'description': 'Meeting details for live lessons. Leave empty for non-live lessons.',
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('class_instance', 'class_instance__course', 'lesson')


# CourseIntroduction admin removed - all fields are now managed in CourseAdmin


@admin.register(CourseReview)
class CourseReviewAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'parent_name', 'course', 'rating', 'is_verified', 'is_featured', 'created_at']
    list_filter = ['rating', 'is_verified', 'is_featured', 'student_age', 'created_at', 'course__category']
    search_fields = ['student_name', 'parent_name', 'review_text', 'course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    actions = ['verify_reviews', 'unverify_reviews', 'feature_reviews', 'unfeature_reviews']
    
    def verify_reviews(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} reviews were marked as verified.')
    verify_reviews.short_description = "Mark selected reviews as verified"
    
    def unverify_reviews(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} reviews were unmarked as verified.')
    unverify_reviews.short_description = "Remove verified status from selected reviews"
    
    def feature_reviews(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} reviews were marked as featured.')
    feature_reviews.short_description = "Mark selected reviews as featured"
    
    def unfeature_reviews(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} reviews were unmarked as featured.')
    unfeature_reviews.short_description = "Remove featured status from selected reviews"
    
    fieldsets = (
        ('Student Information', {
            'fields': ('student_name', 'student_age', 'parent_name')
        }),
        ('Review Content', {
            'fields': ('course', 'rating', 'review_text')
        }),
        ('Review Management', {
            'fields': ('is_verified', 'is_featured')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('course')


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_short', 'course_count']
    list_filter = []
    search_fields = ['name', 'description']
    readonly_fields = ['id']
    actions = ['duplicate_categories']
    
    def description_short(self, obj):
        return obj.description[:100] + "..." if len(obj.description) > 100 else obj.description
    description_short.short_description = 'Description'
    
    def course_count(self, obj):
        return Course.objects.filter(category=obj.name).count()
    course_count.short_description = 'Courses'
    
    def duplicate_categories(self, request, queryset):
        """Action to duplicate selected categories with a suffix"""
        duplicated_count = 0
        for category in queryset:
            new_category = CourseCategory.objects.create(
                name=f"{category.name} (Copy)",
                description=category.description
            )
            duplicated_count += 1
        self.message_user(request, f'{duplicated_count} categories were duplicated.')
    duplicate_categories.short_description = "Duplicate selected categories"
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Statistics', {
            'fields': ('course_count',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'course', 'submission_type', 'points', 'due_at', 
        'submission_count', 'graded_count', 'pending_count', 'created_at'
    ]
    list_filter = [
        'submission_type', 'created_at', 'due_at', 'course__teacher'
    ]
    search_fields = [
        'title', 'instructions', 'course__title', 'course__teacher__first_name',
        'course__teacher__last_name', 'course__teacher__email'
    ]
    readonly_fields = ['id', 'created_at', 'submission_count', 'graded_count', 'pending_count']
    date_hierarchy = 'created_at'
    actions = ['duplicate_projects', 'extend_due_dates']
    
    def submission_count(self, obj):
        return obj.submissions.count()
    submission_count.short_description = 'Total Submissions'
    
    def graded_count(self, obj):
        return obj.submissions.filter(status='GRADED').count()
    graded_count.short_description = 'Graded'
    
    def pending_count(self, obj):
        return obj.submissions.filter(status__in=['ASSIGNED', 'SUBMITTED', 'RETURNED']).count()
    pending_count.short_description = 'Pending'
    
    def duplicate_projects(self, request, queryset):
        """Action to duplicate selected projects"""
        duplicated_count = 0
        for project in queryset:
            new_project = Project.objects.create(
                course=project.course,
                title=f"{project.title} (Copy)",
                instructions=project.instructions,
                submission_type=project.submission_type,
                allowed_file_types=project.allowed_file_types,
                points=project.points,
                due_at=project.due_at
            )
            duplicated_count += 1
        self.message_user(request, f'{duplicated_count} projects were duplicated.')
    duplicate_projects.short_description = "Duplicate selected projects"
    
    def extend_due_dates(self, request, queryset):
        """Action to extend due dates by 1 week"""
        from datetime import timedelta
        updated_count = 0
        for project in queryset:
            if project.due_at:
                project.due_at += timedelta(weeks=1)
                project.save()
                updated_count += 1
        self.message_user(request, f'{updated_count} project due dates were extended by 1 week.')
    extend_due_dates.short_description = "Extend due dates by 1 week"
    
    fieldsets = (
        ('Project Details', {
            'fields': ('course', 'title', 'instructions', 'submission_type', 'points', 'due_at')
        }),
        ('File Upload Settings', {
            'fields': ('allowed_file_types',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('submission_count', 'graded_count', 'pending_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('course', 'course__teacher')


@admin.register(ProjectSubmission)
class ProjectSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'project', 'student_name', 'status', 'points_earned', 
        'submitted_at', 'graded_at', 'feedback_checked', 'created_at'
    ]
    list_filter = [
        'status', 'feedback_checked', 'submitted_at', 'graded_at', 
        'project__course', 'project__submission_type'
    ]
    search_fields = [
        'project__title', 'student__first_name', 'student__last_name', 
        'student__email', 'content', 'feedback'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'submitted_at', 'graded_at']
    date_hierarchy = 'submitted_at'
    actions = ['mark_as_graded', 'mark_as_returned', 'reset_submissions']
    
    def student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip() or obj.student.email
    student_name.short_description = 'Student'
    
    def mark_as_graded(self, request, queryset):
        """Action to mark submissions as graded"""
        from django.utils import timezone
        updated = queryset.filter(status__in=['SUBMITTED', 'RETURNED']).update(
            status='GRADED',
            graded_at=timezone.now(),
            grader=request.user
        )
        self.message_user(request, f'{updated} submissions were marked as graded.')
    mark_as_graded.short_description = "Mark selected submissions as graded"
    
    def mark_as_returned(self, request, queryset):
        """Action to mark submissions as returned for revision"""
        from django.utils import timezone
        updated = queryset.filter(status='SUBMITTED').update(
            status='RETURNED',
            graded_at=timezone.now(),
            grader=request.user
        )
        self.message_user(request, f'{updated} submissions were marked as returned.')
    mark_as_returned.short_description = "Mark selected submissions as returned"
    
    def reset_submissions(self, request, queryset):
        """Action to reset submissions to assigned status"""
        updated = queryset.update(
            status='ASSIGNED',
            content='',
            file_url='',
            reflection='',
            submitted_at=None,
            graded_at=None,
            grader=None,
            points_earned=None,
            feedback='',
            feedback_response='',
            feedback_checked=False,
            feedback_checked_at=None
        )
        self.message_user(request, f'{updated} submissions were reset to assigned status.')
    reset_submissions.short_description = "Reset selected submissions"
    
    fieldsets = (
        ('Submission Details', {
            'fields': ('project', 'student', 'status', 'content', 'file_url', 'reflection')
        }),
        ('Grading', {
            'fields': ('points_earned', 'feedback', 'feedback_response', 'grader'),
            'classes': ('collapse',)
        }),
        ('Feedback Tracking', {
            'fields': ('feedback_checked', 'feedback_checked_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'graded_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'project', 'project__course', 'student', 'grader'
        )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'assignment_type', 'passing_score', 'max_attempts', 'due_date', 'question_count', 'submission_count', 'created_at']
    list_filter = ['assignment_type', 'passing_score', 'max_attempts', 'show_correct_answers', 'randomize_questions', 'created_at']
    search_fields = ['title', 'description', 'lesson__title', 'lesson__course__title', 'lesson__course__teacher__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'question_count', 'submission_count']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lesson', 'title', 'description', 'assignment_type')
        }),
        ('Assignment Settings', {
            'fields': ('due_date', 'passing_score', 'max_attempts', 'show_correct_answers', 'randomize_questions')
        }),
        ('Statistics', {
            'fields': ('question_count', 'submission_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'
    
    def submission_count(self, obj):
        return obj.submissions.count()
    submission_count.short_description = 'Submissions'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'lesson', 'lesson__course', 'lesson__course__teacher'
        ).prefetch_related('questions', 'submissions')


@admin.register(AssignmentQuestion)
class AssignmentQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text_short', 'assignment', 'type', 'points', 'order', 'created_at']
    list_filter = ['type', 'points', 'assignment__assignment_type', 'created_at']
    search_fields = ['question_text', 'assignment__title', 'assignment__lesson__title', 'assignment__lesson__course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Question Information', {
            'fields': ('assignment', 'question_text', 'type', 'content', 'points', 'order', 'explanation')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question Text'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'assignment', 'assignment__lesson', 'assignment__lesson__course'
        )


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'assignment_title', 'attempt_number', 'points_earned', 'points_possible', 'percentage', 'passed', 'is_graded', 'submitted_at']
    list_filter = ['is_graded', 'passed', 'attempt_number', 'assignment__assignment_type', 'submitted_at', 'graded_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'assignment__title', 'assignment__lesson__title']
    readonly_fields = ['id', 'submitted_at', 'graded_at', 'percentage', 'passed']
    date_hierarchy = 'submitted_at'
    
    fieldsets = (
        ('Submission Information', {
            'fields': ('student', 'assignment', 'enrollment', 'attempt_number', 'answers', 'submitted_at')
        }),
        ('Grading', {
            'fields': ('is_graded', 'points_earned', 'points_possible', 'percentage', 'passed', 'graded_by', 'graded_at', 'graded_questions')
        }),
        ('Feedback', {
            'fields': ('instructor_feedback', 'feedback_checked', 'feedback_checked_at', 'feedback_response'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )
    
    def student_name(self, obj):
        return obj.student.get_full_name() or obj.student.email
    student_name.short_description = 'Student'
    
    def assignment_title(self, obj):
        return obj.assignment.title
    assignment_title.short_description = 'Assignment'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'student', 'assignment', 'assignment__lesson', 'assignment__lesson__course', 'graded_by', 'enrollment'
        )


@admin.register(ProjectPlatform)
class ProjectPlatformAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'platform_type', 'age_range_display', 'is_active', 'is_featured', 'is_free', 'usage_count', 'created_at']
    list_filter = ['platform_type', 'is_active', 'is_featured', 'is_free', 'requires_authentication', 'supports_collaboration', 'created_at']
    search_fields = ['name', 'display_name', 'description', 'supported_languages']
    readonly_fields = ['id', 'usage_count', 'created_at', 'updated_at', 'age_range_display', 'capabilities_display']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'platform_type')
        }),
        ('Technical Details', {
            'fields': ('base_url', 'api_endpoint', 'supported_languages', 'platform_config'),
            'classes': ('collapse',)
        }),
        ('Platform Capabilities', {
            'fields': ('requires_authentication', 'supports_collaboration', 'supports_file_upload', 
                      'supports_live_preview', 'supports_version_control'),
            'classes': ('collapse',)
        }),
        ('Visual & Branding', {
            'fields': ('icon', 'color', 'logo_url'),
            'classes': ('collapse',)
        }),
        ('Age & Skill Level', {
            'fields': ('min_age', 'max_age', 'skill_levels'),
            'classes': ('collapse',)
        }),
        ('Status & Features', {
            'fields': ('is_active', 'is_featured', 'is_free')
        }),
        ('Statistics', {
            'fields': ('usage_count', 'capabilities_display'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def age_range_display(self, obj):
        return obj.age_range_display
    age_range_display.short_description = 'Age Range'
    
    def capabilities_display(self, obj):
        return ', '.join(obj.capabilities_display) or 'None'
    capabilities_display.short_description = 'Capabilities'
    
    actions = ['activate_platforms', 'deactivate_platforms', 'feature_platforms', 'unfeature_platforms']
    
    def activate_platforms(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} platforms were activated.')
    activate_platforms.short_description = "Activate selected platforms"
    
    def deactivate_platforms(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} platforms were deactivated.')
    deactivate_platforms.short_description = "Deactivate selected platforms"
    
    def feature_platforms(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} platforms were featured.')
    feature_platforms.short_description = "Feature selected platforms"
    
    def unfeature_platforms(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} platforms were unfeatured.')
    unfeature_platforms.short_description = "Remove featured status from selected platforms"
