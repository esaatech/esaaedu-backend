from django.contrib import admin
from .models import (
    EnrolledCourse, StudentAttendance, StudentGrade, StudentBehavior, 
    StudentNote, StudentCommunication, StudentLessonProgress,
    LessonAssessment, TeacherAssessment, QuizQuestionFeedback, QuizAttemptFeedback,
    Conversation, Message
)


@admin.register(EnrolledCourse)
class EnrolledCourseAdmin(admin.ModelAdmin):
    list_display = [
        'student_profile', 'course', 'status', 'progress_percentage', 
        'enrollment_date', 'payment_status', 'last_accessed'
    ]
    list_filter = [
        'status', 'payment_status', 'enrollment_date', 'certificate_issued',
        'parent_notifications_enabled', 'final_grade_issued'
    ]
    search_fields = [
        'student_profile__user__email', 'student_profile__user__first_name', 
        'student_profile__user__last_name', 'course__title'
    ]
    readonly_fields = [
        'id', 'enrollment_date', 'created_at', 'updated_at', 'last_progress_update',
        'days_since_enrollment', 'days_since_last_access', 'completion_rate',
        'assignment_completion_rate', 'is_at_risk', 'is_active', 'is_completed'
    ]
    date_hierarchy = 'enrollment_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student_profile', 'course', 'status', 'enrolled_by')
        }),
        ('Academic Progress', {
            'fields': (
                'progress_percentage', 'current_lesson', 'completed_lessons_count', 
                'total_lessons_count', 'overall_grade', 'gpa_points', 'average_quiz_score'
            )
        }),
        ('Assignments', {
            'fields': ('total_assignments_completed', 'total_assignments_assigned')
        }),
        ('Engagement Analytics', {
            'fields': (
                'total_study_time', 'last_accessed', 'login_count', 
                'total_video_watch_time'
            )
        }),
        ('Financial', {
            'fields': (
                'payment_status', 'amount_paid', 'payment_due_date', 
                'discount_applied'
            )
        }),
        ('Completion & Certification', {
            'fields': (
                'completion_date', 'certificate_issued', 'certificate_url', 
                'final_grade_issued'
            )
        }),
        ('Communication Settings', {
            'fields': (
                'parent_notifications_enabled', 'reminder_emails_enabled', 
                'special_accommodations'
            )
        }),
        ('Computed Properties', {
            'fields': (
                'days_since_enrollment', 'days_since_last_access', 'completion_rate',
                'assignment_completion_rate', 'is_at_risk', 'is_active', 'is_completed'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'enrollment_date', 'created_at', 'updated_at', 'last_progress_update'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_completed', 'issue_certificates', 'update_progress']
    
    def mark_completed(self, request, queryset):
        for enrollment in queryset:
            enrollment.mark_completed()
        self.message_user(request, f'{queryset.count()} enrollments marked as completed.')
    mark_completed.short_description = "Mark selected enrollments as completed"
    
    def issue_certificates(self, request, queryset):
        count = 0
        for enrollment in queryset.filter(status='completed'):
            if enrollment.issue_certificate():
                count += 1
        self.message_user(request, f'{count} certificates issued.')
    issue_certificates.short_description = "Issue certificates for completed courses"
    
    def update_progress(self, request, queryset):
        for enrollment in queryset:
            enrollment.update_progress()
        self.message_user(request, f'Progress updated for {queryset.count()} enrollments.')
    update_progress.short_description = "Update progress for selected enrollments"


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'class_session', 'date', 'status', 'check_in_time', 'recorded_by']
    list_filter = ['status', 'date', 'class_session', 'recorded_by']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'class_session__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'class_session', 'date', 'status')
        }),
        ('Time Tracking', {
            'fields': ('check_in_time', 'check_out_time')
        }),
        ('Additional Info', {
            'fields': ('notes', 'recorded_by')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentGrade)
class StudentGradeAdmin(admin.ModelAdmin):
    list_display = ['student', 'title', 'grade_type', 'letter_grade', 'percentage', 'course', 'graded_date']
    list_filter = ['grade_type', 'letter_grade', 'course', 'graded_by', 'graded_date']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'title', 'course__title']
    readonly_fields = ['id', 'percentage', 'letter_grade', 'created_at', 'updated_at']
    date_hierarchy = 'graded_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'course', 'lesson', 'quiz_attempt')
        }),
        ('Assessment Details', {
            'fields': ('grade_type', 'title', 'description')
        }),
        ('Scoring', {
            'fields': ('points_earned', 'points_possible', 'percentage', 'letter_grade')
        }),
        ('Dates', {
            'fields': ('assigned_date', 'due_date', 'submitted_date')
        }),
        ('Feedback', {
            'fields': ('teacher_comments', 'private_notes', 'graded_by')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentBehavior)
class StudentBehaviorAdmin(admin.ModelAdmin):
    list_display = ['student', 'title', 'behavior_type', 'category', 'severity', 'incident_date', 'reported_by']
    list_filter = ['behavior_type', 'category', 'severity', 'parent_contacted', 'follow_up_required', 'incident_date']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'title', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'incident_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'class_session', 'incident_date')
        }),
        ('Behavior Details', {
            'fields': ('behavior_type', 'category', 'title', 'description', 'severity')
        }),
        ('Actions & Follow-up', {
            'fields': ('action_taken', 'parent_contacted', 'parent_contact_date', 'follow_up_required', 'follow_up_date')
        }),
        ('Tracking', {
            'fields': ('reported_by',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentNote)
class StudentNoteAdmin(admin.ModelAdmin):
    list_display = ['student', 'title', 'category', 'is_important', 'teacher', 'created_at']
    list_filter = ['category', 'is_private', 'is_important', 'teacher', 'created_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'title', 'content']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'teacher', 'category')
        }),
        ('Note Content', {
            'fields': ('title', 'content')
        }),
        ('Settings', {
            'fields': ('is_private', 'is_important')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentCommunication)
class StudentCommunicationAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'communication_type', 'purpose', 'sent_date', 'response_received', 'teacher']
    list_filter = ['communication_type', 'purpose', 'contacted_student', 'contacted_parent', 'response_received', 'follow_up_required']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'subject', 'message']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'sent_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'teacher', 'communication_type', 'purpose')
        }),
        ('Message Details', {
            'fields': ('subject', 'message')
        }),
        ('Recipients', {
            'fields': ('contacted_student', 'contacted_parent', 'parent_email', 'parent_phone')
        }),
        ('Response', {
            'fields': ('response_received', 'response_date', 'response_content')
        }),
        ('Follow-up', {
            'fields': ('follow_up_required', 'follow_up_date', 'follow_up_completed')
        }),
        ('Metadata', {
            'fields': ('id', 'sent_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentLessonProgress)
class StudentLessonProgressAdmin(admin.ModelAdmin):
    list_display = [
        'enrollment', 'lesson', 'status', 'time_spent', 'quiz_passed', 
        'best_quiz_score', 'completed_at', 'created_at'
    ]
    list_filter = [
        'status', 'quiz_passed', 'completed_at', 'created_at', 
        'enrollment__course', 'enrollment__student_profile__user'
    ]
    search_fields = [
        'enrollment__student_profile__user__email', 
        'enrollment__student_profile__user__first_name',
        'enrollment__student_profile__user__last_name', 
        'lesson__title', 'lesson__course__title'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('enrollment', 'lesson', 'status')
        }),
        ('Progress Tracking', {
            'fields': ('started_at', 'completed_at', 'time_spent', 'progress_data')
        }),
        ('Quiz Performance', {
            'fields': ('quiz_attempts_count', 'quiz_passed', 'best_quiz_score')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_completed', 'mark_in_progress', 'reset_progress']
    
    def mark_completed(self, request, queryset):
        """
        Mark lessons as completed - uses proper validation through enrollment.mark_lesson_complete()
        This ensures quiz requirements and order validation are enforced.
        """
        count = 0
        skipped = 0
        errors = []
        
        for progress in queryset:
            try:
                # Use the proper enrollment method which includes all validation
                success, message = progress.enrollment.mark_lesson_complete(
                    progress.lesson, 
                    require_quiz=True  # Always require quiz validation
                )
                if success:
                    count += 1
                else:
                    skipped += 1
                    errors.append(f"Lesson {progress.lesson.order}: {message}")
            except Exception as e:
                skipped += 1
                errors.append(f"Lesson {progress.lesson.order}: {str(e)}")
        
        message = f'{count} lessons marked as completed.'
        if skipped > 0:
            message += f' {skipped} lessons skipped (validation failed).'
        if errors:
            message += f' Errors: {"; ".join(errors[:5])}'  # Show first 5 errors
        self.message_user(request, message)
    mark_completed.short_description = "Mark selected lessons as completed (with validation)"
    
    def mark_in_progress(self, request, queryset):
        count = 0
        for progress in queryset.filter(status='not_started'):
            progress.mark_as_started()
            count += 1
        self.message_user(request, f'{count} lessons marked as in progress.')
    mark_in_progress.short_description = "Mark selected lessons as in progress"
    
    def reset_progress(self, request, queryset):
        for progress in queryset:
            progress.status = 'not_started'
            progress.started_at = None
            progress.completed_at = None
            progress.time_spent = 0
            progress.quiz_attempts_count = 0
            progress.quiz_passed = False
            progress.best_quiz_score = None
            progress.progress_data = {}
            progress.save()
        self.message_user(request, f'Progress reset for {queryset.count()} lessons.')
    reset_progress.short_description = "Reset progress for selected lessons"


@admin.register(LessonAssessment)
class LessonAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'enrollment', 'lesson', 'teacher', 'assessment_type', 'title', 
        'created_at', 'has_quiz_attempt'
    ]
    list_filter = [
        'assessment_type', 'created_at', 'teacher', 'enrollment__course'
    ]
    search_fields = [
        'title', 'content', 'enrollment__student_profile__user__first_name',
        'enrollment__student_profile__user__last_name', 'lesson__title',
        'teacher__first_name', 'teacher__last_name'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Assessment Details', {
            'fields': ('enrollment', 'lesson', 'teacher', 'assessment_type', 'title', 'content')
        }),
        ('Quiz Link', {
            'fields': ('quiz_attempt',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_quiz_attempt(self, obj):
        return obj.quiz_attempt is not None
    has_quiz_attempt.boolean = True
    has_quiz_attempt.short_description = 'Has Quiz Attempt'


@admin.register(TeacherAssessment)
class TeacherAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'enrollment', 'teacher', 'academic_performance', 'participation_level',
        'created_at', 'has_detailed_feedback'
    ]
    list_filter = [
        'academic_performance', 'participation_level', 'created_at', 'teacher',
        'enrollment__course'
    ]
    search_fields = [
        'enrollment__student_profile__user__first_name',
        'enrollment__student_profile__user__last_name',
        'teacher__first_name', 'teacher__last_name',
        'strengths', 'weaknesses', 'recommendations'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Assessment Overview', {
            'fields': ('enrollment', 'teacher', 'academic_performance', 'participation_level')
        }),
        ('Detailed Feedback', {
            'fields': ('strengths', 'weaknesses', 'recommendations', 'general_comments'),
            'classes': ('wide',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_detailed_feedback(self, obj):
        return bool(obj.strengths or obj.weaknesses or obj.recommendations)
    has_detailed_feedback.boolean = True
    has_detailed_feedback.short_description = 'Has Detailed Feedback'


@admin.register(QuizQuestionFeedback)
class QuizQuestionFeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'quiz_attempt', 'question', 'teacher', 'is_correct', 'points_earned',
        'points_possible', 'created_at'
    ]
    list_filter = [
        'is_correct', 'created_at', 'teacher', 'quiz_attempt__quiz__lessons__course'
    ]
    search_fields = [
        'feedback_text', 'quiz_attempt__student__first_name',
        'quiz_attempt__student__last_name', 'teacher__first_name', 'teacher__last_name',
        'question_text_snapshot'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'question_text_snapshot',
        'student_answer_snapshot', 'correct_answer_snapshot'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Feedback Details', {
            'fields': ('quiz_attempt', 'question', 'teacher', 'feedback_text')
        }),
        ('Scoring', {
            'fields': ('points_earned', 'points_possible', 'is_correct')
        }),
        ('Snapshots', {
            'fields': (
                'question_text_snapshot', 'student_answer_snapshot', 
                'correct_answer_snapshot'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(QuizAttemptFeedback)
class QuizAttemptFeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'quiz_attempt', 'teacher', 'overall_rating', 'created_at',
        'has_detailed_feedback'
    ]
    list_filter = [
        'overall_rating', 'created_at', 'teacher', 
        'quiz_attempt__quiz__lessons__course'
    ]
    search_fields = [
        'feedback_text', 'quiz_attempt__student__first_name',
        'quiz_attempt__student__last_name', 'teacher__first_name', 'teacher__last_name',
        'strengths_highlighted', 'areas_for_improvement'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Feedback Overview', {
            'fields': ('quiz_attempt', 'teacher', 'feedback_text', 'overall_rating')
        }),
        ('Detailed Assessment', {
            'fields': (
                'strengths_highlighted', 'areas_for_improvement', 
                'study_recommendations'
            ),
            'classes': ('wide',)
        }),
        ('Private Notes', {
            'fields': ('private_notes',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_detailed_feedback(self, obj):
        return obj.has_detailed_feedback
    has_detailed_feedback.boolean = True
    has_detailed_feedback.short_description = 'Has Detailed Feedback'


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'student_profile', 'teacher', 'recipient_type', 'course', 'subject',
        'last_message_at', 'created_at'
    ]
    list_filter = [
        'recipient_type', 'course', 'created_at', 'last_message_at', 'teacher'
    ]
    search_fields = [
        'student_profile__user__email', 'student_profile__user__first_name',
        'student_profile__user__last_name', 'teacher__email', 'teacher__first_name',
        'teacher__last_name', 'subject', 'course__title'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_message_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student_profile', 'teacher', 'recipient_type', 'course', 'subject')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_message_at')
        }),
        ('Metadata', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'conversation', 'sender', 'content_preview', 'created_at',
        'read_at', 'read_by', 'is_read'
    ]
    list_filter = [
        'read_at', 'created_at', 'conversation__recipient_type', 'sender'
    ]
    search_fields = [
        'content', 'sender__email', 'sender__first_name', 'sender__last_name',
        'conversation__student_profile__user__email',
        'conversation__teacher__email'
    ]
    readonly_fields = ['id', 'created_at', 'is_read']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Message Details', {
            'fields': ('conversation', 'sender', 'content')
        }),
        ('Read Status', {
            'fields': ('read_at', 'read_by', 'is_read')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        """Show first 50 characters of message content"""
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'