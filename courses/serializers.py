from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Course, Lesson, Quiz, Question, CourseEnrollment, LessonProgress, QuizAttempt, Note, CourseIntroduction, Class, ClassEvent

User = get_user_model()


# ===== ENROLLED STUDENT SERIALIZERS =====

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


class CourseEnrollmentStatsSerializer(serializers.Serializer):
    """Serializer for course enrollment statistics"""
    total_enrolled = serializers.IntegerField()
    active_students = serializers.IntegerField()
    completed_students = serializers.IntegerField()
    pending_payment = serializers.IntegerField()
    paid_students = serializers.IntegerField()
    average_progress = serializers.DecimalField(max_digits=5, decimal_places=2)


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
            'id', 'title', 'description', 'category', 'age_range', 'duration', 
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
    
    # Optional fields based on query parameters
    enrolled_students = serializers.SerializerMethodField()
    enrollment_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'long_description', 'category',
            'age_range', 'duration', 'level', 'price', 'features',
            'featured', 'popular', 'color', 'icon', 'max_students',
            'schedule', 'certificate', 'status', 'teacher_name', 'teacher_id',
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
            return CourseEnrollmentStatsSerializer(stats).data if stats else None
        return None


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating courses
    """
    class Meta:
        model = Course
        fields = [
            'title', 'description', 'long_description', 'category',
            'age_range', 'duration', 'level', 'price', 'features',
            'featured', 'popular', 'color', 'icon', 'max_students',
            'schedule', 'certificate', 'status'
        ]
    
    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
    
    def validate_max_students(self, value):
        if value < 1 or value > 50:
            raise serializers.ValidationError("Max students must be between 1 and 50")
        return value


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
            'age', 'duration', 'level', 'color', 'projects', 'price',
            'popular', 'featured', 'features', 'schedule', 'classSize', 'certificate'
        ]
    
    def get_projects(self, obj):
        # Generate project description based on course type
        return f"Build {obj.total_lessons} projects"
    
    def get_classSize(self, obj):
        return f"Max {obj.max_students} students"


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
        ).order_by('-created_at')[:6]  # Limit to 6 featured courses
        
        return {
            'courses': FrontendCourseSerializer(featured_courses, many=True).data
        }


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


class LessonDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed lesson view with all content
    """
    course_id = serializers.UUIDField(source='course.id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'course_id', 'course_title', 'title', 'description', 
            'type', 'duration', 'order', 'text_content', 'video_url', 'audio_url', 
            'live_class_date', 'live_class_status', 'content', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course_id', 'course_title', 'created_at', 'updated_at']


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
    question_type = serializers.CharField(source='type')
    options = serializers.ListField(required=False, allow_empty=True, allow_null=True)
    correct_answer = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'options', 'correct_answer',
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
        question_type = data.get('type')  # Note: using 'type' since it's the source
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


class CourseIntroductionSerializer(serializers.ModelSerializer):
    """
    Serializer for CourseIntroduction model
    """
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CourseIntroduction
        fields = [
            'id', 'overview', 'learning_objectives', 'prerequisites',
            'duration_weeks', 'max_students', 'sessions_per_week', 'total_projects',
            'value_propositions', 'reviews', 'average_rating', 'review_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_average_rating(self, obj):
        return obj.get_average_rating()
    
    def get_review_count(self, obj):
        return obj.get_review_count()


class CourseIntroductionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating CourseIntroduction
    """
    class Meta:
        model = CourseIntroduction
        fields = [
            'overview', 'learning_objectives', 'prerequisites',
            'duration_weeks', 'max_students', 'sessions_per_week', 'total_projects',
            'value_propositions'
        ]


# ===== CLASS SERIALIZERS =====

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
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'description', 'course_title', 'teacher_name',
            'max_capacity', 'student_count', 'is_full', 'available_spots',
            'schedule', 'is_active', 'created_at'
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
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'description', 'course_id', 'course_title', 
            'teacher_name', 'students', 'max_capacity', 'student_count', 
            'is_full', 'available_spots', 'schedule', 'meeting_link',
            'is_active', 'start_date', 'end_date', 'created_at', 'updated_at'
        ]


class ClassCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating classes"""
    student_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of student IDs to enroll in the class"
    )
    
    class Meta:
        model = Class
        fields = [
            'name', 'description', 'course', 'max_capacity', 
            'schedule', 'meeting_link', 'is_active', 
            'start_date', 'end_date', 'student_ids'
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
            class_instance = Class.objects.create(**validated_data)
            logger.info(f"Class created successfully: {class_instance.id}")
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
        student_ids = validated_data.pop('student_ids', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
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
        
        return instance
    
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


# ===== CLASS EVENT SERIALIZERS =====

class ClassEventListSerializer(serializers.ModelSerializer):
    """Serializer for listing class events"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ClassEvent
        fields = [
            'id', 'title', 'description', 'event_type', 'start_time', 'end_time',
            'lesson_title', 'duration_minutes', 'meeting_platform', 'meeting_link',
            'meeting_id', 'meeting_password', 'created_at'
        ]


class ClassEventDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual class event"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    lesson_id = serializers.CharField(source='lesson.id', read_only=True)
    class_name = serializers.CharField(source='class_instance.name', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ClassEvent
        fields = [
            'id', 'title', 'description', 'event_type', 'start_time', 'end_time',
            'lesson', 'lesson_id', 'lesson_title', 'class_name', 'duration_minutes',
            'meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password',
            'created_at', 'updated_at'
        ]


class ClassEventCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating class events"""
    
    class Meta:
        model = ClassEvent
        fields = [
            'title', 'description', 'event_type', 'start_time', 'end_time', 'lesson',
            'meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password'
        ]
    
    def validate(self, data):
        """Validate event data"""
        if data.get('start_time') and data.get('end_time'):
            if data['end_time'] <= data['start_time']:
                raise serializers.ValidationError("End time must be after start time")
        
        if data.get('event_type') == 'lesson' and not data.get('lesson'):
            raise serializers.ValidationError("Lesson events must have an associated lesson")
        
        return data
    
    def create(self, validated_data):
        """Create a new class event"""
        # Get class_instance from context
        class_instance = self.context.get('class_instance')
        if not class_instance:
            raise serializers.ValidationError("Class instance is required")
        
        validated_data['class_instance'] = class_instance
        return super().create(validated_data)
