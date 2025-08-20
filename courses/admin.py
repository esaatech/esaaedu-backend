from django.contrib import admin
from .models import Course, Lesson, Quiz, Question, CourseEnrollment, LessonProgress, QuizAttempt


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
            'fields': ('age_range', 'duration', 'level', 'price', 'features')
        }),
        ('Display & Marketing', {
            'fields': ('featured', 'popular', 'color', 'icon')
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
