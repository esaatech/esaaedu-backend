from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Course, Lesson, Quiz, Question, CourseEnrollment, LessonProgress, QuizAttempt

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
