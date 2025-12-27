from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Course, Lesson, LessonMaterial, Quiz, Question, QuizAttempt, Note, CourseReview, Class, ClassSession, ClassEvent, Project, ProjectPlatform, ProjectSubmission, SubmissionType, BookPage, VideoMaterial, DocumentMaterial, AudioVideoMaterial, Classroom, Board, BoardPage, CourseAssessment, CourseAssessmentQuestion, CourseAssessmentSubmission

User = get_user_model()


# ===== COURSE REVIEW SERIALIZER =====

class CourseReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for course reviews
    """
    display_name = serializers.ReadOnlyField()
    star_rating = serializers.ReadOnlyField()
    
    class Meta:
        model = CourseReview
        fields = [
            'id', 'student_name', 'student_age', 'display_name', 
            'rating', 'star_rating', 'review_text', 'is_verified', 
            'is_featured', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ===== LESSON MATERIAL SERIALIZER =====

class LessonMaterialSerializer(serializers.ModelSerializer):
    """
    Serializer for lesson materials
    Supports audio_video_material_id for linking AudioVideoMaterial
    """
    file_size_mb = serializers.ReadOnlyField()
    audio_video_material_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    audio_video_data = serializers.SerializerMethodField()
    
    class Meta:
        model = LessonMaterial
        fields = [
            'id', 'title', 'description', 'material_type', 'file_url', 
            'file_size', 'file_size_mb', 'file_extension', 'order', 'created_at',
            'audio_video_material_id', 'audio_video_data'
        ]
        read_only_fields = ['id', 'created_at', 'audio_video_data']
    
    def get_audio_video_data(self, obj):
        """Get AudioVideoMaterial data if exists"""
        try:
            if hasattr(obj, 'audio_video_data') and obj.audio_video_data:
                av_data = obj.audio_video_data
                return {
                    'id': str(av_data.id),
                    'file_name': av_data.file_name,
                    'original_filename': av_data.original_filename,
                    'file_url': av_data.file_url,
                    'file_size': av_data.file_size,
                    'file_size_mb': av_data.file_size_mb,
                    'file_extension': av_data.file_extension,
                    'mime_type': av_data.mime_type,
                    'is_audio': av_data.is_audio,
                    'is_video': av_data.is_video,
                    'uploaded_by_email': av_data.uploaded_by.email if av_data.uploaded_by else None,
                }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting audio_video_data: {e}")
        return None
    
    def create(self, validated_data):
        """Create LessonMaterial and link AudioVideoMaterial if provided"""
        audio_video_material_id = validated_data.pop('audio_video_material_id', None)
        
        # Create the material
        material = super().create(validated_data)
        
        # Link AudioVideoMaterial if provided
        if audio_video_material_id:
            try:
                audio_video_material = AudioVideoMaterial.objects.get(id=audio_video_material_id)
                audio_video_material.lesson_material = material
                audio_video_material.save()
                # Update material file fields from AudioVideoMaterial
                material.file_url = audio_video_material.file_url
                material.file_size = audio_video_material.file_size
                material.file_extension = audio_video_material.file_extension
                material.save()
            except AudioVideoMaterial.DoesNotExist:
                pass
        
        return material
    
    def update(self, instance, validated_data):
        """Update LessonMaterial and handle file replacement"""
        audio_video_material_id = validated_data.pop('audio_video_material_id', None)
        
        # If a new audio_video_material_id is provided, delete the old one first
        # This handles file replacement when updating audio/video materials
        if audio_video_material_id and instance.material_type == 'audio':
            try:
                # Find and delete old AudioVideoMaterial (this will delete file from GCS via delete() method)
                old_audio_video = AudioVideoMaterial.objects.filter(lesson_material=instance).first()
                if old_audio_video:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Deleting old AudioVideoMaterial {old_audio_video.id} for LessonMaterial {instance.id}")
                    # Delete old AudioVideoMaterial - this triggers delete() which removes file from GCS
                    old_audio_video.delete()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error deleting old AudioVideoMaterial: {e}")
        
        # Handle file replacement - delete old file from GCS (fallback check)
        old_file_url = instance.file_url
        new_file_url = validated_data.get('file_url')
        
        # If file_url is being updated but audio_video_material_id wasn't provided, delete old AudioVideoMaterial
        if new_file_url and old_file_url and new_file_url != old_file_url and instance.material_type == 'audio' and not audio_video_material_id:
            try:
                old_audio_video = AudioVideoMaterial.objects.get(lesson_material=instance)
                # Delete file from GCS
                from django.core.files.storage import default_storage
                if old_audio_video.file_name and default_storage.exists(old_audio_video.file_name):
                    try:
                        default_storage.delete(old_audio_video.file_name)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error deleting old audio/video file from GCS: {e}")
                # Delete AudioVideoMaterial record
                old_audio_video.delete()
            except AudioVideoMaterial.DoesNotExist:
                pass
        
        # Link new AudioVideoMaterial if provided
        if audio_video_material_id:
            try:
                audio_video_material = AudioVideoMaterial.objects.get(id=audio_video_material_id)
                # If there's an existing AudioVideoMaterial, delete its file first
                if audio_video_material.lesson_material and audio_video_material.lesson_material != instance:
                    # This material was linked to another lesson, unlink it
                    old_lesson = audio_video_material.lesson_material
                    audio_video_material.lesson_material = None
                    audio_video_material.save()
                    
                    # Update the old lesson's file_url if needed
                    if old_lesson.file_url == audio_video_material.file_url:
                        old_lesson.file_url = None
                        old_lesson.file_size = None
                        old_lesson.file_extension = None
                        old_lesson.save()
                
                # Link to new lesson material
                audio_video_material.lesson_material = instance
                audio_video_material.save()
                
                # Update instance file fields from AudioVideoMaterial
                instance.file_url = audio_video_material.file_url
                instance.file_size = audio_video_material.file_size
                instance.file_extension = audio_video_material.file_extension
            except AudioVideoMaterial.DoesNotExist:
                pass
        
        return super().update(instance, validated_data)


# ===== OPTIMIZED LESSON SERIALIZERS FOR 2-CALL STRATEGY =====

class LessonListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for lesson list (first API call)
    Returns minimal lesson data for the course page
    
    Status is determined directly from StudentLessonProgress records,
    not from enrollment metadata. This makes it robust against lesson reordering
    and new lesson additions.
    """
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'type', 'duration', 'order', 
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_status(self, obj):
        """
        Get lesson status directly from StudentLessonProgress records.
        This is the single source of truth - no inference from metadata.
        """
        lesson_status_map = self.context.get('lesson_status_map', {})
        current_lesson_id = self.context.get('current_lesson_id')
        lesson_id = str(obj.id)
        
        # Check actual progress record
        progress_status = lesson_status_map.get(lesson_id)
        
        if progress_status == 'completed':
            return 'completed'
        elif progress_status == 'in_progress':
            # If it's the current lesson, mark as current, otherwise in_progress
            return 'current' if lesson_id == current_lesson_id else 'in_progress'
        elif progress_status == 'not_started':
            # Check if this is the current lesson or first lesson
            if lesson_id == current_lesson_id:
                return 'current'
            elif obj.order == 1:
                # First lesson is always available if no progress record exists
                return 'current'
            else:
                return 'locked'
        else:
            # No progress record exists - determine from order and prerequisites
            if lesson_id == current_lesson_id:
                return 'current'
            elif obj.order == 1:
                # First lesson is always available
                return 'current'
            else:
                # Check if previous lessons are completed to determine if unlocked
                # For now, default to locked (can be enhanced with prerequisite checking)
                return 'locked'


class LessonDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for individual lesson details (second API call)
    Returns full lesson data including materials, quiz, assignments, and class events
    """
    materials = serializers.SerializerMethodField()
    quiz = serializers.SerializerMethodField()
    assignment = serializers.SerializerMethodField()
    has_assignment = serializers.SerializerMethodField()
    class_event = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    prerequisites = serializers.SerializerMethodField()
    is_material_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'type', 'duration', 'order',
            'text_content', 'video_url', 'audio_url', 'live_class_date', 
            'live_class_status', 'content', 'materials', 'prerequisites',
            'quiz', 'assignment', 'has_assignment', 'class_event', 'teacher_name', 'course_title',
            'is_material_available', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_quiz(self, obj):
        """Get pre-computed quiz data from context"""
        return self.context.get('quiz_data')
    
    def get_assignment(self, obj):
        """Get pre-computed assignment data from context"""
        return self.context.get('assignment_data')
    
    def get_has_assignment(self, obj):
        """Check if lesson has an assignment"""
        assignment_data = self.context.get('assignment_data')
        return assignment_data is not None
    
    def get_class_event(self, obj):
        """Get pre-computed class event data from context"""
        return self.context.get('class_event_data')
    
    def get_materials(self, obj):
        """Get pre-computed materials data from context"""
        return self.context.get('materials_data', [])
    
    def get_teacher_name(self, obj):
        """Get pre-computed teacher name from context"""
        return self.context.get('teacher_name')
    
    def get_prerequisites(self, obj):
        """Get pre-computed prerequisites data from context"""
        return self.context.get('prerequisites_data', [])
    
    def get_is_material_available(self, obj):
        """Get material availability flag from context"""
        return self.context.get('is_material_available', False)


# ===== COURSE WITH LESSONS SERIALIZER (FIRST API CALL) =====

class CourseWithLessonsSerializer(serializers.ModelSerializer):
    """
    Comprehensive course serializer that includes lesson list and current lesson details
    This is the first API call that returns everything needed for the course page
    """
    lessons = LessonListSerializer(many=True, read_only=True)
    current_lesson = serializers.SerializerMethodField()
    enrollment_info = serializers.SerializerMethodField()
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    enrolled_students_count = serializers.ReadOnlyField()
    total_lessons = serializers.ReadOnlyField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'long_description', 'category', 'level',
            'age_range', 'price', 'features', 'overview', 'learning_objectives',
            'prerequisites_text', 'duration_weeks', 'sessions_per_week', 
            'total_projects', 'value_propositions', 'featured', 'popular',
            'color', 'icon', 'image', 'max_students', 'schedule', 'certificate',
            'status', 'teacher_name', 'enrolled_students_count', 'total_lessons',
            'lessons', 'current_lesson', 'enrollment_info', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'enrolled_students_count', 'total_lessons']
    
    def get_current_lesson(self, obj):
        """
        Get detailed information for the current lesson.
        Current lesson is determined from StudentLessonProgress records,
        not from enrollment.current_lesson metadata.
        """
        try:
            current_lesson_id = self.context.get('current_lesson_id')
            
            if current_lesson_id:
                # Get current lesson from context (determined from progress records)
                try:
                    current_lesson = obj.lessons.get(id=current_lesson_id)
                except Lesson.DoesNotExist:
                    # Fallback to first lesson if current_lesson_id doesn't exist
                    current_lesson = obj.lessons.order_by('order').first()
            else:
                # No current lesson determined, fallback to first lesson
                current_lesson = obj.lessons.order_by('order').first()
            
            if current_lesson:
                # Use the detailed serializer for current lesson
                detail_serializer = LessonDetailSerializer(
                    current_lesson, 
                    context=self.context
                )
                return detail_serializer.data
            
            return None
            
        except Exception as e:
            print(f"Error getting current lesson: {str(e)}")
            return None
    
    def get_enrollment_info(self, obj):
        """
        Get enrollment information for the student.
        Uses actual progress records to calculate metrics, not enrollment metadata.
        """
        try:
            student_profile = self.context.get('student_profile')
            if not student_profile:
                return None
                
            from student.models import EnrolledCourse
            enrollment = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                course=obj,
                status__in=['active', 'completed']
            ).first()
            
            if not enrollment:
                return None
            
            # Get actual completed count from context (calculated from progress records)
            actual_completed_count = self.context.get('actual_completed_count', 0)
            current_lesson_id = self.context.get('current_lesson_id')
            
            # Calculate progress percentage from actual records
            total_lessons = enrollment.total_lessons_count or obj.lessons.count()
            if total_lessons > 0:
                calculated_percentage = (actual_completed_count / total_lessons) * 100
                # Cap at 100.0 to prevent DecimalField overflow and because progress can't exceed 100%
                actual_progress_percentage = min(calculated_percentage, 100.0)
                
                # Debug logging for overflow detection
                if calculated_percentage > 100.0:
                    print(f"⚠️ WARNING: Progress percentage calculated as {calculated_percentage}% (capped at 100.0%)")
                    print(f"   - actual_completed_count: {actual_completed_count}")
                    print(f"   - total_lessons: {total_lessons}")
                    print(f"   - Course: {obj.title}")
            else:
                actual_progress_percentage = 0.0
            
            # Determine if course is completed from actual progress
            course_completed = actual_completed_count >= total_lessons if total_lessons > 0 else False
            
            return {
                'current_lesson_id': current_lesson_id,  # From progress records, not enrollment.current_lesson
                'completed_lessons_count': actual_completed_count,  # From progress records
                'progress_percentage': float(actual_progress_percentage),  # Calculated from actual records
                'course_completed': course_completed  # Determined from actual progress
            }
            
        except Exception as e:
            print(f"Error getting enrollment info: {str(e)}")
            return None


# ===== ENROLLED STUDENT SERIALIZERS =====

class TeacherStudentDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for teacher's student management view
    Includes all relevant student data across courses
    """
    # Student basic info
    id = serializers.CharField(source='student_profile.user.id', read_only=True)
    name = serializers.CharField(source='student_profile.user.get_full_name', read_only=True)
    email = serializers.CharField(source='student_profile.user.email', read_only=True)
    
    # Child/Student specific info
    child_name = serializers.SerializerMethodField()
    child_email = serializers.CharField(source='student_profile.child_email', read_only=True)
    child_phone = serializers.CharField(source='student_profile.child_phone', read_only=True)
    grade_level = serializers.CharField(source='student_profile.grade_level', read_only=True)
    age = serializers.ReadOnlyField(source='student_profile.age')
    profile_image = serializers.CharField(source='student_profile.profile_image', read_only=True)
    
    # Parent/Guardian info
    parent_name = serializers.CharField(source='student_profile.parent_name', read_only=True)
    parent_email = serializers.CharField(source='student_profile.parent_email', read_only=True)
    parent_phone = serializers.CharField(source='student_profile.parent_phone', read_only=True)
    emergency_contact = serializers.CharField(source='student_profile.emergency_contact', read_only=True)
    
    # Course enrollment info
    course_id = serializers.CharField(source='course.id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_category = serializers.CharField(source='course.category', read_only=True)
    
    # Academic progress
    enrollment_date = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    completed_lessons_count = serializers.IntegerField(read_only=True)
    total_lessons_count = serializers.IntegerField(read_only=True)
    current_lesson_title = serializers.CharField(source='current_lesson.title', read_only=True)
    
    # Performance metrics
    overall_grade = serializers.CharField(read_only=True)
    gpa_points = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)
    average_quiz_score = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    assignment_completion_rate = serializers.ReadOnlyField()
    
    # Engagement metrics
    last_accessed = serializers.DateTimeField(read_only=True)
    days_since_last_access = serializers.ReadOnlyField()
    total_study_time = serializers.DurationField(read_only=True)
    login_count = serializers.IntegerField(read_only=True)
    is_at_risk = serializers.ReadOnlyField()
    
    # Financial info
    payment_status = serializers.CharField(read_only=True)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payment_due_date = serializers.DateField(read_only=True)
    
    # Completion & certification
    completion_date = serializers.DateField(read_only=True)
    certificate_issued = serializers.BooleanField(read_only=True)
    certificate_url = serializers.URLField(read_only=True)
    
    # Communication preferences
    parent_notifications_enabled = serializers.BooleanField(read_only=True)
    reminder_emails_enabled = serializers.BooleanField(read_only=True)
    special_accommodations = serializers.CharField(read_only=True)
    
    class Meta:
        fields = [
            # Student basic info
            'id', 'name', 'email', 'child_name', 'child_email', 'child_phone', 
            'grade_level', 'age', 'profile_image',
            
            # Parent info
            'parent_name', 'parent_email', 'parent_phone', 'emergency_contact',
            
            # Course info
            'course_id', 'course_title', 'course_category',
            
            # Academic progress
            'enrollment_date', 'status', 'progress_percentage', 'completed_lessons_count',
            'total_lessons_count', 'current_lesson_title',
            
            # Performance
            'overall_grade', 'gpa_points', 'average_quiz_score', 'assignment_completion_rate',
            
            # Engagement
            'last_accessed', 'days_since_last_access', 'total_study_time', 'login_count', 'is_at_risk',
            
            # Financial
            'payment_status', 'amount_paid', 'payment_due_date',
            
            # Completion
            'completion_date', 'certificate_issued', 'certificate_url',
            
            # Communication
            'parent_notifications_enabled', 'reminder_emails_enabled', 'special_accommodations'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from student.models import EnrolledCourse
        self.Meta.model = EnrolledCourse
    
    def get_child_name(self, obj):
        """Get the child's name from student profile"""
        profile = obj.student_profile
        child_name = f"{profile.child_first_name} {profile.child_last_name}".strip()
        return child_name or profile.user.get_full_name()


class TeacherStudentSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for teacher's student list view
    """
    # Student basic info
    id = serializers.CharField(source='student_profile.user.id', read_only=True)
    name = serializers.CharField(source='student_profile.user.get_full_name', read_only=True)
    email = serializers.CharField(source='student_profile.user.email', read_only=True)
    child_name = serializers.SerializerMethodField()
    profile_image = serializers.CharField(source='student_profile.profile_image', read_only=True)
    
    # Course info
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_category = serializers.CharField(source='course.category', read_only=True)
    
    # Key metrics
    enrollment_date = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    overall_grade = serializers.CharField(read_only=True)
    average_quiz_score = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    last_accessed = serializers.DateTimeField(read_only=True)
    is_at_risk = serializers.ReadOnlyField()
    payment_status = serializers.CharField(read_only=True)
    
    class Meta:
        fields = [
            'id', 'name', 'email', 'child_name', 'profile_image',
            'course_title', 'course_category', 'enrollment_date', 'status',
            'progress_percentage', 'overall_grade', 'average_quiz_score',
            'last_accessed', 'is_at_risk', 'payment_status'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from student.models import EnrolledCourse
        self.Meta.model = EnrolledCourse
    
    def get_child_name(self, obj):
        """Get the child's name from student profile"""
        profile = obj.student_profile
        child_name = f"{profile.child_first_name} {profile.child_last_name}".strip()
        return child_name or profile.user.get_full_name()


class EnrolledStudentSerializer(serializers.ModelSerializer):
    """Serializer for enrolled students in a course"""
    name = serializers.CharField(source='student_profile.user.get_full_name', read_only=True)
    email = serializers.CharField(source='student_profile.user.email', read_only=True)
    child_name = serializers.SerializerMethodField()
    enrollment_date = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)
    
    class Meta:
        fields = [
            'id', 'name', 'email', 'child_name', 
            'enrollment_date', 'status', 'progress_percentage', 'payment_status'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from student.models import EnrolledCourse
        self.Meta.model = EnrolledCourse
    
    def get_child_name(self, obj):
        """Get the child's name from student profile"""
        profile = obj.student_profile
        return f"{profile.child_first_name} {profile.child_last_name}".strip() or obj.student_profile.user.get_full_name()




class CourseListSerializer(serializers.ModelSerializer):
    """
    Serializer for course list view (minimal data for performance)
    """
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    total_lessons = serializers.ReadOnlyField()
    enrolled_students_count = serializers.SerializerMethodField()
    active_students_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'category', 'age_range', 'duration_weeks', 'duration', 
            'level', 'required_computer_skills_level', 'price', 'featured', 'popular', 'color', 'icon',
            'max_students', 'schedule', 'certificate', 'status',
            'teacher_name', 'total_lessons', 'enrolled_students_count', 'active_students_count',
            'created_at', 'updated_at'
        ]
    
    def get_enrolled_students_count(self, obj):
        """Get total enrolled students count from EnrolledCourse model"""
        return getattr(obj, 'enrolled_count', 0)
    
    def get_active_students_count(self, obj):
        """Get active enrolled students count"""
        return getattr(obj, 'active_count', 0)


class CourseDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed course view with all related data
    """
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    teacher_id = serializers.UUIDField(source='teacher.id', read_only=True)
    total_lessons = serializers.ReadOnlyField()
    total_duration_minutes = serializers.ReadOnlyField()
    enrolled_students_count = serializers.SerializerMethodField()
    active_students_count = serializers.SerializerMethodField()
    is_featured_eligible = serializers.ReadOnlyField()
    
    # Reviews and ratings
    reviews = CourseReviewSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    # Optional fields based on query parameters
    enrolled_students = serializers.SerializerMethodField()
    enrollment_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            # Basic course info
            'id', 'title', 'description', 'long_description', 'category',
            'age_range', 'level', 'required_computer_skills_level', 'price', 'features',
            'featured', 'popular', 'color', 'icon', 'image', 'max_students',
            'schedule', 'certificate', 'status', 'teacher_name', 'teacher_id',
            
            # Introduction/detailed info (now part of Course model)
            'overview', 'learning_objectives', 'prerequisites_text',
            'duration_weeks', 'duration', 'sessions_per_week', 'total_projects',
            'value_propositions',
            
            # Reviews and ratings
            'reviews', 'average_rating', 'review_count',
            
            # Computed fields
            'total_lessons', 'total_duration_minutes', 'enrolled_students_count',
            'active_students_count', 'is_featured_eligible', 'enrolled_students', 
            'enrollment_stats', 'created_at', 'updated_at'
        ]
    
    def get_enrolled_students_count(self, obj):
        """Get total enrolled students count"""
        return getattr(obj, 'enrolled_count', 0)
    
    def get_active_students_count(self, obj):
        """Get active enrolled students count"""
        return getattr(obj, 'active_count', 0)
    
    def get_average_rating(self, obj):
        """Calculate average rating from reviews"""
        reviews = obj.reviews.all()
        if not reviews:
            return 0
        total_rating = sum(review.rating for review in reviews)
        return round(total_rating / len(reviews), 1)
    
    def get_review_count(self, obj):
        """Get total number of reviews"""
        return obj.reviews.count()
    
    def get_enrolled_students(self, obj):
        """Get enrolled students list if requested"""
        request = self.context.get('request')
        if request and 'students' in request.query_params.get('include', ''):
            enrollments = getattr(obj, 'prefetched_enrollments', [])
            return EnrolledStudentSerializer(enrollments, many=True).data
        return None
    
    def get_enrollment_stats(self, obj):
        """Get enrollment statistics if requested"""
        request = self.context.get('request')
        if request and 'stats' in request.query_params.get('include', ''):
            stats = getattr(obj, 'enrollment_stats', {})
            return stats if stats else None
        return None


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating courses
    """
    class Meta:
        model = Course
        fields = [
            # Basic course info
            'title', 'description', 'long_description', 'category',
            'age_range', 'level', 'required_computer_skills_level', 'price', 'is_free', 'features',
            'featured', 'popular', 'color', 'icon', 'image', 'thumbnail', 'max_students',
            'schedule', 'certificate', 'status',
            
            # Introduction/detailed info
            'overview', 'learning_objectives', 'prerequisites_text',
            'duration_weeks', 'sessions_per_week', 'total_projects',
            'value_propositions'
        ]
    
    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
    
    def validate_max_students(self, value):
        if value < 1 or value > 50:
            raise serializers.ValidationError("Max students must be between 1 and 50")
        return value
    
    def validate(self, data):
        return data
    
    def update(self, instance, validated_data):
        """
        Update course and handle image deletion from GCS when image is replaced or removed.
        """
        from django.core.files.storage import default_storage
        from django.conf import settings
        from urllib.parse import urlparse
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get old image URLs from database BEFORE update
        # This is critical - we need the original values from the database
        old_image_url = instance.image
        old_thumbnail_url = instance.thumbnail
        
        # IMPORTANT: With partial=True, when image is set to None/null, 
        # DRF might not include it in validated_data or might convert it to empty string
        # We need to check the original request data to see if image was explicitly set to None
        # Access the request from the context if available
        request = self.context.get('request') if hasattr(self, 'context') else None
        request_data = request.data if request else {}
        
        # Get new image URLs from validated data
        new_image_url = validated_data.get('image')
        new_thumbnail_url = validated_data.get('thumbnail')
        
        # Check if image field is in request data (even if None/empty)
        # This tells us if the user explicitly set the image field
        image_key_in_request = 'image' in request_data
        thumbnail_key_in_request = 'thumbnail' in request_data
        
        # Also check validated_data (might be there if not None)
        image_key_in_validated = 'image' in validated_data
        thumbnail_key_in_validated = 'thumbnail' in validated_data
        
        # Image is being updated if it's in request data OR validated data
        image_is_being_updated = image_key_in_request or image_key_in_validated
        thumbnail_is_being_updated = thumbnail_key_in_request or thumbnail_key_in_validated
        
        # If image is in request but not in validated_data, it might be None/empty
        # In that case, check request_data directly
        if image_key_in_request and not image_key_in_validated:
            # Field was in request but not in validated_data - likely None or empty string
            request_image_value = request_data.get('image')
            if request_image_value is None or request_image_value == '':
                new_image_url = None
        
        if thumbnail_key_in_request and not thumbnail_key_in_validated:
            request_thumbnail_value = request_data.get('thumbnail')
            if request_thumbnail_value is None or request_thumbnail_value == '':
                new_thumbnail_url = None
        
        # Log for debugging
        logger.info(f"Image update check - Old: {old_image_url}, New: {new_image_url}, In request: {image_key_in_request}, In validated: {image_key_in_validated}")
        
        # Determine if we need to delete old images:
        # Case 1: Image is being replaced (new URL is different from old)
        # Case 2: Image is being removed (new URL is None/empty but old exists)
        should_delete_old_image = (
            old_image_url is not None and  # Old image exists in database
            image_is_being_updated and  # Image field is being updated
            (
                new_image_url != old_image_url  # Being replaced with different URL OR removed (None/empty)
            )
        )
        
        should_delete_old_thumbnail = (
            old_thumbnail_url is not None and  # Old thumbnail exists in database
            thumbnail_is_being_updated and  # Thumbnail field is being updated
            (
                new_thumbnail_url != old_thumbnail_url  # Being replaced with different URL OR removed (None/empty)
            )
        )
        
        logger.info(f"Should delete old image: {should_delete_old_image}, Should delete old thumbnail: {should_delete_old_thumbnail}")
        
        def extract_file_path_from_url(url):
            """
            Extract file path from GCS URL.
            URL format: https://storage.googleapis.com/BUCKET_NAME/path/to/file
            Returns: path/to/file (relative to bucket root, URL-decoded)
            """
            if not url:
                return None
            
            try:
                from urllib.parse import unquote
                
                if 'storage.googleapis.com' in url:
                    # Parse URL: https://storage.googleapis.com/bucket-name/path/to/file
                    parsed_url = urlparse(url)
                    path_parts = parsed_url.path.split('/', 2)
                    if len(path_parts) >= 3:
                        # Get everything after /bucket-name/ and URL-decode it
                        # GCS URLs are URL-encoded, but storage paths are not
                        encoded_path = path_parts[2]
                        decoded_path = unquote(encoded_path)
                        return decoded_path
                    else:
                        # Fallback: try to extract from full path
                        if 'course_images/' in url:
                            encoded_path = url.split('course_images/', 1)[1]
                            # Remove query parameters if any
                            if '?' in encoded_path:
                                encoded_path = encoded_path.split('?')[0]
                            decoded_path = unquote(encoded_path)
                            return f'course_images/{decoded_path}'
                        return None
                else:
                    # If not a full URL, assume it's already a path (might still be encoded)
                    # Try to decode it
                    try:
                        return unquote(url)
                    except:
                        return url
            except Exception as e:
                logger.warning(f"Error extracting file path from URL {url}: {e}")
                return None
        
        # Delete old image if it exists and is being replaced/removed
        if should_delete_old_image:
            try:
                file_path = extract_file_path_from_url(old_image_url)
                logger.info(f"Deleting old course image from GCS: {file_path} (old URL: {old_image_url}, new URL: {new_image_url})")
                if file_path:
                    if default_storage.exists(file_path):
                        default_storage.delete(file_path)
                        logger.info(f"✅ Successfully deleted old course image from GCS: {file_path}")
                    else:
                        logger.warning(f"⚠️ Course image file not found in GCS: {file_path}")
                else:
                    logger.warning(f"⚠️ Could not extract file path from URL: {old_image_url}")
            except Exception as e:
                logger.error(f"❌ Error deleting old course image from GCS: {e}", exc_info=True)
        
        # Delete old thumbnail if it exists and is being replaced/removed
        if should_delete_old_thumbnail:
            try:
                thumb_path = extract_file_path_from_url(old_thumbnail_url)
                logger.info(f"Deleting old course thumbnail from GCS: {thumb_path} (old URL: {old_thumbnail_url}, new URL: {new_thumbnail_url})")
                if thumb_path:
                    if default_storage.exists(thumb_path):
                        default_storage.delete(thumb_path)
                        logger.info(f"✅ Successfully deleted old course thumbnail from GCS: {thumb_path}")
                    else:
                        logger.warning(f"⚠️ Course thumbnail file not found in GCS: {thumb_path}")
                else:
                    logger.warning(f"⚠️ Could not extract file path from URL: {old_thumbnail_url}")
            except Exception as e:
                logger.error(f"❌ Error deleting old course thumbnail from GCS: {e}", exc_info=True)
        
        # Call parent update method
        return super().update(instance, validated_data)


# Frontend-compatible serializers (matching existing data structure)
class FrontendCourseSerializer(serializers.ModelSerializer):
    """
    Serializer that matches the existing frontend CourseData interface
    """
    icon = serializers.CharField()  # Will need to map to Lucide icon names
    projects = serializers.SerializerMethodField()
    classSize = serializers.SerializerMethodField()
    age = serializers.CharField(source='age_range')
    longDescription = serializers.CharField(source='long_description')
    category = serializers.CharField(read_only=False)  # Explicitly include category field
    status = serializers.CharField(read_only=False)  # Explicitly include status field
    age_range = serializers.CharField(read_only=False)  # Explicitly include age_range field
    
    class Meta:
        model = Course
        fields = [
            'id', 'icon', 'title', 'description', 'longDescription',
            'age', 'duration_weeks', 'duration', 'level', 'required_computer_skills_level', 'color', 'projects', 'price',
            'popular', 'featured', 'features', 'schedule', 'classSize', 'certificate', 'status', 'category', 'age_range',
            'image', 'thumbnail'  # Added image and thumbnail fields
        ]
    
    def get_projects(self, obj):
        # Use Course total_projects if available, otherwise fallback to lesson count
        if obj.total_projects and obj.total_projects > 0:
            return f"Build {obj.total_projects} projects"
        elif obj.total_lessons and obj.total_lessons > 0:
            return f"Build {obj.total_lessons} projects"
        return "Multiple projects"
    
    def get_classSize(self, obj):
        # Use Course max_students field directly
        if obj.max_students and obj.max_students > 0:
            return f"Max {obj.max_students} students"
        return "Small class size"


class FeaturedCoursesSerializer(serializers.Serializer):
    """
    Serializer for featured courses endpoint (home page)
    """
    courses = FrontendCourseSerializer(many=True)
    
    def to_representation(self, instance):
        # Filter only published and featured courses
        featured_courses = Course.objects.filter(
            status='published',
            featured=True
        ).select_related('teacher').order_by('-created_at')[:6]  # Limit to 6 featured courses
        
        return {
            'courses': FrontendCourseSerializer(featured_courses, many=True).data
        }


# CourseReviewSerializer moved to top of file


# CourseIntroductionDetailSerializer removed - now using CourseDetailSerializer directly


class LessonListSerializer(serializers.ModelSerializer):
    """
    Serializer for lesson list view (for course management)
    """
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'type', 'duration', 'order',
            'text_content', 'video_url', 'audio_url', 'live_class_date', 
            'live_class_status', 'content',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating lessons
    """
    class Meta:
        model = Lesson
        fields = [
            'title', 'description', 'type', 'duration', 'order', 'content',
            'text_content', 'video_url', 'audio_url', 'live_class_date', 
            'live_class_status'
        ]
    
    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Lesson title cannot be empty")
        return value.strip()
    
    def validate_duration(self, value):
        if value < 1 or value > 300:
            raise serializers.ValidationError("Duration must be between 1 and 300 minutes")
        return value
    
    def validate_order(self, value):
        if value < 1:
            raise serializers.ValidationError("Lesson order must be positive")
        return value


class LessonReorderSerializer(serializers.Serializer):
    """
    Serializer for reordering lessons within a course
    """
    lessons = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        help_text="List of lesson objects with id and order fields"
    )
    
    def validate_lessons(self, value):
        if not value:
            raise serializers.ValidationError("Lessons list cannot be empty")
        
        for lesson_data in value:
            if 'id' not in lesson_data or 'order' not in lesson_data:
                raise serializers.ValidationError("Each lesson must have 'id' and 'order' fields")
            
            try:
                order = int(lesson_data['order'])
                if order < 1:
                    raise serializers.ValidationError("Lesson order must be positive")
            except (ValueError, TypeError):
                raise serializers.ValidationError("Lesson order must be a valid integer")
        
        return value


class ProjectReorderSerializer(serializers.Serializer):
    """
    Serializer for reordering projects within a course
    """
    projects = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        help_text="List of project objects with id and order fields"
    )
    
    def validate_projects(self, value):
        if not value:
            raise serializers.ValidationError("Projects list cannot be empty")
        
        for project_data in value:
            if 'id' not in project_data or 'order' not in project_data:
                raise serializers.ValidationError("Each project must have 'id' and 'order' fields")
            
            try:
                order = int(project_data['order'])
                if order < 0:
                    raise serializers.ValidationError("Project order must be non-negative")
            except (ValueError, TypeError):
                raise serializers.ValidationError("Project order must be a valid integer")
        
        return value


# ===== QUIZ SERIALIZERS =====

class QuizListSerializer(serializers.ModelSerializer):
    """
    Serializer for quiz list view (for lesson management)
    """
    question_count = serializers.IntegerField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'time_limit', 'passing_score',
            'max_attempts', 'show_correct_answers', 'randomize_questions',
            'question_count', 'total_points', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'question_count', 'total_points', 'created_at', 'updated_at']


class QuizDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed quiz view with questions
    """
    lesson_id = serializers.SerializerMethodField()
    lesson_title = serializers.SerializerMethodField()
    question_count = serializers.IntegerField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)
    
    def get_lesson_id(self, obj):
        """Get the first lesson ID (for backward compatibility)"""
        first_lesson = obj.lessons.first()
        return first_lesson.id if first_lesson else None
    
    def get_lesson_title(self, obj):
        """Get the first lesson title (for backward compatibility)"""
        first_lesson = obj.lessons.first()
        return first_lesson.title if first_lesson else None
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'lesson_id', 'lesson_title', 'title', 'description',
            'time_limit', 'passing_score', 'max_attempts', 'show_correct_answers',
            'randomize_questions', 'question_count', 'total_points',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'lesson_id', 'lesson_title', 'question_count', 'total_points', 'created_at', 'updated_at']


class QuizCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating quizzes
    """
    class Meta:
        model = Quiz
        fields = [
            'title', 'description', 'time_limit', 'passing_score',
            'max_attempts', 'show_correct_answers', 'randomize_questions'
        ]
    
    def validate_time_limit(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Time limit must be at least 1 minute")
        return value
    
    def validate_passing_score(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Passing score must be between 0 and 100")
        return value
    
    def validate_max_attempts(self, value):
        if value < 1:
            raise serializers.ValidationError("Max attempts must be at least 1")
        return value


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Serializer for question list view (for quiz management)
    """
    question_type = serializers.CharField(source='type', read_only=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type', 'points', 'order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed question view with all options
    """
    quiz_id = serializers.UUIDField(source='quiz.id', read_only=True)
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    question_type = serializers.CharField(source='type', read_only=True)
    options = serializers.SerializerMethodField()
    correct_answer = serializers.SerializerMethodField()
    full_options = serializers.SerializerMethodField()
    
    class Meta:
        model = Question
        fields = [
            'id', 'quiz_id', 'quiz_title', 'question_text', 'question_type',
            'options', 'correct_answer', 'explanation', 'points', 'order',
            'created_at', 'updated_at', 'full_options'
        ]
        read_only_fields = ['id', 'quiz_id', 'quiz_title', 'created_at', 'updated_at']
    
    def get_options(self, obj):
        return obj.content.get('options', []) if obj.content else []
    
    def get_correct_answer(self, obj):
        return obj.content.get('correct_answer', '') if obj.content else ''
    
    def get_full_options(self, obj):
        return obj.content.get('full_options', None) if obj.content else None


class QuestionCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating questions
    """
    # Virtual fields that will be stored in the content JSONField
    # NOTE: We accept both 'question_type' and 'type' for backward compatibility
    # Frontend components (both teacher and student) may send either field name
    # This prevents breaking changes when shared components are used
    question_type = serializers.CharField(required=False, write_only=True)
    type = serializers.CharField(required=False, write_only=True)
    options = serializers.ListField(required=False, allow_empty=True, allow_null=True)
    correct_answer = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    # New field for rich options with explanations
    full_options = serializers.JSONField(required=False, allow_null=True)
    
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'type', 'options', 'correct_answer',
            'explanation', 'points', 'order', 'full_options'
        ]
        extra_kwargs = {
            'order': {'required': False}
        }
    
    def validate_points(self, value):
        if value < 1:
            raise serializers.ValidationError("Points must be at least 1")
        return value
    
    def validate_order(self, value):
        if value < 1:
            raise serializers.ValidationError("Order must be at least 1")
        return value
    
    def validate(self, data):
        # Handle both 'question_type' and 'type' field names for backward compatibility
        question_type = data.get('question_type') or data.get('type')
        
        # For updates, type field is optional if not being changed
        # For creates, type field is required
        if not question_type and not self.instance:
            raise serializers.ValidationError("Either 'question_type' or 'type' is required")
        
        # If no type provided for update, use existing type
        if not question_type and self.instance:
            question_type = self.instance.type
        
        options = data.get('options')
        correct_answer = data.get('correct_answer')
        
        # Validate options and correct_answer based on question type
        if question_type in ['multiple_choice', 'matching']:
            if not options or not isinstance(options, list) or len(options) < 2:
                raise serializers.ValidationError(
                    f"{question_type.replace('_', ' ').title()} questions must have at least 2 options"
                )
        
        if question_type == 'true_false':
            if not correct_answer or correct_answer.lower() not in ['true', 'false']:
                raise serializers.ValidationError("True/False questions must have 'true' or 'false' as correct answer")
        
        return data
    
    def _trim_full_options_whitespace(self, full_options):
        """
        Trim whitespace from full_options structure
        """
        if not full_options:
            return full_options
        
        # Handle options array (for multiple choice)
        if 'options' in full_options and isinstance(full_options['options'], list):
            for option in full_options['options']:
                if isinstance(option, dict) and 'text' in option:
                    option['text'] = str(option['text']).strip()
        
        # Handle True/False options
        if 'trueOption' in full_options and isinstance(full_options['trueOption'], dict):
            if 'text' in full_options['trueOption']:
                full_options['trueOption']['text'] = str(full_options['trueOption']['text']).strip()
        
        if 'falseOption' in full_options and isinstance(full_options['falseOption'], dict):
            if 'text' in full_options['falseOption']:
                full_options['falseOption']['text'] = str(full_options['falseOption']['text']).strip()
        
        return full_options
    
    def create(self, validated_data):
        # Extract virtual fields
        options = validated_data.pop('options', None)
        correct_answer = validated_data.pop('correct_answer', None)
        full_options = validated_data.pop('full_options', None)
        question_type = validated_data.pop('question_type', None)
        type_field = validated_data.pop('type', None)
        
        # Set the type field (either from question_type or type)
        if question_type:
            validated_data['type'] = question_type
        elif type_field:
            validated_data['type'] = type_field
        # For creates, type is required (validated above)
        
        # 🔧 FIX: Trim whitespace from options and correct_answer before saving
        if options is not None and options != []:
            # Trim whitespace from all options
            options = [str(option).strip() for option in options if option]
        
        if correct_answer is not None and correct_answer != '':
            # Trim whitespace from correct_answer
            correct_answer = str(correct_answer).strip()
        
        if full_options is not None:
            # Trim whitespace from full_options structure
            full_options = self._trim_full_options_whitespace(full_options)
        
        # Create content dict
        content = {}
        if options is not None and options != []:
            content['options'] = options
        if correct_answer is not None and correct_answer != '':
            content['correct_answer'] = correct_answer
        if full_options is not None:
            content['full_options'] = full_options
            
        validated_data['content'] = content
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Extract virtual fields
        options = validated_data.pop('options', None)
        correct_answer = validated_data.pop('correct_answer', None)
        full_options = validated_data.pop('full_options', None)
        question_type = validated_data.pop('question_type', None)
        type_field = validated_data.pop('type', None)
        
        # Set the type field (either from question_type or type)
        if question_type:
            validated_data['type'] = question_type
        elif type_field:
            validated_data['type'] = type_field
        # For updates, if no type provided, keep existing type (don't set validated_data['type'])
        
        # 🔧 FIX: Trim whitespace from options and correct_answer before saving
        if options is not None and options != []:
            # Trim whitespace from all options
            options = [str(option).strip() for option in options if option]
        
        if correct_answer is not None and correct_answer != '':
            # Trim whitespace from correct_answer
            correct_answer = str(correct_answer).strip()
        
        if full_options is not None:
            # Trim whitespace from full_options structure
            full_options = self._trim_full_options_whitespace(full_options)
        
        # Update content dict
        content = instance.content or {}
        if options is not None and options != []:
            content['options'] = options
        if correct_answer is not None and correct_answer != '':
            content['correct_answer'] = correct_answer
        if full_options is not None:
            content['full_options'] = full_options
            
        validated_data['content'] = content
        return super().update(instance, validated_data)


class NoteSerializer(serializers.ModelSerializer):
    """
    Serializer for Note model
    """
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'content', 'category', 
            'lesson_id', 'lesson_title',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'lesson_title']
    
    def validate_lesson_id(self, value):
        """
        Validate that the lesson belongs to the same course
        """
        if value:
            course = self.context.get('course')
            if course and not course.lessons.filter(id=value).exists():
                raise serializers.ValidationError(
                    "Lesson does not belong to this course"
                )
        return value


class NoteCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating Note instances
    """
    class Meta:
        model = Note
        fields = ['title', 'content', 'category']


# CourseIntroduction serializers removed - now using Course serializers directly


# ===== CLASS SERIALIZERS =====

class ClassSessionSerializer(serializers.ModelSerializer):
    """Serializer for class sessions"""
    day_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ClassSession
        fields = [
            'id', 'name', 'day_of_week', 'day_name', 'start_time', 'end_time', 
            'session_number', 'is_active'
        ]
    
    def get_day_name(self, obj):
        """Get human-readable day name"""
        day_choices = dict(ClassSession.DAY_CHOICES)
        return day_choices.get(obj.day_of_week, 'Unknown')
    
    def validate(self, data):
        """Validate session times"""
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data


class StudentBasicSerializer(serializers.ModelSerializer):
    """Basic student information for class enrollment"""
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'first_name', 'last_name']
    
    def get_name(self, obj):
        return obj.get_full_name() or obj.email


class ClassListSerializer(serializers.ModelSerializer):
    """Serializer for listing classes"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    available_spots = serializers.IntegerField(read_only=True)
    formatted_schedule = serializers.CharField(read_only=True)
    session_count = serializers.IntegerField(read_only=True)
    sessions = ClassSessionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'description', 'course_title', 'teacher_name',
            'max_capacity', 'student_count', 'is_full', 'available_spots',
            'formatted_schedule', 'session_count', 'sessions', 'is_active', 'created_at'
        ]


class ClassDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual class"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_id = serializers.CharField(source='course.id', read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    students = StudentBasicSerializer(many=True, read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    available_spots = serializers.IntegerField(read_only=True)
    formatted_schedule = serializers.CharField(read_only=True)
    session_count = serializers.IntegerField(read_only=True)
    sessions = ClassSessionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'description', 'course_id', 'course_title', 
            'teacher_name', 'students', 'max_capacity', 'student_count', 
            'is_full', 'available_spots', 'meeting_link',
            'formatted_schedule', 'session_count', 'sessions', 'is_active', 'start_date', 'end_date', 'created_at', 'updated_at'
        ]


class ClassCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating classes"""
    student_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of student IDs to enroll in the class"
    )
    
    sessions = ClassSessionSerializer(many=True, required=False, help_text="List of class sessions")
    
    class Meta:
        model = Class
        fields = [
            'name', 'description', 'course', 'max_capacity', 
            'meeting_link', 'is_active', 
            'start_date', 'end_date', 'student_ids', 'sessions'
        ]
    
    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        student_ids = validated_data.pop('student_ids', [])
        logger.info(f"Creating class with student_ids: {student_ids}")
        logger.info(f"Validated data: {validated_data}")
        
        # Set teacher from request user
        validated_data['teacher'] = self.context['request'].user
        logger.info(f"Teacher set to: {validated_data['teacher']}")
        
        try:
            # Extract sessions data before creating class
            sessions_data = validated_data.pop('sessions', [])
            logger.info(f"Creating class with {len(sessions_data)} sessions")
            
            class_instance = Class.objects.create(**validated_data)
            logger.info(f"Class created successfully: {class_instance.id}")
            
            # Create sessions for the class
            if sessions_data:
                logger.info(f"Creating {len(sessions_data)} sessions")
                for session_data in sessions_data:
                    session_data['class_instance'] = class_instance
                    ClassSession.objects.create(**session_data)
                logger.info("All sessions created successfully")
                
        except Exception as e:
            logger.error(f"Failed to create class: {e}")
            raise
        
        # Add students to the class
        if student_ids:
            logger.info(f"Processing {len(student_ids)} student IDs")
            
            try:
                # The student_ids might be EnrolledCourse IDs, so we need to get the actual User IDs
                from student.models import EnrolledCourse
                
                # The student_ids are EnrolledCourse UUIDs, not User IDs
                # We need to get the User objects from EnrolledCourse
                logger.info("Looking up users from EnrolledCourse records")
                course = validated_data.get('course') or class_instance.course
                logger.info(f"Using course: {course}")
                
                enrollments = EnrolledCourse.objects.filter(
                    id__in=student_ids,
                    course=course
                ).select_related('student_profile__user')
                logger.info(f"Found {enrollments.count()} enrollments")
                
                users = [enrollment.student_profile.user for enrollment in enrollments]
                logger.info(f"Extracted {len(users)} users from enrollments")
                
                for i, user in enumerate(users):
                    logger.info(f"User {i}: {user.id} ({type(user.id)}) - {user.get_full_name()}")
                
                logger.info(f"Setting {len(users)} students to class")
                class_instance.students.set(users)
                logger.info("Students set successfully")
                
            except Exception as e:
                logger.error(f"Error adding students to class: {e}")
                logger.error(f"Exception type: {type(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        
        logger.info(f"Class creation completed: {class_instance.id}")
        return class_instance
    
    def update(self, instance, validated_data):
        """Update class and its sessions"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Updating class {instance.id} with data: {validated_data}")
        
        # Extract sessions data before updating class
        sessions_data = validated_data.pop('sessions', None)
        
        # Update basic class fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Handle sessions update
        if sessions_data is not None:  # Only update if sessions are provided
            logger.info(f"Updating {len(sessions_data)} sessions")
            
            # Delete existing sessions
            instance.sessions.all().delete()
            logger.info("Deleted existing sessions")
            
            # Create new sessions
            if sessions_data:
                for session_data in sessions_data:
                    session_data['class_instance'] = instance
                    ClassSession.objects.create(**session_data)
                logger.info("Created new sessions")
        
        # Handle students update if provided
        student_ids = validated_data.pop('student_ids', None)
        if student_ids is not None:
            try:
                from student.models import EnrolledCourse
                course = instance.course
                enrollments = EnrolledCourse.objects.filter(
                    id__in=student_ids,
                    course=course
                ).select_related('student_profile__user')
                users = [enrollment.student_profile.user for enrollment in enrollments]
                instance.students.set(users)
                logger.info(f"Updated students: {len(users)} students")
            except Exception as e:
                logger.error(f"Error updating students: {e}")
                raise
        
        logger.info(f"Class update completed: {instance.id}")
        return instance
    
        # Update students if provided
        if student_ids is not None:
            from student.models import EnrolledCourse
            
            # The student_ids are EnrolledCourse UUIDs, get User objects from them
            enrollments = EnrolledCourse.objects.filter(
                id__in=student_ids,
                course=instance.course
            ).select_related('student_profile__user')
            users = [enrollment.student_profile.user for enrollment in enrollments]
            
            instance.students.set(users)
    
    def validate_student_ids(self, value):
        """Validate that all student IDs exist as EnrolledCourse records"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"🔍 VALIDATION: validate_student_ids called with: {value}")
        logger.info(f"🔍 VALIDATION: Type of value: {type(value)}")
        
        if not value:
            logger.info("🔍 VALIDATION: No student IDs provided, returning empty")
            return value
        
        try:
            # Since student_ids are EnrolledCourse UUIDs, validate them as such
            from student.models import EnrolledCourse
            
            logger.info(f"🔍 VALIDATION: Looking up {len(value)} EnrolledCourse records")
            enrollments = EnrolledCourse.objects.filter(id__in=value)
            found_count = enrollments.count()
            
            logger.info(f"🔍 VALIDATION: Found {found_count} enrollments out of {len(value)} requested")
            
            if found_count != len(value):
                logger.error(f"🔍 VALIDATION: Validation failed - missing enrollments")
                raise serializers.ValidationError("One or more student enrollment IDs are invalid")
            
            logger.info("🔍 VALIDATION: All student IDs validated successfully")
            return value
            
        except Exception as e:
            logger.error(f"🔍 VALIDATION: Exception during validation: {e}")
            logger.error(f"🔍 VALIDATION: Exception type: {type(e)}")
            raise
    
    def validate(self, data):
        """Validate class capacity constraints"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"🔍 MAIN VALIDATION: validate() called with data keys: {list(data.keys())}")
        
        student_ids = data.get('student_ids', [])
        max_capacity = data.get('max_capacity', 10)
        
        logger.info(f"🔍 MAIN VALIDATION: student_ids count: {len(student_ids)}")
        logger.info(f"🔍 MAIN VALIDATION: max_capacity: {max_capacity}")
        
        if len(student_ids) > max_capacity:
            logger.error(f"🔍 MAIN VALIDATION: Capacity exceeded - {len(student_ids)} > {max_capacity}")
            raise serializers.ValidationError(
                f"Cannot enroll {len(student_ids)} students. Maximum capacity is {max_capacity}."
            )
        
        logger.info("🔍 MAIN VALIDATION: All validations passed")
        return data


# ===== CLASSROOM SERIALIZERS =====

class ClassroomClassSerializer(serializers.ModelSerializer):
    """Nested serializer for class_instance in Classroom"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_id = serializers.CharField(source='course.id', read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'description', 'course_id', 'course_title',
            'teacher_name', 'max_capacity', 'student_count',
            'is_active', 'start_date', 'end_date'
        ]


class ClassroomActiveSessionSerializer(serializers.ModelSerializer):
    """Serializer for active session info in Classroom"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    lesson_id = serializers.CharField(source='lesson.id', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ClassEvent
        fields = [
            'id', 'title', 'description', 'event_type', 'lesson_type',
            'lesson_id', 'lesson_title', 'start_time', 'end_time',
            'duration_minutes'
        ]


class ClassroomSerializer(serializers.ModelSerializer):
    """Serializer for Classroom model with nested class_instance and active session info"""
    class_instance = ClassroomClassSerializer(read_only=True)
    is_session_active = serializers.SerializerMethodField()
    active_session = serializers.SerializerMethodField()
    student_count = serializers.IntegerField(read_only=True)
    tldraw_board_url = serializers.SerializerMethodField()
    teacher_settings = serializers.SerializerMethodField()
    
    class Meta:
        model = Classroom
        fields = [
            'id', 'room_code', 'is_active', 'chat_enabled', 'board_enabled',
            'video_enabled', 'ide_enabled', 'virtual_lab_enabled',
            'class_instance', 'is_session_active',
            'active_session', 'student_count', 'tldraw_board_url',
            'teacher_settings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'room_code', 'created_at', 'updated_at']
    
    def get_is_session_active(self, obj):
        """Check if there's an active session"""
        return obj.is_session_active()
    
    def get_active_session(self, obj):
        """Get active session data"""
        active_session = obj.get_active_session()
        if active_session:
            return ClassroomActiveSessionSerializer(active_session).data
        return None
    
    def get_tldraw_board_url(self, obj):
        """Get tldraw board URL (generates board ID on-demand if needed)"""
        return obj.get_tldraw_board_url()
    
    def get_teacher_settings(self, obj):
        """Get teacher settings for tool URLs"""
        try:
            from settings.models import UserDashboardSettings, ClassroomToolDefaults
            
            teacher = obj.class_instance.teacher
            if not teacher:
                return None
            
            settings = UserDashboardSettings.get_or_create_settings(teacher)
            app_defaults = ClassroomToolDefaults.get_or_create_defaults()
            
            return {
                'whiteboard_url': settings.whiteboard_url or app_defaults.whiteboard_url,
                'ide_url': settings.ide_url or app_defaults.ide_url,
                'virtual_lab_url': settings.virtual_lab_url or app_defaults.virtual_lab_url,
                'app_defaults': {
                    'whiteboard_url': app_defaults.whiteboard_url,
                    'ide_url': app_defaults.ide_url,
                    'virtual_lab_url': app_defaults.virtual_lab_url,
                }
            }
        except Exception as e:
            # Return None if settings can't be retrieved - frontend will handle gracefully
            return None


class ClassroomCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a Classroom"""
    room_code = serializers.CharField(required=False, allow_blank=True, max_length=20)
    
    class Meta:
        model = Classroom
        fields = [
            'class_instance', 'room_code', 'is_active',
            'chat_enabled', 'board_enabled', 'video_enabled'
        ]
    
    def validate_class_instance(self, value):
        """Ensure classroom doesn't already exist for this class"""
        if Classroom.objects.filter(class_instance=value).exists():
            raise serializers.ValidationError(
                "A classroom already exists for this class."
            )
        return value


class ClassroomUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Classroom settings"""
    
    class Meta:
        model = Classroom
        fields = [
            'is_active', 'chat_enabled', 'board_enabled', 'video_enabled',
            'ide_enabled', 'virtual_lab_enabled'
        ]


# ===== BOARD SERIALIZERS =====

class BoardPageSerializer(serializers.ModelSerializer):
    """Serializer for BoardPage model"""
    
    class Meta:
        model = BoardPage
        fields = [
            'id', 'page_name', 'page_order', 'state', 'version',
            'created_by', 'last_updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'created_by', 'last_updated_by', 'created_at', 'updated_at']


class BoardPageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing board pages (without state)"""
    
    class Meta:
        model = BoardPage
        fields = [
            'id', 'page_name', 'page_order', 'version',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'created_at', 'updated_at']


class BoardPageStateSerializer(serializers.ModelSerializer):
    """Serializer for saving/loading board page state"""
    
    class Meta:
        model = BoardPage
        fields = ['state', 'version']
        read_only_fields = ['version']


class BoardSerializer(serializers.ModelSerializer):
    """Serializer for Board model with pages list"""
    pages = BoardPageListSerializer(many=True, read_only=True)
    current_page = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_create_pages = serializers.SerializerMethodField()
    
    class Meta:
        model = Board
        fields = [
            'id', 'title', 'description',
            'allow_student_edit', 'allow_student_create_pages', 'view_only_mode',
            'current_page_id', 'current_page', 'pages',
            'can_edit', 'can_create_pages',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_current_page(self, obj):
        """Get the current page data"""
        page = obj.get_current_page()
        if page:
            return BoardPageListSerializer(page).data
        return None
    
    def get_can_edit(self, obj):
        """Check if current user can edit"""
        request = self.context.get('request')
        if request and request.user:
            return obj.can_user_edit(request.user)
        return False
    
    def get_can_create_pages(self, obj):
        """Check if current user can create pages"""
        request = self.context.get('request')
        if request and request.user:
            return obj.can_user_create_pages(request.user)
        return False


class BoardUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Board settings"""
    
    class Meta:
        model = Board
        fields = [
            'title', 'description',
            'allow_student_edit', 'allow_student_create_pages', 'view_only_mode',
            'current_page_id'
        ]


# ===== PROJECT SERIALIZERS =====

class ProjectPlatformSerializer(serializers.ModelSerializer):
    """Serializer for project platforms"""
    
    class Meta:
        model = ProjectPlatform
        fields = [
            'id', 'name', 'display_name', 'description', 'platform_type',
            'base_url', 'icon', 'color', 'min_age', 'max_age', 'skill_levels',
            'is_active', 'is_featured', 'is_free'
        ]


class ProjectListSerializer(serializers.ModelSerializer):
    """Serializer for listing projects"""
    allowed_file_types = serializers.JSONField(read_only=True)
    project_platform = serializers.SerializerMethodField()
    submission_type = serializers.SerializerMethodField()
    due_at = serializers.SerializerMethodField()
    meeting_link = serializers.SerializerMethodField()
    
    def get_project_platform(self, obj):
        """Get project platform from associated ClassEvent if available"""
        # Get the most recent ClassEvent for this project that has a platform
        from .models import ClassEvent
        event = ClassEvent.objects.filter(
            project=obj,
            project_platform__isnull=False
        ).select_related('project_platform').order_by('-created_at').first()
        
        if event and event.project_platform:
            return {
                'id': str(event.project_platform.id),
                'name': event.project_platform.name,
                'display_name': event.project_platform.display_name,
                'base_url': event.project_platform.base_url,
            }
        return None
    
    def get_submission_type(self, obj):
        """Get submission_type from associated ClassEvent if available, otherwise from Project"""
        # Get the most recent ClassEvent for this project that has a submission_type
        from .models import ClassEvent
        event = ClassEvent.objects.filter(
            project=obj,
            submission_type__isnull=False
        ).order_by('-created_at').first()
        
        # Prefer submission_type from ClassEvent if available, otherwise use Project's
        if event and event.submission_type:
            # Return the name (internal identifier) of the submission type
            submission_type_name = event.submission_type.name if hasattr(event.submission_type, 'name') else str(event.submission_type)
            print(f"🔍 ProjectListSerializer: Using submission_type '{submission_type_name}' from ClassEvent {event.id} for project {obj.id}")
            return submission_type_name
        
        # Return the name (internal identifier) of the submission type
        submission_type_name = obj.submission_type.name if obj.submission_type and hasattr(obj.submission_type, 'name') else str(obj.submission_type) if obj.submission_type else None
        print(f"🔍 ProjectListSerializer: Using submission_type '{submission_type_name}' from Project {obj.id} (no ClassEvent found)")
        return submission_type_name
    
    def get_due_at(self, obj):
        """Get due_at from associated ClassEvent if available, otherwise from Project"""
        # Get the most recent ClassEvent for this project that has a due_date
        from .models import ClassEvent
        event = ClassEvent.objects.filter(
            project=obj,
            due_date__isnull=False
        ).order_by('-created_at').first()
        
        # Prefer due_date from ClassEvent if available, otherwise use Project's
        if event and event.due_date:
            return event.due_date.isoformat()
        if obj.due_at:
            return obj.due_at.isoformat()
        return None
    
    def get_meeting_link(self, obj):
        """Get meeting_link from associated ClassEvent if available"""
        # Get the most recent ClassEvent for this project that has a meeting_link
        from .models import ClassEvent
        event = ClassEvent.objects.filter(
            project=obj,
            meeting_link__isnull=False
        ).exclude(meeting_link='').order_by('-created_at').first()
        
        if event and event.meeting_link:
            return event.meeting_link
        return None
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'instructions', 'submission_type', 'points', 'due_at', 
            'order', 'created_at', 'allowed_file_types', 'project_platform', 'meeting_link'
        ]


class StudentProjectSubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer for ProjectSubmission model - Student view
    Similar to AssignmentSubmission structure
    """
    project_title = serializers.CharField(source='project.title', read_only=True)
    project_points = serializers.IntegerField(source='project.points', read_only=True)
    project_instructions = serializers.CharField(source='project.instructions', read_only=True)
    submission_type = serializers.SerializerMethodField()
    project_platform = serializers.SerializerMethodField()
    points_possible = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    passed = serializers.SerializerMethodField()
    is_graded = serializers.SerializerMethodField()
    grader_name = serializers.SerializerMethodField()
    
    def get_points_possible(self, obj):
        """Get total points possible from project"""
        return obj.project.points
    
    def get_percentage(self, obj):
        """Calculate percentage score"""
        if obj.points_earned is not None and obj.project.points > 0:
            return float((obj.points_earned / obj.project.points) * 100)
        return None
    
    def get_passed(self, obj):
        """Check if student passed (assuming 70% passing score like assignments)"""
        percentage = self.get_percentage(obj)
        if percentage is not None:
            return percentage >= 70.0
        return False
    
    def get_is_graded(self, obj):
        """Check if submission is graded"""
        return obj.status == 'GRADED'
    
    def get_grader_name(self, obj):
        """Get grader name"""
        if obj.grader:
            return obj.grader.get_full_name() or obj.grader.email
        return None
    
    def get_project_platform(self, obj):
        """Get project platform from associated ClassEvent if available"""
        # Get the most recent ClassEvent for this project that has a platform
        from .models import ClassEvent
        event = ClassEvent.objects.filter(
            project=obj.project,
            project_platform__isnull=False
        ).select_related('project_platform').order_by('-created_at').first()
        
        if event and event.project_platform:
            return {
                'id': str(event.project_platform.id),
                'name': event.project_platform.name,
                'display_name': event.project_platform.display_name,
                'base_url': event.project_platform.base_url,
            }
        return None
    
    def get_submission_type(self, obj):
        """Get submission_type from associated ClassEvent if available, otherwise from Project"""
        # Get the most recent ClassEvent for this project that has a submission_type
        from .models import ClassEvent
        event = ClassEvent.objects.filter(
            project=obj.project,
            submission_type__isnull=False
        ).order_by('-created_at').first()
        
        # Prefer submission_type from ClassEvent if available, otherwise use Project's
        if event and event.submission_type:
            # Return the name (internal identifier) of the submission type
            submission_type_name = event.submission_type.name if hasattr(event.submission_type, 'name') else str(event.submission_type)
            return submission_type_name
        
        # Return the name (internal identifier) of the submission type
        submission_type_name = obj.project.submission_type.name if obj.project.submission_type and hasattr(obj.project.submission_type, 'name') else str(obj.project.submission_type) if obj.project.submission_type else None
        return submission_type_name
    
    class Meta:
        model = ProjectSubmission
        fields = [
            'id', 'project', 'project_title', 'project_points', 'project_instructions',
            'submission_type', 'project_platform', 'status',
            'content', 'file_url', 'reflection', 'submitted_at', 'graded_at',
            'points_earned', 'points_possible', 'percentage', 'passed', 'is_graded',
            'feedback', 'feedback_response', 'feedback_checked', 'feedback_checked_at',
            'grader_name', 'share_token', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'project', 'submitted_at', 'graded_at', 'points_earned',
            'feedback', 'feedback_response', 'feedback_checked', 'feedback_checked_at',
            'grader', 'created_at', 'updated_at'
        ]


class PublicProjectSubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer for public shared project submission (portfolio view)
    Excludes sensitive information like grades and feedback
    """
    project = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    
    def get_project(self, obj):
        """Get project details"""
        project_data = {
            'id': str(obj.project.id),
            'title': obj.project.title,
            'instructions': obj.project.instructions,
            'submission_type': obj.project.submission_type.name if obj.project.submission_type else None,
        }
        
        # Add project_platform if it exists
        if obj.project.project_platform:
            project_data['project_platform'] = {
                'id': str(obj.project.project_platform.id),
                'name': obj.project.project_platform.name,
                'display_name': obj.project.project_platform.display_name,
                'base_url': obj.project.project_platform.base_url,
            }
        
        return project_data
    
    def get_student(self, obj):
        """Get student details"""
        return {
            'id': str(obj.student.id),
            'name': obj.student.get_full_name() or obj.student.email,
            'first_name': obj.student.first_name,
            'last_name': obj.student.last_name,
            'email': obj.student.email,
        }
    
    def get_course_title(self, obj):
        """Get course title"""
        return obj.project.course.title if obj.project.course else None
    
    class Meta:
        model = ProjectSubmission
        fields = [
            'id', 'project', 'student', 'course_title',
            'content', 'file_url', 'submitted_at', 'created_at'
        ]
        read_only_fields = fields


# ===== CLASS SERIALIZERS =====

class ClassEventListSerializer(serializers.ModelSerializer):
    """Serializer for listing class events"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    project_platform_name = serializers.CharField(source='project_platform.display_name', read_only=True)
    submission_type_name = serializers.SerializerMethodField()
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    assessment_type = serializers.CharField(source='assessment.assessment_type', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    def get_submission_type_name(self, obj):
        """Get submission type name (internal identifier)"""
        if obj.submission_type:
            return obj.submission_type.name if hasattr(obj.submission_type, 'name') else str(obj.submission_type)
        return None
    
    class Meta:
        model = ClassEvent
        fields = [
            'id', 'title', 'description', 'event_type', 'start_time', 'end_time',
            'lesson_title', 'project_title', 'project_platform_name', 
            'assessment_title', 'assessment_type', 'lesson_type', 
            'duration_minutes', 'meeting_platform', 'meeting_link',
            'meeting_id', 'meeting_password', 'due_date', 'submission_type_name', 'created_at'
        ]


class ClassEventDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual class event"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    lesson_id = serializers.CharField(source='lesson.id', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    project_id = serializers.CharField(source='project.id', read_only=True)
    project_platform_name = serializers.CharField(source='project_platform.display_name', read_only=True)
    project_platform_id = serializers.CharField(source='project_platform.id', read_only=True)
    submission_type_name = serializers.SerializerMethodField()
    submission_type_display = serializers.SerializerMethodField()
    assessment_id = serializers.CharField(source='assessment.id', read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    assessment_type = serializers.CharField(source='assessment.assessment_type', read_only=True)
    
    def get_submission_type_name(self, obj):
        """Get submission type name (internal identifier)"""
        if obj.submission_type:
            return obj.submission_type.name if hasattr(obj.submission_type, 'name') else str(obj.submission_type)
        return None
    
    def get_submission_type_display(self, obj):
        """Get submission type display name"""
        if obj.submission_type:
            return obj.submission_type.display_name if hasattr(obj.submission_type, 'display_name') else str(obj.submission_type)
        return None
    class_name = serializers.CharField(source='class_instance.name', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ClassEvent
        fields = [
            'id', 'title', 'description', 'event_type', 'start_time', 'end_time',
            'lesson', 'lesson_id', 'lesson_title', 'project', 'project_id', 'project_title',
            'project_platform', 'project_platform_id', 'project_platform_name',
            'submission_type', 'submission_type_name', 'submission_type_display',
            'assessment', 'assessment_id', 'assessment_title', 'assessment_type',
            'lesson_type', 'class_name', 'duration_minutes',
            'meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password',
            'due_date', 'submission_type', 'created_at', 'updated_at'
        ]


class ClassEventCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating class events"""
    
    # Override submission_type to accept string name or object
    submission_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = ClassEvent
        fields = [
            'title', 'description', 'event_type', 'start_time', 'end_time', 
            'lesson', 'project', 'project_platform', 'project_title', 'due_date', 'submission_type',
            'lesson_type', 'meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password',
            'assessment'
        ]
    
    def validate(self, data):
        """Validate event data"""
        event_type = data.get('event_type')
        
        # For non-project events (lesson, meeting, break, test, exam), validate start_time and end_time
        if event_type != 'project':
            if data.get('start_time') and data.get('end_time'):
                if data['end_time'] <= data['start_time']:
                    raise serializers.ValidationError("End time must be after start time")
        
        # Validate lesson events
        if event_type == 'lesson' and not data.get('lesson'):
            raise serializers.ValidationError("Lesson events must have an associated lesson")
        
        # Validate assessment events (test and exam)
        if event_type in ['test', 'exam']:
            if not data.get('assessment'):
                raise serializers.ValidationError("Assessment events must have an associated assessment")
        
        # Validate project events
        if event_type == 'project':
            if not data.get('project'):
                raise serializers.ValidationError("Project is required for project events")
            if not data.get('project_platform'):
                raise serializers.ValidationError("Project platform is required for project events")
            
            # For project events, due_date is required instead of start_time/end_time
            if not data.get('due_date'):
                raise serializers.ValidationError("Due date is required for project events")
            
            # Handle submission_type if passed as string (name) - convert to object
            submission_type = data.get('submission_type')
            if submission_type and isinstance(submission_type, str):
                from .models import SubmissionType
                try:
                    submission_type_obj = SubmissionType.objects.get(name=submission_type, is_active=True)
                    data['submission_type'] = submission_type_obj
                except SubmissionType.DoesNotExist:
                    raise serializers.ValidationError(f"Submission type '{submission_type}' not found or inactive")
            
            # Auto-set submission_type to 'code' if Ace Pyodide platform is selected
            project_platform = data.get('project_platform')
            if project_platform:
                platform_name = None
                
                # Handle if platform is passed as string UUID
                if isinstance(project_platform, str):
                    from .models import ProjectPlatform
                    try:
                        platform_obj = ProjectPlatform.objects.get(id=project_platform)
                        platform_name = platform_obj.name
                    except (ProjectPlatform.DoesNotExist, ValueError):
                        pass
                # Handle if platform is already an object
                elif hasattr(project_platform, 'name'):
                    platform_name = project_platform.name
                # Handle if platform is passed as ID (UUID object)
                elif hasattr(project_platform, 'id'):
                    from .models import ProjectPlatform
                    try:
                        platform_obj = ProjectPlatform.objects.get(id=project_platform.id)
                        platform_name = platform_obj.name
                    except ProjectPlatform.DoesNotExist:
                        pass
                
                # If Ace Pyodide is selected and no submission_type is set, auto-set to 'code'
                if platform_name == 'ace_pyodide' and not data.get('submission_type'):
                    from .models import SubmissionType
                    try:
                        code_submission_type = SubmissionType.objects.get(name='code', is_active=True)
                        data['submission_type'] = code_submission_type
                    except SubmissionType.DoesNotExist:
                        pass  # If code type doesn't exist, let validation handle it
        
        return data
    
    def create(self, validated_data):
        """Create a new class event"""
        # Get class_instance from context
        class_instance = self.context.get('class_instance')
        if not class_instance:
            raise serializers.ValidationError("Class instance is required")
        
        # Handle submission_type if passed as string (name) - convert to object
        submission_type = validated_data.pop('submission_type', None)
        if submission_type:
            if isinstance(submission_type, str):
                from .models import SubmissionType
                try:
                    submission_type_obj = SubmissionType.objects.get(name=submission_type, is_active=True)
                    validated_data['submission_type'] = submission_type_obj
                except SubmissionType.DoesNotExist:
                    raise serializers.ValidationError(f"Submission type '{submission_type}' not found or inactive")
            else:
                # Already an object
                validated_data['submission_type'] = submission_type
        else:
            # No submission_type provided, set to None
            validated_data['submission_type'] = None
        
        validated_data['class_instance'] = class_instance
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update an existing class event"""
        # Handle submission_type if passed as string (name) - convert to object
        submission_type = validated_data.pop('submission_type', None)
        if submission_type is not None:
            if isinstance(submission_type, str):
                from .models import SubmissionType
                try:
                    submission_type_obj = SubmissionType.objects.get(name=submission_type, is_active=True)
                    validated_data['submission_type'] = submission_type_obj
                except SubmissionType.DoesNotExist:
                    raise serializers.ValidationError(f"Submission type '{submission_type}' not found or inactive")
            else:
                # Already an object
                validated_data['submission_type'] = submission_type
        # If submission_type is None, it will remain as is (nullable field)
        
        # Auto-set submission_type to 'code' if Ace Pyodide platform is selected
        project_platform = validated_data.get('project_platform', instance.project_platform)
        if project_platform:
            platform_name = None
            
            # Handle if platform is passed as string UUID
            if isinstance(project_platform, str):
                from .models import ProjectPlatform
                try:
                    platform_obj = ProjectPlatform.objects.get(id=project_platform)
                    platform_name = platform_obj.name
                except (ProjectPlatform.DoesNotExist, ValueError):
                    pass
            # Handle if platform is already an object
            elif hasattr(project_platform, 'name'):
                platform_name = project_platform.name
            
            if platform_name == 'ace_pyodide' and not validated_data.get('submission_type') and not instance.submission_type:
                from .models import SubmissionType
                try:
                    code_submission_type = SubmissionType.objects.get(name='code', is_active=True)
                    validated_data['submission_type'] = code_submission_type
                except SubmissionType.DoesNotExist:
                    pass
        
        return super().update(instance, validated_data)


# ===== LESSON MATERIAL SERIALIZERS =====

class LessonMaterialCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating lesson materials
    """
    # Use CharField for file_url to allow more lenient validation for link materials
    # We'll validate and convert to URL format in validate_file_url
    file_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = LessonMaterial
        fields = [
            'title', 'description', 'material_type', 'file_url', 
            'file_size', 'file_extension', 'is_required', 
            'is_downloadable', 'order'
        ]
    
    def validate_material_type(self, value):
        """Validate material type"""
        valid_types = [choice[0] for choice in LessonMaterial.MATERIAL_TYPES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid material type. Must be one of: {valid_types}")
        return value
    
    def validate_file_size(self, value):
        """Validate file size"""
        if value is not None and value < 0:
            raise serializers.ValidationError("File size cannot be negative")
        return value
    
    def validate_file_url(self, value):
        """Validate file URL - required for link materials, more lenient validation"""
        material_type = self.initial_data.get('material_type')
        
        if material_type == 'link':
            if not value or (isinstance(value, str) and not value.strip()):
                raise serializers.ValidationError("URL is required for link materials")
            # Ensure value is a string
            if not isinstance(value, str):
                raise serializers.ValidationError("URL must be a string")
            # Basic URL format validation - allow any string starting with http:// or https://
            value = value.strip()
            if not value.startswith(('http://', 'https://')):
                raise serializers.ValidationError("URL must start with http:// or https://")
            # For link materials, we accept the URL as-is (even if Django URLField would reject it)
            # The model's URLField will handle storage
        elif value:
            # For other material types, validate as URL if provided
            value = value.strip() if isinstance(value, str) else value
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        material_type = data.get('material_type')
        
        # For link materials, file_url is required
        if material_type == 'link':
            file_url = data.get('file_url')
            if not file_url or (isinstance(file_url, str) and not file_url.strip()):
                raise serializers.ValidationError({
                    'file_url': ['URL is required for link materials']
                })
        
        return data


class LessonMaterialUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating lesson materials
    """
    class Meta:
        model = LessonMaterial
        fields = [
            'title', 'description', 'material_type', 'file_url', 
            'file_size', 'file_extension', 'is_required', 
            'is_downloadable', 'order'
        ]
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
            'material_type': {'required': False},
            'file_url': {'required': False},
            'file_size': {'required': False},
            'file_extension': {'required': False},
            'is_required': {'required': False},
            'is_downloadable': {'required': False},
            'order': {'required': False},
        }


# ===== BOOK CREATION SERIALIZER (Single API Call) =====

class BookPageNestedSerializer(serializers.ModelSerializer):
    """
    Nested serializer for book pages within book creation
    """
    class Meta:
        model = BookPage
        fields = ['title', 'content', 'is_required']
    
    def validate_content(self, value):
        """Validate content is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Page content cannot be empty")
        return value


class BookCreationSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a complete book with pages in a single API call
    """
    pages = BookPageNestedSerializer(many=True, write_only=True)
    
    class Meta:
        model = LessonMaterial
        fields = [
            'title', 'description', 'material_type', 'is_required', 
            'is_downloadable', 'order', 'pages'
        ]
        extra_kwargs = {
            'material_type': {'default': 'book'},
            'order': {'default': 0}
        }
    
    def validate_pages(self, value):
        """Validate that at least one page is provided"""
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one page is required")
        return value
    
    def create(self, validated_data):
        """Create book material and all pages in a single transaction"""
        pages_data = validated_data.pop('pages')
        
        # Create the book material
        book_material = LessonMaterial.objects.create(**validated_data)
        
        # Create all pages
        created_pages = []
        for i, page_data in enumerate(pages_data, 1):
            page = BookPage.objects.create(
                book_material=book_material,
                page_number=i,
                **page_data
            )
            created_pages.append(page)
        
        # Add pages to the material for response
        book_material.created_pages = created_pages
        return book_material


# ===== BOOK PAGE SERIALIZERS =====

class BookPageCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating book pages
    """
    class Meta:
        model = BookPage
        fields = [
            'title', 'content', 'is_required'
        ]
    
    def validate_content(self, value):
        """Validate content is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Page content cannot be empty")
        return value
    
    def create(self, validated_data):
        """Create a new book page with the provided book_material and page_number"""
        book_material = self.context.get('book_material')
        page_number = self.context.get('page_number')
        
        if not book_material:
            raise serializers.ValidationError("book_material is required")
        if not page_number:
            raise serializers.ValidationError("page_number is required")
        
        return BookPage.objects.create(
            book_material=book_material,
            page_number=page_number,
            **validated_data
        )


class BookPageUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating book pages
    """
    class Meta:
        model = BookPage
        fields = [
            'title', 'content', 'is_required'
        ]
        extra_kwargs = {
            'title': {'required': False},
            'content': {'required': False},
            'is_required': {'required': False}
        }
    
    def validate_content(self, value):
        """Validate content is not empty if provided"""
        if value is not None and not value.strip():
            raise serializers.ValidationError("Page content cannot be empty")
        return value


# ===== VIDEO MATERIAL SERIALIZERS =====

class VideoMaterialSerializer(serializers.ModelSerializer):
    """
    Serializer for video materials with transcript data
    """
    has_transcript = serializers.ReadOnlyField()
    
    class Meta:
        model = VideoMaterial
        fields = [
            'id', 'lesson_material', 'video_url', 'video_id', 'is_youtube',
            'transcript', 'language', 'language_name', 'method_used',
            'transcript_length', 'word_count', 'has_transcript',
            'transcript_available_to_students',
            'created_at', 'updated_at', 'transcribed_at'
        ]
        read_only_fields = [
            'id', 'video_id', 'is_youtube', 'transcript_length', 'word_count',
            'has_transcript', 'created_at', 'updated_at', 'transcribed_at'
        ]
    
    def update(self, instance, validated_data):
        """
        Update video material, especially transcript and availability settings.
        Auto-update transcript_length and word_count if transcript changes.
        Also allows updating lesson_material link.
        """
        # Update lesson_material if provided
        if 'lesson_material' in validated_data:
            instance.lesson_material = validated_data['lesson_material']
        
        # Update transcript if provided
        if 'transcript' in validated_data:
            instance.transcript = validated_data['transcript']
            # Auto-calculate length and word count
            if instance.transcript:
                instance.transcript_length = len(instance.transcript)
                instance.word_count = len(instance.transcript.split())
            else:
                instance.transcript_length = None
                instance.word_count = None
        
        # Update transcript_available_to_students if provided
        if 'transcript_available_to_students' in validated_data:
            instance.transcript_available_to_students = validated_data['transcript_available_to_students']
        
        instance.save()
        return instance


class VideoMaterialCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating video materials
    """
    class Meta:
        model = VideoMaterial
        fields = ['video_url', 'lesson_material']
        extra_kwargs = {
            'lesson_material': {'required': False}
        }
    
    def validate_video_url(self, value):
        """Validate video URL"""
        if not value:
            raise serializers.ValidationError("Video URL is required")
        return value


class VideoMaterialTranscribeSerializer(serializers.Serializer):
    """
    Serializer for transcribing a video material
    """
    language_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Optional list of language codes to try (e.g., ['en', 'es'])"
    )
    
    def validate_language_codes(self, value):
        """Validate language codes"""


class DocumentMaterialSerializer(serializers.ModelSerializer):
    """
    Serializer for document materials with file metadata
    """
    file_size_mb = serializers.ReadOnlyField()
    is_pdf = serializers.ReadOnlyField()
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)
    
    class Meta:
        model = DocumentMaterial
        fields = [
            'id',
            'lesson_material',
            'file_name',
            'original_filename',
            'file_url',
            'file_size',
            'file_size_mb',
            'file_extension',
            'mime_type',
            'uploaded_by',
            'uploaded_by_email',
            'is_pdf',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AudioVideoMaterialSerializer(serializers.ModelSerializer):
    """
    Serializer for audio/video materials with file metadata
    """
    file_size_mb = serializers.ReadOnlyField()
    is_audio = serializers.ReadOnlyField()
    is_video = serializers.ReadOnlyField()
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)
    
    class Meta:
        model = AudioVideoMaterial
        fields = [
            'id',
            'lesson_material',
            'file_name',
            'original_filename',
            'file_url',
            'file_size',
            'file_size_mb',
            'file_extension',
            'mime_type',
            'uploaded_by',
            'uploaded_by_email',
            'is_audio',
            'is_video',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DocumentMaterialCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating document materials
    """
    class Meta:
        model = DocumentMaterial
        fields = [
            'file_name',
            'original_filename',
            'file_url',
            'file_size',
            'file_extension',
            'mime_type',
            'lesson_material',
        ]
        extra_kwargs = {
            'lesson_material': {'required': False}
        }
    
    def validate_file_url(self, value):
        """Validate file URL"""
        if not value:
            raise serializers.ValidationError("File URL is required")
        return value
    
    def validate_file_size(self, value):
        """Validate file size (max 50MB)"""
        max_size = 50 * 1024 * 1024  # 50MB in bytes
        if value > max_size:
            raise serializers.ValidationError(f"File size exceeds maximum allowed size of 50MB")
        return value
    
    def validate_file_extension(self, value):
        """Validate file extension"""
        allowed_extensions = ['pdf', 'docx', 'doc', 'txt']
        if value.lower() not in allowed_extensions:
            raise serializers.ValidationError(
                f"File extension '{value}' not allowed. Allowed extensions: {', '.join(allowed_extensions)}"
            )
            return value.lower()


# ===== COURSE ASSESSMENT SERIALIZERS =====

class CourseAssessmentQuestionSerializer(serializers.ModelSerializer):
    """Serializer for assessment questions"""
    
    class Meta:
        model = CourseAssessmentQuestion
        fields = [
            'id', 'assessment', 'question_text', 'order', 'points',
            'type', 'content', 'explanation', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'assessment', 'created_at', 'updated_at']


class CourseAssessmentQuestionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating assessment questions"""
    
    class Meta:
        model = CourseAssessmentQuestion
        fields = [
            'question_text', 'order', 'points', 'type', 'content', 'explanation'
        ]
    
    def validate_content(self, value):
        """Validate question content based on type"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Content must be a JSON object")
        
        # Validate code question content
        question_type = self.initial_data.get('type')
        if question_type == 'code':
            if 'language' not in value:
                raise serializers.ValidationError("Code questions require 'language' field")
        
        return value


class CourseAssessmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing assessments"""
    question_count = serializers.ReadOnlyField()
    total_points = serializers.ReadOnlyField()
    
    class Meta:
        model = CourseAssessment
        fields = [
            'id', 'course', 'assessment_type', 'title', 'description', 'instructions',
            'time_limit_minutes', 'passing_score', 'max_attempts',
            'order', 'question_count', 'total_points', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course', 'question_count', 'total_points', 'created_at', 'updated_at']


class CourseAssessmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual assessment"""
    questions = CourseAssessmentQuestionSerializer(many=True, read_only=True)
    question_count = serializers.ReadOnlyField()
    total_points = serializers.ReadOnlyField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    
    class Meta:
        model = CourseAssessment
        fields = [
            'id', 'course', 'assessment_type', 'title', 'description', 'instructions',
            'time_limit_minutes', 'passing_score', 'max_attempts',
            'order', 'questions', 'question_count', 'total_points',
            'created_by', 'created_by_email', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course', 'questions', 'question_count', 'total_points', 'created_by', 'created_at', 'updated_at']


class CourseAssessmentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating assessments"""
    
    class Meta:
        model = CourseAssessment
        fields = [
            'assessment_type', 'title', 'description', 'instructions',
            'time_limit_minutes', 'passing_score', 'max_attempts', 'order'
        ]
    
    def validate_assessment_type(self, value):
        """Validate assessment type"""
        if value not in ['test', 'exam']:
            raise serializers.ValidationError("Assessment type must be 'test' or 'exam'")
        return value
    
    def validate_passing_score(self, value):
        """Validate passing score"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Passing score must be between 0 and 100")
        return value
    
    def validate_time_limit_minutes(self, value):
        """Validate time limit"""
        if value is not None and value < 1:
            raise serializers.ValidationError("Time limit must be at least 1 minute")
        return value


# ===== COURSE ASSESSMENT SUBMISSION SERIALIZERS =====

class CourseAssessmentSubmissionSerializer(serializers.Serializer):
    """Serializer for assessment submission requests"""
    answers = serializers.JSONField(help_text="Student answers for each question")
    time_remaining_seconds = serializers.IntegerField(
        required=False, 
        allow_null=True,
        help_text="Remaining time in seconds (for auto-save)"
    )
    is_auto_submit = serializers.BooleanField(
        default=False,
        help_text="Whether this was auto-submitted (timeout or page close)"
    )
    
    def validate_answers(self, value):
        """Validate that answers is a dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Answers must be a dictionary")
        return value


class CourseAssessmentSubmissionResponseSerializer(serializers.ModelSerializer):
    """Serializer for assessment submission responses"""
    
    class Meta:
        model = CourseAssessmentSubmission
        fields = [
            'id', 'attempt_number', 'status', 'started_at', 'submitted_at',
            'time_limit_minutes', 'time_remaining_seconds',
            'answers', 'is_graded', 'is_teacher_draft', 'points_earned', 'points_possible', 
            'percentage', 'passed', 'instructor_feedback', 'graded_questions'
        ]
        read_only_fields = fields


class CourseAssessmentGradingSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for grading course assessments (tests/exams)
    Similar to AssignmentGradingSerializer for consistency
    """
    class Meta:
        model = CourseAssessmentSubmission
        fields = [
            'status', 'is_graded', 'is_teacher_draft', 'points_earned', 'points_possible', 
            'instructor_feedback', 'graded_questions'
        ]
    
    def validate(self, data):
        """Validate grading data"""
        if data.get('is_graded'):
            if data.get('points_earned') is None:
                raise serializers.ValidationError("Points earned is required for graded submissions")
            if data.get('points_possible') is None:
                raise serializers.ValidationError("Points possible is required for graded submissions")
        
        # Normalize graded_questions to ensure consistent structure
        if 'graded_questions' in data and isinstance(data['graded_questions'], list):
            normalized_questions = []
            for q in data['graded_questions']:
                normalized_q = {
                    'question_id': q.get('question_id'),
                    'points_earned': q.get('points_earned', 0),
                    'points_possible': q.get('points_possible'),
                    # Accept both 'feedback' and 'teacher_feedback' for backward compatibility
                    'teacher_feedback': q.get('teacher_feedback') or q.get('feedback', ''),
                    # Include correct_answer if provided
                    'correct_answer': q.get('correct_answer'),
                    # Include is_correct if provided (for backward compatibility)
                    'is_correct': q.get('is_correct'),
                }
                # Remove None values to keep JSON clean
                normalized_q = {k: v for k, v in normalized_q.items() if v is not None}
                normalized_questions.append(normalized_q)
            data['graded_questions'] = normalized_questions
        
        return data
