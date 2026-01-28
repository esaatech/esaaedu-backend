from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Course, Lesson, LessonMaterial, Quiz, Question, QuizAttempt, Class, ClassSession, ClassEvent, CourseReview, CourseCategory, Project, ProjectSubmission, Assignment, AssignmentQuestion, AssignmentSubmission, ProjectPlatform, SubmissionType, Note, BookPage, VideoMaterial, DocumentMaterial, Classroom, Board, BoardPage, CourseAssessment, CourseAssessmentQuestion, CourseAssessmentSubmission
from .views import delete_course_with_cleanup


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'category', 'level', 'status', 'featured', 'popular', 'enrolled_students_count', 'created_at']
    list_filter = ['status', 'level', 'category', 'featured', 'popular', 'created_at']
    search_fields = ['title', 'description', 'teacher__email', 'teacher__first_name', 'teacher__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'total_lessons', 'enrolled_students_count', 'get_full_landing_page_url_display']
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
            'fields': ('age_range', 'level', 'required_computer_skills_level', 'delivery_type', 'price', 'features')
        }),
        ('Introduction/Detailed Info', {
            'fields': ('overview', 'learning_objectives', 'prerequisites_text', 
                      'duration_weeks', 'sessions_per_week', 'total_projects', 'value_propositions'),
            'classes': ('collapse',)
        }),
        ('Display & Marketing', {
            'fields': ('featured', 'popular', 'color', 'icon', 'image', 'landing_page_url', 'get_full_landing_page_url_display')
        }),
        ('Settings', {
            'fields': ('max_students', 'schedule', 'certificate', 'status')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'total_lessons', 'enrolled_students_count'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_landing_page_url_display(self, obj):
        """
        Display full landing page URL with copy button in Django Admin
        """
        if not obj:
            return "-"
        
        # Get request from admin instance if available
        request = getattr(self, '_request', None)
        full_url = obj.get_full_landing_page_url(request=request)
        
        # Create unique IDs for this instance
        input_id = f"landing-url-{obj.id}"
        button_id = f"copy-btn-{obj.id}"
        
        # Create HTML with URL and copy button
        html = format_html(
            '''
            <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px;">
                <input type="text" 
                       id="{}" 
                       value="{}" 
                       readonly 
                       style="flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 13px; background-color: #f9f9f9;"
                       onclick="this.select();">
                <button type="button" 
                        id="{}"
                        style="padding: 8px 16px; background-color: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                    Copy
                </button>
            </div>
            <script>
                (function() {{
                    var inputId = '{}';
                    var buttonId = '{}';
                    var button = document.getElementById(buttonId);
                    
                    if (button) {{
                        button.addEventListener('click', function() {{
                            var input = document.getElementById(inputId);
                            var url = input.value;
                            var originalText = button.textContent;
                            
                            // Try modern clipboard API first
                            if (navigator.clipboard && window.isSecureContext) {{
                                navigator.clipboard.writeText(url).then(function() {{
                                    button.textContent = 'Copied!';
                                    button.style.backgroundColor = '#28a745';
                                    
                                    setTimeout(function() {{
                                        button.textContent = originalText;
                                        button.style.backgroundColor = '#007cba';
                                    }}, 2000);
                                }}).catch(function(err) {{
                                    console.error('Clipboard API failed:', err);
                                    fallbackCopy();
                                }});
                            }} else {{
                                fallbackCopy();
                            }}
                            
                            function fallbackCopy() {{
                                input.select();
                                input.setSelectionRange(0, 99999);
                                
                                try {{
                                    var successful = document.execCommand('copy');
                                    if (successful) {{
                                        button.textContent = 'Copied!';
                                        button.style.backgroundColor = '#28a745';
                                        
                                        setTimeout(function() {{
                                            button.textContent = originalText;
                                            button.style.backgroundColor = '#007cba';
                                        }}, 2000);
                                    }} else {{
                                        alert('Failed to copy. Please select and copy manually.');
                                    }}
                                }} catch(err) {{
                                    console.error('execCommand failed:', err);
                                    alert('Failed to copy. Please select and copy manually.');
                                }}
                            }}
                        }});
                    }}
                }})();
            </script>
            ''',
            input_id,
            full_url,
            button_id,
            input_id,
            button_id
        )
        return html
    
    get_full_landing_page_url_display.short_description = 'Full Landing Page URL'
    
    def get_form(self, request, obj=None, **kwargs):
        """Store request object for use in display methods"""
        form = super().get_form(request, obj, **kwargs)
        self._request = request
        return form
    
    def save_model(self, request, obj, form, change):
        """
        Override save_model to trigger Stripe updates when price or duration changes.
        This ensures admin updates sync with Stripe, just like API updates.
        """
        # Store original values before save to detect changes
        original_price = None
        original_duration_weeks = None
        original_is_free = None
        
        if change and obj.pk:  # Only check for updates, not new objects
            try:
                original_obj = Course.objects.get(pk=obj.pk)
                original_price = original_obj.price
                original_duration_weeks = original_obj.duration_weeks
                original_is_free = getattr(original_obj, 'is_free', False)
            except Course.DoesNotExist:
                pass
        
        # Call parent save to actually save the model
        super().save_model(request, obj, form, change)
        
        # Check if billing-related fields changed and trigger Stripe update
        if change and obj.pk:  # Only for updates, not new objects
            price_changed = (
                original_price is not None and 
                (obj.price != original_price or getattr(obj, 'is_free', False) != original_is_free)
            )
            duration_changed = (
                original_duration_weeks is not None and 
                obj.duration_weeks != original_duration_weeks
            )
            
            if price_changed or duration_changed:
                # Check if billing product exists (course might not have Stripe setup yet)
                from billings.models import BillingProduct
                try:
                    # Only update if billing product exists
                    BillingProduct.objects.get(course=obj)
                    from .stripe_integration import update_stripe_product_for_course
                    stripe_result = update_stripe_product_for_course(obj)
                    
                    if stripe_result['success']:
                        self.message_user(
                            request,
                            f'Course updated and Stripe prices synced successfully.',
                            messages.SUCCESS
                        )
                    else:
                        self.message_user(
                            request,
                            f'Course updated but Stripe sync failed: {stripe_result.get("error", "Unknown error")}',
                            messages.WARNING
                        )
                except BillingProduct.DoesNotExist:
                    # Course doesn't have Stripe product yet - this is normal for new courses
                    # Stripe product will be created when course is published or via API
                    pass
    
    def delete_model(self, request, obj):
        """
        Override delete_model to use the shared cleanup function.
        This ensures admins use the same deletion logic as API endpoints,
        preventing orphaned data in GCS and Stripe.
        Admins can delete courses with enrollments (skip_enrollment_check=True).
        """
        result = delete_course_with_cleanup(obj, skip_enrollment_check=True)
        
        if result['success']:
            self.message_user(
                request,
                f'Course "{result["course_title"]}" and all related data deleted successfully.',
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                f'Failed to delete course: {result.get("error", "Unknown error")}',
                messages.ERROR
            )
            # Raise exception to prevent Django admin from proceeding with default delete
            raise Exception(result.get('error', 'Failed to delete course'))


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
    list_display = ['title', 'get_lessons', 'material_type', 'is_required', 'order', 'created_at']
    list_filter = ['material_type', 'is_required', 'is_downloadable', 'created_at']
    search_fields = ['title', 'description', 'lessons__title', 'lessons__course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['lessons']
    
    def get_lessons(self, obj):
        """Display lessons as a comma-separated list"""
        return ", ".join([lesson.title for lesson in obj.lessons.all()])
    get_lessons.short_description = 'Lessons'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lessons', 'title', 'description', 'material_type')
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
        return super().get_queryset(request).prefetch_related('lessons', 'lessons__course')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_lessons', 'passing_score', 'max_attempts', 'question_count', 'created_at']
    list_filter = ['passing_score', 'max_attempts', 'show_correct_answers', 'created_at']
    search_fields = ['title', 'description', 'lessons__title']
    readonly_fields = ['id', 'question_count', 'total_points', 'created_at', 'updated_at']
    filter_horizontal = ['lessons']
    
    def get_lessons(self, obj):
        """Display lessons associated with this quiz"""
        lessons = obj.lessons.all()[:3]
        lesson_names = ', '.join([lesson.title for lesson in lessons])
        if obj.lessons.count() > 3:
            lesson_names += f' ... (+{obj.lessons.count() - 3} more)'
        return lesson_names or 'No lessons'
    get_lessons.short_description = 'Lessons'


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
    list_display = ['title', 'class_instance', 'event_type', 'lesson_type', 'project', 'project_platform', 'assessment', 'due_date', 'start_time', 'end_time', 'duration_minutes', 'created_at']
    list_filter = ['event_type', 'lesson_type', 'project_platform', 'submission_type', 'start_time', 'class_instance__course__category', 'created_at']
    search_fields = ['title', 'description', 'class_instance__name', 'class_instance__course__title', 'project__title', 'project_title', 'assessment__title']
    readonly_fields = ['id', 'duration_minutes', 'created_at', 'updated_at']
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'class_instance', 'event_type', 'lesson_type')
        }),
        ('Schedule', {
            'fields': ('start_time', 'end_time', 'duration_minutes'),
            'description': 'Required for lesson/meeting/break/test/exam events. Leave empty for project events.'
        }),
        ('Project Details', {
            'fields': ('due_date', 'project_title', 'submission_type'),
            'description': 'Required for project events. Leave empty for other event types.',
            'classes': ('collapse',)
        }),
        ('Event Content', {
            'fields': ('lesson', 'project', 'project_platform', 'assessment'),
            'description': 'Select lesson for lesson events, project + platform for project events, or assessment for test/exam events'
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
        return super().get_queryset(request).select_related('class_instance', 'class_instance__course', 'lesson', 'assessment')


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
    list_display = ['title', 'get_lessons', 'assignment_type', 'passing_score', 'max_attempts', 'due_date', 'question_count', 'submission_count', 'created_at']
    list_filter = ['assignment_type', 'passing_score', 'max_attempts', 'show_correct_answers', 'randomize_questions', 'created_at']
    search_fields = ['title', 'description', 'lessons__title', 'lessons__course__title', 'lessons__course__teacher__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'question_count', 'submission_count']
    date_hierarchy = 'created_at'
    filter_horizontal = ['lessons']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lessons', 'title', 'description', 'assignment_type')
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
    
    def get_lessons(self, obj):
        """Display lessons associated with this assignment"""
        lessons = obj.lessons.all()[:3]
        lesson_names = ', '.join([lesson.title for lesson in lessons])
        if obj.lessons.count() > 3:
            lesson_names += f' ... (+{obj.lessons.count() - 3} more)'
        return lesson_names or 'No lessons'
    get_lessons.short_description = 'Lessons'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'lessons', 'lessons__course', 'lessons__course__teacher', 'questions', 'submissions'
        )


@admin.register(AssignmentQuestion)
class AssignmentQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text_short', 'assignment', 'type', 'points', 'order', 'created_at']
    list_filter = ['type', 'points', 'assignment__assignment_type', 'created_at']
    search_fields = ['question_text', 'assignment__title', 'assignment__lessons__title', 'assignment__lessons__course__title']
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
            'assignment'
        ).prefetch_related(
            'assignment__lessons', 'assignment__lessons__course'
        )


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'assignment_title', 'attempt_number', 'status', 'points_earned', 'points_possible', 'percentage', 'passed', 'is_graded', 'is_teacher_draft', 'submitted_at']
    list_filter = ['status', 'is_graded', 'is_teacher_draft', 'passed', 'attempt_number', 'assignment__assignment_type', 'submitted_at', 'graded_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'assignment__title', 'assignment__lessons__title']
    readonly_fields = ['id', 'submitted_at', 'graded_at', 'percentage', 'passed']
    date_hierarchy = 'submitted_at'
    actions = ['mark_as_draft', 'mark_as_submitted', 'mark_as_graded']
    
    fieldsets = (
        ('Submission Information', {
            'fields': ('student', 'assignment', 'enrollment', 'attempt_number', 'status', 'answers', 'submitted_at')
        }),
        ('Grading', {
            'fields': ('is_graded', 'is_teacher_draft', 'points_earned', 'points_possible', 'percentage', 'passed', 'graded_by', 'graded_at', 'graded_questions')
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
            'student', 'assignment', 'graded_by', 'enrollment'
        ).prefetch_related(
            'assignment__lessons', 'assignment__lessons__course'
        )
    
    def mark_as_draft(self, request, queryset):
        """Action to mark submissions as draft"""
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} submissions were marked as draft.')
    mark_as_draft.short_description = "Mark selected submissions as draft"
    
    def mark_as_submitted(self, request, queryset):
        """Action to mark submissions as submitted"""
        updated = queryset.update(status='submitted')
        self.message_user(request, f'{updated} submissions were marked as submitted.')
    mark_as_submitted.short_description = "Mark selected submissions as submitted"
    
    def mark_as_graded(self, request, queryset):
        """Action to mark submissions as graded"""
        from django.utils import timezone
        updated = queryset.update(status='graded', is_graded=True, graded_at=timezone.now(), graded_by=request.user)
        self.message_user(request, f'{updated} submissions were marked as graded.')
    mark_as_graded.short_description = "Mark selected submissions as graded"


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


@admin.register(SubmissionType)
class SubmissionTypeAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'requires_file_upload', 'requires_text_input', 'requires_url_input', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'requires_file_upload', 'requires_text_input', 'requires_url_input', 'created_at']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['order', 'display_name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'icon', 'order')
        }),
        ('Submission Requirements', {
            'fields': ('requires_file_upload', 'requires_text_input', 'requires_url_input')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_types', 'deactivate_types']
    
    def activate_types(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} submission types were activated.')
    activate_types.short_description = "Activate selected submission types"
    
    def deactivate_types(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} submission types were deactivated.')
    deactivate_types.short_description = "Deactivate selected submission types"


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'course', 'category', 'lesson', 'created_at', 'updated_at']
    list_filter = ['category', 'course__category', 'created_at', 'updated_at']
    search_fields = ['title', 'content', 'teacher__email', 'teacher__first_name', 'teacher__last_name', 'course__title', 'lesson__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Note Information', {
            'fields': ('title', 'content', 'category')
        }),
        ('Associations', {
            'fields': ('course', 'teacher', 'lesson'),
            'description': 'Course is required. Lesson is optional for lesson-specific notes.'
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('teacher', 'course', 'lesson')
    
    def save_model(self, request, obj, form, change):
        """Automatically set teacher to current user if not set"""
        if not obj.teacher_id:
            obj.teacher = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['categorize_as_general', 'categorize_as_lesson', 'categorize_as_idea', 'categorize_as_reminder', 'categorize_as_issue']
    
    def categorize_as_general(self, request, queryset):
        """Categorize selected notes as general"""
        updated = queryset.update(category='general')
        self.message_user(request, f'{updated} note(s) categorized as general.')
    categorize_as_general.short_description = "Categorize as General"
    
    def categorize_as_lesson(self, request, queryset):
        """Categorize selected notes as lesson-specific"""
        updated = queryset.update(category='lesson')
        self.message_user(request, f'{updated} note(s) categorized as lesson-specific.')
    categorize_as_lesson.short_description = "Categorize as Lesson"
    
    def categorize_as_idea(self, request, queryset):
        """Categorize selected notes as ideas"""
        updated = queryset.update(category='idea')
        self.message_user(request, f'{updated} note(s) categorized as ideas.')
    categorize_as_idea.short_description = "Categorize as Ideas"
    
    def categorize_as_reminder(self, request, queryset):
        """Categorize selected notes as reminders"""
        updated = queryset.update(category='reminder')
        self.message_user(request, f'{updated} note(s) categorized as reminders.')
    categorize_as_reminder.short_description = "Categorize as Reminders"
    
    def categorize_as_issue(self, request, queryset):
        """Categorize selected notes as issues"""
        updated = queryset.update(category='issue')
        self.message_user(request, f'{updated} note(s) categorized as issues.')
    categorize_as_issue.short_description = "Categorize as Issues"


@admin.register(BookPage)
class BookPageAdmin(admin.ModelAdmin):
    list_display = ['get_book_title', 'page_number', 'title', 'is_required', 'created_at']
    list_filter = ['is_required', 'created_at', 'book_material__material_type']
    search_fields = ['title', 'content', 'book_material__title', 'book_material__lessons__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def get_book_title(self, obj):
        """Display the book title"""
        return obj.book_material.title
    get_book_title.short_description = 'Book'
    get_book_title.admin_order_field = 'book_material__title'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('book_material', 'page_number', 'title', 'content')
        }),
        ('Resources', {
            'fields': ('image_url', 'audio_url')
        }),
        ('Settings', {
            'fields': ('is_required',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('book_material')


@admin.register(DocumentMaterial)
class DocumentMaterialAdmin(admin.ModelAdmin):
    """
    Admin interface for DocumentMaterial
    """
    list_display = ['id', 'original_filename', 'file_extension', 'file_size_mb', 'uploaded_by', 'created_at']
    list_filter = ['file_extension', 'mime_type', 'created_at', 'uploaded_by']
    search_fields = ['original_filename', 'file_name', 'file_url', 'lesson_material__title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'file_size_mb', 'is_pdf']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'lesson_material', 'original_filename', 'file_name')
        }),
        ('File Information', {
            'fields': ('file_url', 'file_size', 'file_size_mb', 'file_extension', 'mime_type', 'is_pdf')
        }),
        ('Upload Information', {
            'fields': ('uploaded_by',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('lesson_material', 'uploaded_by')


@admin.register(VideoMaterial)
class VideoMaterialAdmin(admin.ModelAdmin):
    list_display = ['get_lesson_material_title', 'video_url_short', 'is_youtube', 'has_transcript_display', 'transcript_available_to_students', 'word_count', 'method_used', 'created_at', 'transcribed_at']
    list_filter = ['is_youtube', 'method_used', 'language', 'transcript_available_to_students', 'created_at', 'transcribed_at']
    search_fields = ['video_url', 'video_id', 'lesson_material__title', 'transcript']
    readonly_fields = ['id', 'created_at', 'updated_at', 'transcribed_at', 'transcript_length', 'word_count', 'has_transcript_display']
    date_hierarchy = 'created_at'
    
    def get_lesson_material_title(self, obj):
        """Display the lesson material title if linked"""
        if obj.lesson_material:
            return obj.lesson_material.title
        return "Not linked"
    get_lesson_material_title.short_description = 'Lesson Material'
    get_lesson_material_title.admin_order_field = 'lesson_material__title'
    
    def video_url_short(self, obj):
        """Display shortened video URL"""
        if len(obj.video_url) > 50:
            return obj.video_url[:47] + "..."
        return obj.video_url
    video_url_short.short_description = 'Video URL'
    
    def has_transcript_display(self, obj):
        """Display has_transcript property"""
        return obj.has_transcript
    has_transcript_display.boolean = True
    has_transcript_display.short_description = 'Has Transcript'
    
    fieldsets = (
        ('Video Information', {
            'fields': ('lesson_material', 'video_url', 'video_id', 'is_youtube')
        }),
        ('Transcript Information', {
            'fields': ('has_transcript_display', 'transcript', 'transcript_available_to_students', 'language', 'language_name', 'method_used', 'transcript_length', 'word_count', 'transcribed_at'),
            'description': 'Transcript settings. Check "Available to students" to make transcript visible to students.'
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lesson_material')


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ['room_code', 'class_instance', 'is_active', 'chat_enabled', 'board_enabled', 'video_enabled', 'student_count', 'created_at']
    list_filter = ['is_active', 'chat_enabled', 'board_enabled', 'video_enabled', 'created_at']
    search_fields = ['room_code', 'class_instance__name', 'class_instance__course__title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'student_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('class_instance', 'room_code')
        }),
        ('Features', {
            'fields': ('is_active', 'chat_enabled', 'board_enabled', 'video_enabled')
        }),
        ('Metadata', {
            'fields': ('id', 'student_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('class_instance', 'class_instance__course')


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ['title', 'classroom', 'allow_student_edit', 'allow_student_create_pages', 'view_only_mode', 'current_page_id', 'created_by', 'created_at']
    list_filter = ['allow_student_edit', 'allow_student_create_pages', 'view_only_mode', 'created_at']
    search_fields = ['title', 'description', 'classroom__room_code', 'classroom__class_instance__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('classroom', 'title', 'description')
        }),
        ('Permissions & Settings', {
            'fields': ('allow_student_edit', 'allow_student_create_pages', 'view_only_mode', 'current_page_id')
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('classroom', 'classroom__class_instance', 'created_by')


@admin.register(BoardPage)
class BoardPageAdmin(admin.ModelAdmin):
    list_display = ['page_name', 'board', 'page_order', 'version', 'last_updated_by', 'created_at', 'updated_at']
    list_filter = ['board', 'created_at', 'updated_at']
    search_fields = ['page_name', 'board__title', 'board__classroom__room_code']
    readonly_fields = ['id', 'version', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Page Information', {
            'fields': ('board', 'page_name', 'page_order')
        }),
        ('Page State', {
            'fields': ('state', 'version'),
            'description': 'State contains the tldraw document snapshot (JSON)'
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'last_updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('board', 'board__classroom', 'created_by', 'last_updated_by')


@admin.register(CourseAssessment)
class CourseAssessmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'assessment_type', 'time_limit_minutes', 'passing_score', 'max_attempts', 'question_count', 'total_points', 'created_by', 'created_at']
    list_filter = ['assessment_type', 'passing_score', 'max_attempts', 'created_at', 'course__category']
    search_fields = ['title', 'description', 'instructions', 'course__title', 'created_by__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'question_count', 'total_points']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('course', 'assessment_type', 'title', 'description', 'instructions')
        }),
        ('Assessment Configuration', {
            'fields': ('time_limit_minutes', 'passing_score', 'max_attempts', 'order')
        }),
        ('Statistics', {
            'fields': ('question_count', 'total_points'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('course', 'created_by').prefetch_related('questions')


@admin.register(CourseAssessmentQuestion)
class CourseAssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text_short', 'assessment', 'type', 'points', 'order', 'created_at']
    list_filter = ['type', 'points', 'assessment__assessment_type', 'created_at']
    search_fields = ['question_text', 'assessment__title', 'assessment__course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Question Information', {
            'fields': ('assessment', 'question_text', 'type', 'content', 'points', 'order', 'explanation')
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
        return super().get_queryset(request).select_related('assessment', 'assessment__course')


@admin.register(CourseAssessmentSubmission)
class CourseAssessmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'assessment_title', 'attempt_number', 'status', 'points_earned', 'points_possible', 'percentage', 'passed', 'is_graded', 'submitted_at', 'graded_at']
    list_filter = ['status', 'is_graded', 'passed', 'attempt_number', 'assessment__assessment_type', 'submitted_at', 'graded_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'assessment__title', 'assessment__course__title']
    readonly_fields = ['id', 'started_at', 'submitted_at', 'graded_at', 'percentage', 'passed']
    date_hierarchy = 'submitted_at'
    actions = ['mark_as_submitted', 'mark_as_graded', 'reset_to_in_progress']
    
    fieldsets = (
        ('Submission Information', {
            'fields': ('student', 'assessment', 'enrollment', 'attempt_number', 'status', 'started_at', 'submitted_at')
        }),
        ('Timer Information', {
            'fields': ('time_limit_minutes', 'time_remaining_seconds'),
            'classes': ('collapse',)
        }),
        ('Student Answers', {
            'fields': ('answers',),
            'classes': ('collapse',)
        }),
        ('Grading', {
            'fields': ('is_graded', 'is_teacher_draft', 'points_earned', 'points_possible', 'percentage', 'passed', 'graded_by', 'graded_at', 'graded_questions')
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
    
    def assessment_title(self, obj):
        return obj.assessment.title
    assessment_title.short_description = 'Assessment'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'student', 'assessment', 'assessment__course', 'graded_by', 'enrollment'
        )
    
    def mark_as_submitted(self, request, queryset):
        """Action to mark submissions as submitted"""
        from django.utils import timezone
        updated = queryset.filter(status='in_progress').update(
            status='submitted',
            submitted_at=timezone.now()
        )
        self.message_user(request, f'{updated} submissions were marked as submitted.')
    mark_as_submitted.short_description = "Mark selected submissions as submitted"
    
    def mark_as_graded(self, request, queryset):
        """Action to mark submissions as graded"""
        from django.utils import timezone
        updated = queryset.filter(status__in=['submitted', 'auto_submitted']).update(
            status='graded',
            is_graded=True,
            graded_at=timezone.now(),
            graded_by=request.user
        )
        self.message_user(request, f'{updated} submissions were marked as graded.')
    mark_as_graded.short_description = "Mark selected submissions as graded"
    
    def reset_to_in_progress(self, request, queryset):
        """Action to reset submissions to in_progress status"""
        updated = queryset.update(
            status='in_progress',
            submitted_at=None,
            is_graded=False,
            is_teacher_draft=False,
            graded_at=None,
            graded_by=None
        )
        self.message_user(request, f'{updated} submissions were reset to in_progress status.')
    reset_to_in_progress.short_description = "Reset selected submissions to in_progress"
