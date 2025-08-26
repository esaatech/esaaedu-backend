from django.contrib import admin
from .models import Course, Lesson, Quiz, Question, CourseEnrollment, LessonProgress, QuizAttempt, Class, ClassSession, ClassEvent, CourseReview


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
            'fields': ('type', 'content')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


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


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'status', 'progress_percentage', 'enrolled_at']
    list_filter = ['status', 'enrolled_at', 'course__category']
    search_fields = ['student__email', 'course__title']
    readonly_fields = ['id', 'progress_percentage', 'completed_lessons_count', 'enrolled_at']


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'lesson', 'status', 'time_spent', 'completed_at']
    list_filter = ['status', 'completed_at']
    search_fields = ['enrollment__student__email', 'lesson__title']


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
    list_display = ['title', 'class_instance', 'event_type', 'start_time', 'end_time', 'duration_minutes', 'created_at']
    list_filter = ['event_type', 'start_time', 'class_instance__course__category', 'created_at']
    search_fields = ['title', 'description', 'class_instance__name', 'class_instance__course__title']
    readonly_fields = ['id', 'duration_minutes', 'created_at', 'updated_at']
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'class_instance', 'event_type')
        }),
        ('Schedule', {
            'fields': ('start_time', 'end_time', 'duration_minutes')
        }),
        ('Lesson Association', {
            'fields': ('lesson',),
            'description': 'Only required for lesson-type events'
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
    list_display = ['student_name', 'course', 'rating', 'is_verified', 'is_featured', 'created_at']
    list_filter = ['rating', 'is_verified', 'is_featured', 'student_age', 'created_at', 'course__category']
    search_fields = ['student_name', 'review_text', 'course__title']
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
            'fields': ('student_name', 'student_age')
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
