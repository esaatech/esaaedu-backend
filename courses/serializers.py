from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Course, Lesson, LessonMaterial, Quiz, Question, QuizAttempt, Note, CourseReview, Class, ClassSession, ClassEvent, Project, ProjectPlatform

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
    """
    file_size_mb = serializers.ReadOnlyField()
    
    class Meta:
        model = LessonMaterial
        fields = [
            'id', 'title', 'description', 'material_type', 'file_url', 
            'file_size', 'file_size_mb', 'file_extension', 'is_required', 
            'is_downloadable', 'order', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ===== OPTIMIZED LESSON SERIALIZERS FOR 2-CALL STRATEGY =====

class LessonListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for lesson list (first API call)
    Returns minimal lesson data for the course page
    """
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'type', 'duration', 'order', 
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class LessonDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for individual lesson details (second API call)
    Returns full lesson data including materials, quiz, and class events
    """
    materials = serializers.SerializerMethodField()
    quiz = serializers.SerializerMethodField()
    class_event = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    prerequisites = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'type', 'duration', 'order',
            'text_content', 'video_url', 'audio_url', 'live_class_date', 
            'live_class_status', 'content', 'materials', 'prerequisites',
            'quiz', 'class_event', 'teacher_name', 'course_title',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_quiz(self, obj):
        """Get pre-computed quiz data from context"""
        return self.context.get('quiz_data')
    
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
        """Get detailed information for the current/first lesson"""
        try:
            # Get the first lesson or current lesson based on enrollment progress
            student_profile = self.context.get('student_profile')
            if student_profile:
                # Try to get current lesson from enrollment
                from student.models import EnrolledCourse
                enrollment = EnrolledCourse.objects.filter(
                    student_profile=student_profile,
                    course=obj,
                    status__in=['active', 'completed']
                ).first()
                
                if enrollment and hasattr(enrollment, 'current_lesson') and enrollment.current_lesson:
                    current_lesson = enrollment.current_lesson
                else:
                    # Fallback to first lesson
                    current_lesson = obj.lessons.order_by('order').first()
            else:
                # No student context, return first lesson
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
        """Get enrollment information for the student"""
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
                
            return {
                'current_lesson_id': str(enrollment.current_lesson.id) if enrollment.current_lesson else None,
                'completed_lessons_count': enrollment.completed_lessons_count,
                'progress_percentage': float(enrollment.progress_percentage),
                'course_completed': enrollment.status == 'completed'
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
            'level', 'price', 'featured', 'popular', 'color', 'icon',
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
            'age_range', 'level', 'price', 'features',
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
            'age_range', 'level', 'price', 'is_free', 'features',
            'featured', 'popular', 'color', 'icon', 'image', 'max_students',
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
    
    class Meta:
        model = Course
        fields = [
            'id', 'icon', 'title', 'description', 'longDescription',
            'age', 'duration_weeks', 'duration', 'level', 'color', 'projects', 'price',
            'popular', 'featured', 'features', 'schedule', 'classSize', 'certificate'
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
    lesson_id = serializers.UUIDField(source='lesson.id', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)
    
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
    
    class Meta:
        model = Question
        fields = [
            'id', 'quiz_id', 'quiz_title', 'question_text', 'question_type',
            'options', 'correct_answer', 'explanation', 'points', 'order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'quiz_id', 'quiz_title', 'created_at', 'updated_at']
    
    def get_options(self, obj):
        return obj.content.get('options', []) if obj.content else []
    
    def get_correct_answer(self, obj):
        return obj.content.get('correct_answer', '') if obj.content else ''


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
    
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'type', 'options', 'correct_answer',
            'explanation', 'points', 'order'
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
    
    def create(self, validated_data):
        # Extract virtual fields
        options = validated_data.pop('options', None)
        correct_answer = validated_data.pop('correct_answer', None)
        question_type = validated_data.pop('question_type', None)
        type_field = validated_data.pop('type', None)
        
        # Set the type field (either from question_type or type)
        if question_type:
            validated_data['type'] = question_type
        elif type_field:
            validated_data['type'] = type_field
        # For creates, type is required (validated above)
        
        # Create content dict
        content = {}
        if options is not None and options != []:
            content['options'] = options
        if correct_answer is not None and correct_answer != '':
            content['correct_answer'] = correct_answer
            
        validated_data['content'] = content
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Extract virtual fields
        options = validated_data.pop('options', None)
        correct_answer = validated_data.pop('correct_answer', None)
        question_type = validated_data.pop('question_type', None)
        type_field = validated_data.pop('type', None)
        
        # Set the type field (either from question_type or type)
        if question_type:
            validated_data['type'] = question_type
        elif type_field:
            validated_data['type'] = type_field
        # For updates, if no type provided, keep existing type (don't set validated_data['type'])
        
        # Update content dict
        content = instance.content or {}
        if options is not None and options != []:
            content['options'] = options
        if correct_answer is not None and correct_answer != '':
            content['correct_answer'] = correct_answer
            
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
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'instructions', 'submission_type', 'points', 'due_at', 'created_at'
        ]


# ===== CLASS SERIALIZERS =====

class ClassEventListSerializer(serializers.ModelSerializer):
    """Serializer for listing class events"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    project_platform_name = serializers.CharField(source='project_platform.display_name', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ClassEvent
        fields = [
            'id', 'title', 'description', 'event_type', 'start_time', 'end_time',
            'lesson_title', 'project_title', 'project_platform_name', 'lesson_type', 
            'duration_minutes', 'meeting_platform', 'meeting_link',
            'meeting_id', 'meeting_password', 'due_date', 'submission_type', 'created_at'
        ]


class ClassEventDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual class event"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    lesson_id = serializers.CharField(source='lesson.id', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    project_id = serializers.CharField(source='project.id', read_only=True)
    project_platform_name = serializers.CharField(source='project_platform.display_name', read_only=True)
    project_platform_id = serializers.CharField(source='project_platform.id', read_only=True)
    class_name = serializers.CharField(source='class_instance.name', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ClassEvent
        fields = [
            'id', 'title', 'description', 'event_type', 'start_time', 'end_time',
            'lesson', 'lesson_id', 'lesson_title', 'project', 'project_id', 'project_title',
            'project_platform', 'project_platform_id', 'project_platform_name',
            'lesson_type', 'class_name', 'duration_minutes',
            'meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password',
            'due_date', 'submission_type', 'created_at', 'updated_at'
        ]


class ClassEventCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating class events"""
    
    class Meta:
        model = ClassEvent
        fields = [
            'title', 'description', 'event_type', 'start_time', 'end_time', 
            'lesson', 'project', 'project_platform', 'project_title', 'due_date', 'submission_type',
            'lesson_type', 'meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password'
        ]
    
    def validate(self, data):
        """Validate event data"""
        event_type = data.get('event_type')
        
        # For non-project events, validate start_time and end_time
        if event_type != 'project':
            if data.get('start_time') and data.get('end_time'):
                if data['end_time'] <= data['start_time']:
                    raise serializers.ValidationError("End time must be after start time")
        
        # Validate lesson events
        if event_type == 'lesson' and not data.get('lesson'):
            raise serializers.ValidationError("Lesson events must have an associated lesson")
        
        # Validate project events
        if event_type == 'project':
            if not data.get('project'):
                raise serializers.ValidationError("Project is required for project events")
            if not data.get('project_platform'):
                raise serializers.ValidationError("Project platform is required for project events")
            
            # For project events, due_date is required instead of start_time/end_time
            if not data.get('due_date'):
                raise serializers.ValidationError("Due date is required for project events")
            
            # Validate submission_type if provided
            if data.get('submission_type'):
                valid_submission_types = ['link', 'image', 'video', 'audio', 'file', 'note', 'code', 'presentation']
                if data['submission_type'] not in valid_submission_types:
                    raise serializers.ValidationError(f"Invalid submission type. Must be one of: {', '.join(valid_submission_types)}")
        
        return data
    
    def create(self, validated_data):
        """Create a new class event"""
        # Get class_instance from context
        class_instance = self.context.get('class_instance')
        if not class_instance:
            raise serializers.ValidationError("Class instance is required")
        
        validated_data['class_instance'] = class_instance
        return super().create(validated_data)
