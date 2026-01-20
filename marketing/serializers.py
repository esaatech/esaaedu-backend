from rest_framework import serializers
from .models import Program
from courses.serializers import CourseDetailSerializer
from courses.models import Course, Class, ClassSession


class ProgramSerializer(serializers.ModelSerializer):
    """
    Serializer for Program landing page API.
    Returns program details with enriched courses array (including billing and classes).
    """
    
    seo_url = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    
    class Meta:
        model = Program
        fields = [
            # Basic Information
            'id',
            'name',
            'slug',
            'description',
            
            # Hero Section
            'hero_media_url',
            'hero_media_type',
            'hero_title',
            'hero_subtitle',
            'hero_features',
            'hero_value_propositions',
            
            # Program Overview & Trust Strip
            'program_overview_features',
            'trust_strip_features',
            
            # Call to Action
            'cta_text',
            
            # Status
            'is_active',
            
            # Discount & Promotion
            'discount_enabled',
            'promotion_message',
            'promo_code',
            
            # Computed Fields
            'seo_url',
            'courses',
        ]
        # Note: 'category' field is NOT included - it's only used internally
        # to determine which courses to include. The API always returns a 'courses' array.
    
    def get_seo_url(self, obj):
        """Get full SEO URL for this program."""
        request = self.context.get('request')
        if request:
            domain = request.build_absolute_uri('/').rstrip('/')
        else:
            from django.conf import settings
            domain = getattr(settings, 'FRONTEND_URL', 'https://www.sbtyacedemy.com')
        
        return f"{domain}/{obj.slug}"
    
    def get_courses(self, obj):
        """
        Get enriched courses for this program.
        Each course includes full details, billing data, and available classes.
        """
        # Import here to avoid circular imports
        from courses.views import get_course_billing_data_helper
        
        # Get courses using the program's get_courses() method
        # This handles both category-based and ManyToMany-based programs
        courses = obj.get_courses()
        
        # Prefetch related data for efficiency
        courses = courses.select_related('teacher').prefetch_related(
            'reviews',
            'billing_product__prices'
        )
        
        enriched_courses = []
        
        for course in courses:
            try:
                # Get full course details using CourseDetailSerializer
                course_serializer = CourseDetailSerializer(course, context=self.context)
                course_data = course_serializer.data
                
                # Add billing data
                billing_data = get_course_billing_data_helper(course)
                if billing_data:
                    course_data['billing'] = billing_data
                else:
                    course_data['billing'] = None
                
                # Add available classes
                available_classes = self._get_available_classes(course)
                course_data['available_classes'] = available_classes
                
                enriched_courses.append(course_data)
                
            except Exception as e:
                # Log error but continue with other courses
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error enriching course {course.id} for program {obj.id}: {e}")
                continue
        
        return enriched_courses
    
    def _get_available_classes(self, course):
        """
        Get available classes for a course.
        Reuses the same logic as course_available_classes view.
        """
        try:
            # Get active classes for this course that have available spots
            classes = Class.objects.filter(
                course=course,
                is_active=True
            ).select_related('course', 'teacher').prefetch_related('students', 'sessions').order_by('name')
            
            # Filter classes with available spots
            available_classes = []
            for cls in classes:
                if cls.student_count < cls.max_capacity:
                    # Get session information
                    sessions_info = []
                    for session in cls.sessions.filter(is_active=True).order_by('session_number'):
                        sessions_info.append({
                            'session_number': session.session_number,
                            'day_of_week': session.day_of_week,
                            'day_name': dict(ClassSession.DAY_CHOICES)[session.day_of_week],
                            'start_time': session.start_time.strftime('%I:%M %p'),
                            'end_time': session.end_time.strftime('%I:%M %p'),
                            'formatted_schedule': session.formatted_schedule
                        })
                    
                    available_classes.append({
                        'id': str(cls.id),
                        'name': cls.name,
                        'description': cls.description,
                        'max_capacity': cls.max_capacity,
                        'student_count': cls.student_count,
                        'course_id': str(cls.course.id),
                        'course_title': cls.course.title,
                        'sessions': sessions_info,
                        'formatted_schedule': cls.formatted_schedule,
                        'session_count': cls.session_count,
                        'teacher_name': cls.teacher.get_full_name() or cls.teacher.email,
                        'available_spots': cls.available_spots
                    })
            
            return available_classes
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting available classes for course {course.id}: {e}")
            return []

