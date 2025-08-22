from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Course, Lesson, Quiz, Question, CourseEnrollment, LessonProgress, QuizAttempt, Note, CourseIntroduction

User = get_user_model()


class CourseListSerializer(serializers.ModelSerializer):
    """
    Serializer for course list view (minimal data for performance)
    """
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    total_lessons = serializers.ReadOnlyField()
    enrolled_students_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'category', 'age_range', 'duration', 
            'level', 'price', 'featured', 'popular', 'color', 'icon',
            'max_students', 'schedule', 'certificate', 'status',
            'teacher_name', 'total_lessons', 'enrolled_students_count',
            'created_at', 'updated_at'
        ]


class CourseDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed course view with all related data
    """
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    teacher_id = serializers.UUIDField(source='teacher.id', read_only=True)
    total_lessons = serializers.ReadOnlyField()
    total_duration_minutes = serializers.ReadOnlyField()
    enrolled_students_count = serializers.ReadOnlyField()
    is_featured_eligible = serializers.ReadOnlyField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'long_description', 'category',
            'age_range', 'duration', 'level', 'price', 'features',
            'featured', 'popular', 'color', 'icon', 'max_students',
            'schedule', 'certificate', 'status', 'teacher_name', 'teacher_id',
            'total_lessons', 'total_duration_minutes', 'enrolled_students_count',
            'is_featured_eligible', 'created_at', 'updated_at'
        ]


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
            'type', 'duration', 'order', 'content', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course_id', 'course_title', 'created_at', 'updated_at']


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating lessons
    """
    class Meta:
        model = Lesson
        fields = [
            'title', 'description', 'type', 'duration', 'order', 'content'
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
