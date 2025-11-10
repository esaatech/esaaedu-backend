from multiprocessing import parent_process
from django.shortcuts import get_object_or_404
from django.db import models
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from datetime import timedelta
from .models import Course, Lesson, Quiz, Question, Note, Class, ClassSession, QuizAttempt, CourseReview, LessonMaterial as LessonMaterialModel, BookPage, VideoMaterial
from student.models import EnrolledCourse
from django.db.models import F, Sum
from courses.models import ClassEvent
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateUpdateSerializer,
    FrontendCourseSerializer, FeaturedCoursesSerializer,
    LessonListSerializer, LessonDetailSerializer, LessonCreateUpdateSerializer,
    LessonReorderSerializer, QuizListSerializer, QuizDetailSerializer,
    QuizCreateUpdateSerializer, QuestionListSerializer, QuestionDetailSerializer,
    QuestionCreateUpdateSerializer, NoteSerializer, NoteCreateSerializer,

    ClassListSerializer, ClassDetailSerializer, ClassCreateUpdateSerializer,
    StudentBasicSerializer, TeacherStudentDetailSerializer, TeacherStudentSummarySerializer,
    CourseWithLessonsSerializer, LessonMaterialSerializer
)









class CoursesPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


def get_course_average_rating(course):
    """
    Calculate the average rating for a course from CourseReview model.
    Returns 0.0 if no reviews exist.
    """
    try:
        reviews = CourseReview.objects.filter(course=course)
        if not reviews.exists():
            return 0.0
        
        # Calculate average rating
        total_rating = sum(review.rating for review in reviews)
        average_rating = total_rating / reviews.count()
        
        # Round to 1 decimal place
        return round(average_rating, 1)
    except Exception as e:
        print(f"Error calculating rating for course {course.id}: {e}")
        return 0.0


# ===== PUBLIC ENDPOINTS (for frontend/students) =====

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def featured_courses(request):
    """
    Get featured courses for home page
    """
    try:
        serializer = FeaturedCoursesSerializer({})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch featured courses', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_courses_list(request):
    """
    Get all published courses for public viewing
    """
    try:
        courses = Course.objects.filter(status='published').select_related('teacher').order_by('-featured', '-created_at')
        
        # Apply pagination
        paginator = CoursesPagination()
        page = paginator.paginate_queryset(courses, request)
        
        if page is not None:
            serializer = FrontendCourseSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = FrontendCourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch courses', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def course_introduction_detail(request, course_id):
    """
    Get detailed course information for course details modal
    Now working directly with Course model (no separate CourseIntroduction)
    """
    try:
        course = get_object_or_404(Course, id=course_id, status='published')
        
        # Prefetch related reviews
        course = Course.objects.select_related('teacher').prefetch_related('reviews').get(id=course_id, status='published')
        
        serializer = CourseDetailSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch course introduction', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def course_available_classes(request, course_id):
    """
    Get available classes for a specific course (for student enrollment)
    """
    try:
        # Get the course
        course = get_object_or_404(Course, id=course_id, status='published')
        
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
                    'id': cls.id,
                    'name': cls.name,
                    'description': cls.description,
                    'max_capacity': cls.max_capacity,
                    'student_count': cls.student_count,
                    'course_id': cls.course.id,
                    'course_title': cls.course.title,
                    'sessions': sessions_info,
                    'formatted_schedule': cls.formatted_schedule,
                    'session_count': cls.session_count,
                    'teacher_name': cls.teacher.get_full_name() or cls.teacher.email,
                    'available_spots': cls.available_spots
                })
        
        return Response(available_classes, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch available classes', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===== TEACHER ENDPOINTS =====

@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def teacher_courses(request):
    """
    GET: List all courses created by the authenticated teacher
    POST: Create a new course
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            from django.db.models import Count, Q
            from student.models import EnrolledCourse
            
            # Get courses with enrollment counts
            courses = Course.objects.filter(teacher=request.user).annotate(
                enrolled_count=Count(
                    'student_enrollments',
                    distinct=True
                ),
                active_count=Count(
                    'student_enrollments',
                    filter=Q(student_enrollments__status='active'),
                    distinct=True
                )
            ).order_by('-created_at')
            
            serializer = CourseListSerializer(courses, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error in teacher_courses: {str(e)}")
            return Response(
                {'error': 'Failed to fetch courses', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            serializer = CourseCreateUpdateSerializer(data=request.data)
            if serializer.is_valid():
                course = serializer.save(teacher=request.user)
                
                # Create Stripe product and prices
                from .stripe_integration import create_stripe_product_for_course
                stripe_result = create_stripe_product_for_course(course)
                
                if not stripe_result['success']:
                    # If Stripe setup fails, delete the course and return error
                    course.delete()
                    return Response(
                        {'error': 'Course creation failed - billing setup error', 'details': stripe_result['error']},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                response_serializer = CourseDetailSerializer(course)
                response_data = response_serializer.data
                response_data['billing_setup'] = stripe_result
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to create course', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CourseCreationView(APIView):
    """
    Course Management CBV - Complete CRUD operations for courses
    GET: Retrieve default values for course creation form
    POST: Create a new course with validation and Stripe integration
    PUT: Update an existing course
    DELETE: Delete a course
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        GET: Retrieve default values for course creation
        Returns categories, settings, and form defaults
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access course creation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get course categories
            from .models import CourseCategory
            categories = CourseCategory.objects.all().order_by('name')
            categories_data = [
                {
                    'id': str(cat.id),
                    'name': cat.name,
                    'description': cat.description
                }
                for cat in categories
            ]
            
            # Get course settings
            from settings.models import CourseSettings
            settings = CourseSettings.get_settings()
            
            # Check price control permissions
            user_can_set_price = (
                settings.who_sets_price == 'teacher' or 
                settings.who_sets_price == 'both' or
                request.user.is_staff
            )
            
            # Form defaults based on settings
            form_defaults = {
                'max_students': settings.max_students_per_course,
                'duration_weeks': settings.default_course_duration_weeks,
                'enable_trial_period': settings.enable_trial_period,
                'trial_period_days': settings.trial_period_days,
                'price': 0.00,  # Default free course
                'is_free': True,  # Default to free
                'level': 'beginner',  # Default level
                'status': 'draft'  # Default status
            }
            
            # Default settings for response
            default_settings = {
                'monthly_price_markup_percentage': float(settings.monthly_price_markup_percentage),
                'max_students_per_course': settings.max_students_per_course,
                'default_course_duration_weeks': settings.default_course_duration_weeks,
                'enable_trial_period': settings.enable_trial_period,
                'trial_period_days': settings.trial_period_days,
                'who_sets_price': settings.who_sets_price
            }
            
            response_data = {
                'categories': categories_data,
                'default_settings': default_settings,
                'form_defaults': form_defaults,
                'price_control': settings.who_sets_price,
                'user_can_set_price': user_can_set_price,
                'user_context': {
                    'teacher_id': str(request.user.id),
                    'teacher_name': f"{request.user.first_name} {request.user.last_name}".strip(),
                    'teacher_email': request.user.email
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error in CourseCreationView GET: {str(e)}")
            return Response(
                {'error': 'Failed to fetch course creation defaults', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """
        POST: Create a new course
        Uses existing CourseCreateUpdateSerializer and Stripe integration
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can create courses'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check price control permissions
            from settings.models import CourseSettings
            settings = CourseSettings.get_settings()
            
            # If price control is admin-only and user is not staff, set default price values
            if settings.who_sets_price == 'admin' and not request.user.is_staff:
                # Set default values instead of removing fields
                request.data['price'] = 0  # Default to free
                request.data['is_free'] = True  # Default to free
            
            # Use existing serializer for validation and saving
            serializer = CourseCreateUpdateSerializer(data=request.data)
            
            if serializer.is_valid():
                course = serializer.save(teacher=request.user)
                
                # Create Stripe product and prices
                from .stripe_integration import create_stripe_product_for_course
                stripe_result = create_stripe_product_for_course(course)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            if not stripe_result['success']:
                # If Stripe setup fails, delete the course and return error
                course.delete()
                return Response(
                    {'error': 'Course creation failed - billing setup error', 'details': stripe_result['error']},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Prepare response data
            response_serializer = CourseDetailSerializer(course)
            response_data = response_serializer.data
            response_data['billing_setup'] = stripe_result
            response_data['message'] = 'Course created successfully'
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error in CourseCreationView POST: {str(e)}")
            return Response(
                {'error': 'Failed to create course', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, course_id=None):
        """
        PUT: Update an existing course
        Requires course_id in URL or request data
        """
        print(f"Request data: {request.data}")
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can update courses'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get course_id from URL parameter or request data
            if not course_id:
                course_id = request.data.get('course_id')
            
            if not course_id:
                return Response(
                    {'error': 'Course ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the course and check ownership
            try:
                course = Course.objects.get(id=course_id, teacher=request.user)
            except Course.DoesNotExist:
                return Response(
                    {'error': 'Course not found or you do not have permission to update it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check price control permissions
            from settings.models import CourseSettings
            settings = CourseSettings.get_settings()
            
            # If price control is admin-only and user is not staff, remove price from data
            if settings.who_sets_price == 'admin' and not request.user.is_staff:
                if 'price' in request.data:
                    request.data.pop('price')
                if 'is_free' in request.data:
                    request.data.pop('is_free')
            
            print(f"about to validate and update course")
            # Use existing serializer for validation and updating
            serializer = CourseCreateUpdateSerializer(course, data=request.data, partial=True)
            if serializer.is_valid():
                updated_course = serializer.save()
                
                # Update Stripe product if price changed
                if 'price' in request.data or 'is_free' in request.data:
                    from .stripe_integration import update_stripe_product_for_course
                    stripe_result = update_stripe_product_for_course(updated_course)
                    
                    if not stripe_result['success']:
                        return Response(
                            {'error': 'Course updated but Stripe sync failed', 'details': stripe_result['error']},
                            status=status.HTTP_206_PARTIAL_CONTENT
                        )
                
                # Prepare response data
                response_serializer = CourseDetailSerializer(updated_course)
                response_data = response_serializer.data
                response_data['message'] = 'Course updated successfully'
                
                return Response(response_data, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print(f"Error in CourseCreationView PUT: {str(e)}")
            return Response(
                {'error': 'Failed to update course', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, course_id=None):
        """
        DELETE: Delete a course
        Requires course_id in URL or request data
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can delete courses'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get course_id from URL parameter or request data
            if not course_id:
                course_id = request.data.get('course_id')
            
            if not course_id:
                return Response(
                    {'error': 'Course ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the course and check ownership
            try:
                course = Course.objects.get(id=course_id, teacher=request.user)
            except Course.DoesNotExist:
                return Response(
                    {'error': 'Course not found or you do not have permission to delete it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if course has enrollments
            from student.models import EnrolledCourse
            enrollment_count = EnrolledCourse.objects.filter(course=course).count()
            
            if enrollment_count > 0:
                return Response(
                    {'error': f'Cannot delete course with {enrollment_count} active enrollments. Please contact admin.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Store course data for response
            course_data = {
                'id': str(course.id),
                'title': course.title,
                'teacher': course.teacher.email
            }
            
            # Delete Stripe product if it exists
            if hasattr(course, 'stripe_product_id') and course.stripe_product_id:
                from .stripe_integration import delete_stripe_product
                stripe_result = delete_stripe_product(course.stripe_product_id)
                
                if not stripe_result['success']:
                    print(f"Warning: Stripe product deletion failed: {stripe_result['error']}")
            
            # Delete the course
            course.delete()
            
            return Response(
                {
                    'message': 'Course deleted successfully',
                    'deleted_course': course_data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            print(f"Error in CourseCreationView DELETE: {str(e)}")
            return Response(
                {'error': 'Failed to delete course', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_courses_to_teacher(request):
    """
    TEMPORARY DEBUG ENDPOINT: Assign all courses without a teacher to the current teacher
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Find courses without a teacher or assign all to current teacher
        courses_without_teacher = Course.objects.filter(teacher__isnull=True)
        updated_count = courses_without_teacher.update(teacher=request.user)
        
        # If no courses without teacher, assign all courses to current teacher (for debugging)
        if updated_count == 0:
            all_courses = Course.objects.all()
            updated_count = all_courses.update(teacher=request.user)
        
        return Response({
            'message': f'Assigned {updated_count} courses to {request.user.email}',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to assign courses', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def teacher_course_detail(request, course_id):
    """
    GET: Get detailed information about a specific course
    PUT: Update course details
    DELETE: Delete a course
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get the course and verify teacher ownership
    try:
        course = get_object_or_404(Course, id=course_id)
    except Course.DoesNotExist:
        return Response(
            {'error': 'Course not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage this course
    if course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can manage this course'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            serializer = CourseDetailSerializer(course)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch course details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        try:
            serializer = CourseCreateUpdateSerializer(course, data=request.data, partial=True)
            if serializer.is_valid():
                course = serializer.save()
                
                # Update Stripe product if it exists
                from .stripe_integration import update_stripe_product_for_course
                try:
                    stripe_result = update_stripe_product_for_course(course)
                    if not stripe_result['success']:
                        print(f"Stripe update failed for course {course.id}: {stripe_result['error']}")
                except Exception as e:
                    print(f"Stripe update error for course {course.id}: {str(e)}")
                
                response_serializer = CourseDetailSerializer(course)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update course', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            course_title = course.title
            
            # Deactivate Stripe product before deleting course
            from .stripe_integration import deactivate_stripe_product_for_course
            try:
                stripe_result = deactivate_stripe_product_for_course(course)
                if not stripe_result['success']:
                    print(f"Stripe deactivation failed for course {course.id}: {stripe_result['error']}")
            except Exception as e:
                print(f"Stripe deactivation error for course {course.id}: {str(e)}")
            
            course.delete()
            return Response(
                {'message': f'Course "{course_title}" deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete course', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===== LESSON MANAGEMENT ENDPOINTS =====

@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def course_lessons(request, course_id):
    """
    GET: List all lessons for a specific course
    POST: Create a new lesson for the course
    """
    # Get the course and verify teacher ownership
    try:
        course = get_object_or_404(Course, id=course_id)
    except Course.DoesNotExist:
        return Response(
            {'error': 'Course not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage lessons
    if course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can manage lessons'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            lessons = course.lessons.all().order_by('order')
            serializer = LessonListSerializer(lessons, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch lessons', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            serializer = LessonCreateUpdateSerializer(data=request.data)
            if serializer.is_valid():
                # Auto-assign order if not provided
                if 'order' not in serializer.validated_data:
                    max_order = course.lessons.aggregate(
                        max_order=models.Max('order')
                    )['max_order'] or 0
                    serializer.validated_data['order'] = max_order + 1
                
                lesson = serializer.save(course=course)
                response_serializer = LessonDetailSerializer(lesson)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to create lesson', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def lesson_detail(request, lesson_id):
    """
    GET: Get detailed lesson information
    PUT: Update lesson
    DELETE: Delete lesson
    """
    try:
        lesson = get_object_or_404(Lesson, id=lesson_id)
    except Lesson.DoesNotExist:
        return Response(
            {'error': 'Lesson not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage lessons
    if lesson.course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can manage this lesson'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            serializer = LessonDetailSerializer(lesson)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch lesson details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        try:
            serializer = LessonCreateUpdateSerializer(lesson, data=request.data, partial=True)
            if serializer.is_valid():
                lesson = serializer.save()
                response_serializer = LessonDetailSerializer(lesson)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update lesson', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            lesson.delete()
            return Response(
                {'message': 'Lesson deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete lesson', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def reorder_lessons(request, course_id):
    """
    PUT: Reorder lessons within a course
    """
    try:
        course = get_object_or_404(Course, id=course_id)
    except Course.DoesNotExist:
        return Response(
            {'error': 'Course not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can reorder lessons
    if course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can reorder lessons'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        serializer = LessonReorderSerializer(data=request.data)
        if serializer.is_valid():
            lessons_data = serializer.validated_data['lessons']
            
            # Step 1: Set all lessons to temporary negative orders to avoid constraint violations
            lessons_to_update = []
            for lesson_data in lessons_data:
                lesson_id = lesson_data['id']
                try:
                    lesson = course.lessons.get(id=lesson_id)
                    lessons_to_update.append((lesson, lesson_data['order']))
                    # Set temporary negative order to avoid constraint violations
                    lesson.order = -(lesson.id.int % 1000000)  # Use negative ID-based temp order
                    lesson.save()
                except Lesson.DoesNotExist:
                    return Response(
                        {'error': f'Lesson with id {lesson_id} not found in this course'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Step 2: Now set the actual desired orders
            for lesson, new_order in lessons_to_update:
                lesson.order = new_order
                lesson.save()
            
            # Return updated lessons
            lessons = course.lessons.all().order_by('order')
            response_serializer = LessonListSerializer(lessons, many=True)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Failed to reorder lessons', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===== QUIZ MANAGEMENT ENDPOINTS =====

@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def lesson_quiz(request, lesson_id):
    """
    GET: Get quiz for a specific lesson with questions (if exists)
    POST: Create a new quiz for the lesson
    
    This enhanced endpoint allows teachers to:
    - View complete quiz details including all questions and answers
    - Access quiz configuration and settings
    - Create new quizzes for lessons they teach
    
    Args:
        request: HTTP request object with authenticated teacher user
        lesson_id: UUID of the lesson to get/create quiz for
        
    Returns:
        GET: Complete quiz data with questions if quiz exists
        POST: Created quiz data if successful
        - 404 if lesson not found
        - 403 if user is not the course teacher
        - 200 with null quiz if lesson has no quiz
    """
    print(f"=== DEBUGGING lesson_quiz ===")
    print(f"Request method: {request.method}")
    print(f"Request user: {request.user}")
    print(f"Request lesson_id: {lesson_id}")
    
    # Get the lesson and verify teacher ownership
    try:
        lesson = get_object_or_404(Lesson, id=lesson_id)
        print(f"✅ Lesson found: {lesson.title} (ID: {lesson.id})")
        print(f"✅ Lesson course: {lesson.course.title}")
    except Lesson.DoesNotExist:
        print(f"❌ Lesson not found: {lesson_id}")
        return Response(
            {'error': 'Lesson not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage lesson quizzes
    if lesson.course.teacher != request.user:
        print(f"❌ User {request.user} is not the teacher of course {lesson.course.title}")
        return Response(
            {'error': 'Only the course teacher can manage lesson quizzes'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    print(f"✅ Teacher {request.user.get_full_name()} authorized for course {lesson.course.title}")
    
    if request.method == 'GET':
        try:
            # Check if quiz exists for this lesson
            try:
                quiz = Quiz.objects.get(lesson=lesson)
                print(f"✅ Quiz found: {quiz.title} (ID: {quiz.id})")
            except Quiz.DoesNotExist:
                print(f"ℹ️ No quiz found for lesson {lesson.title}")
                return Response(
                    {
                        'message': 'No quiz found for this lesson',
                        'quiz': None,
                        'lesson': {
                            'id': str(lesson.id),
                            'title': lesson.title,
                            'course': lesson.course.title
                        }
                    },
                    status=status.HTTP_200_OK
                )
            
            # Get quiz questions with proper ordering
            questions = quiz.questions.all().order_by('order')
            print(f"✅ Questions loaded: {questions.count()} questions found")
            
            # Prepare complete quiz data with questions
            quiz_data = {
                'id': str(quiz.id),
                'title': quiz.title,
                'description': quiz.description or '',
                'time_limit': quiz.time_limit,
                'passing_score': quiz.passing_score,
                'max_attempts': quiz.max_attempts,
                'show_correct_answers': quiz.show_correct_answers,
                'randomize_questions': quiz.randomize_questions,
                'total_points': quiz.total_points,
                'question_count': quiz.question_count,
                'created_at': quiz.created_at.isoformat() if quiz.created_at else None,
                'updated_at': quiz.updated_at.isoformat() if quiz.updated_at else None,
                'questions': []
            }
            
            # Add questions with their content
            for question in questions:
                question_data = {
                    'id': str(question.id),
                    'question_text': question.question_text,
                    'type': question.type,
                    'points': question.points,
                    'content': question.content,
                    'explanation': question.explanation or '',
                    'order': question.order,
                    'created_at': question.created_at.isoformat() if question.created_at else None,
                    'updated_at': question.updated_at.isoformat() if question.updated_at else None
                }
                quiz_data['questions'].append(question_data)
            
            # Add lesson context
            quiz_data['lesson'] = {
                'id': str(lesson.id),
                'title': lesson.title,
                'course': lesson.course.title,
                'type': lesson.type,
                'order': lesson.order
            }
            
            print(f"✅ Quiz data prepared successfully")
            print(f"📊 Quiz stats: {quiz_data['question_count']} questions, {quiz_data['total_points']} total points")
            
            return Response(quiz_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Error fetching quiz: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return Response(
                {'error': 'Failed to fetch quiz', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            # Check if quiz already exists
            if hasattr(lesson, 'quiz'):
                print(f"❌ Quiz already exists for lesson {lesson.title}")
                return Response(
                    {'error': 'Quiz already exists for this lesson'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"🎯 Creating new quiz for lesson {lesson.title}")
            serializer = QuizCreateUpdateSerializer(data=request.data)
            if serializer.is_valid():
                quiz = serializer.save(lesson=lesson)
                print(f"✅ Quiz created successfully: {quiz.title}")
                
                # Return enhanced quiz data (same format as GET)
                response_serializer = QuizDetailSerializer(quiz)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            else:
                print(f"❌ Quiz creation validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"❌ Error creating quiz: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return Response(
                {'error': 'Failed to create quiz', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def quiz_detail(request, quiz_id):
    """
    GET: Get detailed quiz information
    PUT: Update quiz
    DELETE: Delete quiz
    """
    try:
        quiz = get_object_or_404(Quiz, id=quiz_id)
    except Quiz.DoesNotExist:
        return Response(
            {'error': 'Quiz not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage this quiz
    if quiz.lesson.course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can manage this quiz'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            serializer = QuizDetailSerializer(quiz)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch quiz details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        try:
            serializer = QuizCreateUpdateSerializer(quiz, data=request.data, partial=True)
            if serializer.is_valid():
                quiz = serializer.save()
                response_serializer = QuizDetailSerializer(quiz)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update quiz', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            quiz.delete()
            return Response(
                {'message': 'Quiz deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete quiz', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def quiz_questions(request, quiz_id):
    """
    GET: List all questions for a specific quiz
    POST: Create a new question for the quiz
    """
    # Get the quiz and verify teacher ownership
    try:
        quiz = get_object_or_404(Quiz, id=quiz_id)
    except Quiz.DoesNotExist:
        return Response(
            {'error': 'Quiz not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage quiz questions
    if quiz.lesson.course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can manage quiz questions'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            questions = quiz.questions.all().order_by('order')
            serializer = QuestionListSerializer(questions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch questions', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            # Auto-assign order if not provided in request data
            data = request.data.copy()
            if 'order' not in data:
                max_order = quiz.questions.aggregate(
                    max_order=models.Max('order')
                )['max_order'] or 0
                data['order'] = max_order + 1
            
            serializer = QuestionCreateUpdateSerializer(data=data)
            if serializer.is_valid():
                question = serializer.save(quiz=quiz)
                response_serializer = QuestionDetailSerializer(question)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
            # Return detailed validation errors
            print(f"❌ Question validation errors: {serializer.errors}")
            print(f"📝 Request data: {request.data}")
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors,
                'received_data': request.data
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            print(f"🚨 Exception in quiz_questions POST: {str(e)}")
            print(f"🚨 Traceback: {traceback.format_exc()}")
            return Response(
                {'error': 'Failed to create question', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def question_detail(request, question_id):
    """
    GET: Get detailed question information
    PUT: Update question
    DELETE: Delete question
    """
    try:
        question = get_object_or_404(Question, id=question_id)
    except Question.DoesNotExist:
        return Response(
            {'error': 'Question not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage this question
    if question.quiz.lesson.course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can manage this question'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            serializer = QuestionDetailSerializer(question)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch question details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        try:
            serializer = QuestionCreateUpdateSerializer(question, data=request.data, partial=True)
            if serializer.is_valid():
                question = serializer.save()
                response_serializer = QuestionDetailSerializer(question)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update question', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            question.delete()
            return Response(
                {'message': 'Question deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete question', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def lesson_notes(request, lesson_id):
    """
    GET: Get all notes for a specific lesson
    POST: Create a new note for a specific lesson
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access lesson notes'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        lesson = get_object_or_404(Lesson, id=lesson_id)
        course = lesson.course
    except Lesson.DoesNotExist:
        return Response(
            {'error': 'Lesson not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Verify teacher owns the course
    if course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can access lesson notes'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            # Get notes specific to this lesson only
            notes = Note.objects.filter(lesson=lesson, teacher=request.user)
            serializer = NoteSerializer(notes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve notes', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            serializer = NoteCreateSerializer(
                data=request.data,
                context={'course': course, 'lesson': lesson}
            )
            if serializer.is_valid():
                # Always save note with the specific lesson
                note = serializer.save(
                    course=course,
                    lesson=lesson,
                    teacher=request.user
                )
                response_serializer = NoteSerializer(note)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to create note', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def lesson_note_detail(request, lesson_id, note_id):
    """
    GET: Get a specific note
    PUT: Update a note
    DELETE: Delete a note
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can manage notes'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        lesson = get_object_or_404(Lesson, id=lesson_id)
        note = get_object_or_404(Note, id=note_id, lesson=lesson)
        course = lesson.course
    except (Lesson.DoesNotExist, Note.DoesNotExist):
        return Response(
            {'error': 'Lesson or note not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Verify teacher owns the course and note
    if course.teacher != request.user or note.teacher != request.user:
        return Response(
            {'error': 'Only the note owner can manage this note'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            serializer = NoteSerializer(note)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve note', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        try:
            serializer = NoteCreateSerializer(
                note,
                data=request.data,
                context={'course': course, 'lesson': lesson},
                partial=True
            )
            if serializer.is_valid():
                note = serializer.save()
                response_serializer = NoteSerializer(note)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update note', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            note_title = note.title
            note.delete()
            return Response(
                {'message': f'Note "{note_title}" deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete note', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
def course_introduction(request, course_id):
    """
    GET/PUT: Get or update course introduction data (now working directly with Course model)
    No more separate CourseIntroduction table - all data is in the Course model
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access course introduction'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        course = get_object_or_404(Course, id=course_id)
    except Course.DoesNotExist:
        return Response(
            {'error': 'Course not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Verify teacher owns the course
    if course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can access course introduction'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        # Return course data with all introduction fields
        try:
            # Prefetch related reviews for the course
            course = Course.objects.select_related('teacher').prefetch_related('reviews').get(id=course_id)
            serializer = CourseDetailSerializer(course)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve course introduction', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        # Update course introduction fields directly on the Course model
        try:
            serializer = CourseCreateUpdateSerializer(
                course,
                data=request.data,
                partial=True
            )
            if serializer.is_valid():
                updated_course = serializer.save()
                
                # Return the updated course
                response_serializer = CourseDetailSerializer(updated_course)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': 'Failed to update course introduction', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===== CLASS MANAGEMENT VIEWS =====

@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def teacher_classes(request):
    """
    GET: List all classes for the authenticated teacher
    POST: Create a new class
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            classes = Class.objects.filter(teacher=request.user).select_related('course', 'teacher').prefetch_related('students', 'sessions').order_by('-created_at')
            serializer = ClassDetailSerializer(classes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch classes', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"🚀 VIEW: Received class creation request")
            logger.info(f"🚀 VIEW: Request data keys: {list(request.data.keys())}")
            logger.info(f"🚀 VIEW: Full request data: {request.data}")
            logger.info(f"🚀 VIEW: User: {request.user} (role: {request.user.role})")
            
            logger.info("🚀 VIEW: Creating serializer...")
            serializer = ClassCreateUpdateSerializer(
                data=request.data, 
                context={'request': request}
            )
            
            logger.info("🚀 VIEW: Starting serializer validation...")
            if serializer.is_valid():
                logger.info("🚀 VIEW: ✅ Serializer is valid, calling save()...")
                class_instance = serializer.save()
                logger.info(f"🚀 VIEW: ✅ Class saved successfully: {class_instance.id}")
                
                logger.info("🚀 VIEW: Creating response serializer...")
                response_serializer = ClassDetailSerializer(class_instance)
                logger.info("🚀 VIEW: ✅ Returning successful response")
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"🚀 VIEW: ❌ Serializer validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Exception in class creation: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': 'Failed to create class', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def teacher_class_detail(request, class_id):
    """
    GET: Retrieve class details
    PUT: Update class
    DELETE: Delete class
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        class_instance = get_object_or_404(
            Class.objects.select_related('course', 'teacher').prefetch_related('students', 'sessions'), 
            id=class_id, 
            teacher=request.user
        )
    except Exception:
        return Response(
            {'error': 'Class not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            serializer = ClassDetailSerializer(class_instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch class details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        try:
            serializer = ClassCreateUpdateSerializer(
                class_instance, 
                data=request.data, 
                context={'request': request},
                partial=True
            )
            if serializer.is_valid():
                updated_class = serializer.save()
                response_serializer = ClassDetailSerializer(updated_class)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update class', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            class_instance.delete()
            return Response(
                {'message': 'Class deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete class', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def course_enrolled_students(request, course_id):
    """
    Get all students enrolled in a specific course
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from student.models import EnrolledCourse
        from .serializers import EnrolledStudentSerializer
        
        # Verify the course belongs to the teacher
        course = get_object_or_404(Course, id=course_id, teacher=request.user)
        
        # Get all active enrollments for this course using the new EnrolledCourse model
        enrollments = EnrolledCourse.objects.filter(
            course=course,
            status='active'
        ).select_related('student_profile__user').order_by('enrollment_date')
        
        # Use the new EnrolledStudentSerializer for richer data
        serializer = EnrolledStudentSerializer(enrollments, many=True)
        
        return Response({
            'course_id': course_id,
            'course_title': course.title,
            'total_enrolled': enrollments.count(),
            'students': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Course.DoesNotExist:
        return Response(
            {'error': 'Course not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch enrolled students', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def teacher_students(request):
    """
    Get all students enrolled in any course taught by the authenticated teacher
    
    Query Parameters:
    - detail: 'true' for detailed view, 'false' for summary (default: false)
    - course: Filter by specific course ID
    - status: Filter by enrollment status (active, completed, dropped, etc.)
    - search: Search by student name or email
    - at_risk: 'true' to show only at-risk students
    - page: Page number for pagination
    - page_size: Number of results per page (default: 20, max: 100)
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from student.models import EnrolledCourse
        from django.db.models import Q, Prefetch
        from django.core.paginator import Paginator
        
        # Get query parameters
        detail_view = request.GET.get('detail', 'false').lower() == 'true'
        course_filter = request.GET.get('course')
        status_filter = request.GET.get('status')
        search_query = request.GET.get('search', '').strip()
        at_risk_only = request.GET.get('at_risk', 'false').lower() == 'true'
        page_num = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 20)), 100)
        
        # Base queryset - all enrollments for teacher's courses
        enrollments = EnrolledCourse.objects.filter(
            course__teacher=request.user
        ).select_related(
            'student_profile__user',
            'course',
            'current_lesson'
        ).prefetch_related(
            Prefetch('student_profile')
        )
        
        # Apply filters
        if course_filter:
            enrollments = enrollments.filter(course__id=course_filter)
        
        if status_filter:
            enrollments = enrollments.filter(status=status_filter)
        
        if search_query:
            enrollments = enrollments.filter(
                Q(student_profile__user__first_name__icontains=search_query) |
                Q(student_profile__user__last_name__icontains=search_query) |
                Q(student_profile__user__email__icontains=search_query) |
                Q(student_profile__child_first_name__icontains=search_query) |
                Q(student_profile__child_last_name__icontains=search_query)
            )
        
        # Filter for at-risk students
        if at_risk_only:
            # This will use the is_at_risk property from the model
            # We need to filter in Python since it's a property, not a DB field
            all_enrollments = list(enrollments)
            enrollments = [e for e in all_enrollments if e.is_at_risk]
            
            # Convert back to queryset-like structure for pagination
            from django.core.paginator import Paginator
            paginator = Paginator(enrollments, page_size)
            page_obj = paginator.get_page(page_num)
            enrollments_page = page_obj.object_list
            
            # Serialize the data
            if detail_view:
                serializer = TeacherStudentDetailSerializer(enrollments_page, many=True)
            else:
                serializer = TeacherStudentSummarySerializer(enrollments_page, many=True)
            
            return Response({
                'students': serializer.data,
                'pagination': {
                    'current_page': page_obj.number,
                    'total_pages': paginator.num_pages,
                    'total_students': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'page_size': page_size
                },
                'filters_applied': {
                    'course': course_filter,
                    'status': status_filter,
                    'search': search_query,
                    'at_risk_only': at_risk_only,
                    'detail_view': detail_view
                }
            }, status=status.HTTP_200_OK)
        
        # Regular pagination for non-at-risk filtering
        enrollments = enrollments.order_by('-enrollment_date', 'student_profile__user__first_name')
        
        # Apply pagination
        paginator = Paginator(enrollments, page_size)
        page_obj = paginator.get_page(page_num)
        
        # Serialize the data
        if detail_view:
            serializer = TeacherStudentDetailSerializer(page_obj.object_list, many=True)
        else:
            serializer = TeacherStudentSummarySerializer(page_obj.object_list, many=True)
        
        # Get summary statistics
        total_enrollments = enrollments.count()
        active_students = enrollments.filter(status='active').count()
        completed_students = enrollments.filter(status='completed').count()
        at_risk_count = sum(1 for e in enrollments if e.is_at_risk)
        
        return Response({
            'students': serializer.data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_students': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'page_size': page_size
            },
            'summary': {
                'total_enrollments': total_enrollments,
                'active_students': active_students,
                'completed_students': completed_students,
                'at_risk_students': at_risk_count,
                'unique_students': enrollments.values('student_profile__user').distinct().count()
            },
            'filters_applied': {
                'course': course_filter,
                'status': status_filter,
                'search': search_query,
                'at_risk_only': at_risk_only,
                'detail_view': detail_view
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch teacher students', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def teacher_students_master(request):
    """
    Consolidated endpoint that returns all teacher courses and students in a single call.
    This eliminates the need for multiple API calls on page load.
    
    Returns:
    - All courses taught by the teacher
    - All students enrolled in those courses
    - Basic student information for the master panel
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from student.models import EnrolledCourse
        from django.db.models import Q, Prefetch
        
        # Get all courses taught by the teacher
        courses = Course.objects.filter(teacher=request.user).annotate(
            enrolled_count=models.Count('student_enrollments', distinct=True),
            active_count=models.Count(
                'student_enrollments',
                filter=Q(student_enrollments__status='active'),
                distinct=True
            )
        ).order_by('-created_at')
        
        # Get all enrollments for teacher's courses
        enrollments = EnrolledCourse.objects.filter(
            course__teacher=request.user
        ).select_related(
            'student_profile__user',
            'course',
            'current_lesson'
        ).order_by('-enrollment_date', 'student_profile__user__first_name')
        
        # Prepare courses data
        courses_data = []
        for course in courses:
            course_data = {
                'id': str(course.id),
                'title': course.title,
                'description': course.description,
                'category': course.category,
                'difficulty_level': getattr(course, 'difficulty_level', 'beginner'),
                'status': course.status,
                'created_at': course.created_at.isoformat() if course.created_at else None,
                'enrolled_count': course.enrolled_count,
                'active_count': course.active_count,
                'total_lessons': course.lessons.count()
            }
            courses_data.append(course_data)
        
        # Prepare students data (summary view for master panel)
        students_data = []
        for enrollment in enrollments:
            student_user = enrollment.student_profile.user
            
            # Get assignment summary for this student (count only submissions that are submitted and ungraded FOR THIS SPECIFIC COURSE)
            from courses.models import AssignmentSubmission
            
            # Filter by student AND course (through the assignment's lesson)
            ungraded_submissions = AssignmentSubmission.objects.filter(
                student=student_user,
                assignment__lesson__course=enrollment.course,
                status='submitted',
                is_graded=False
            )
            
            assignment_count = ungraded_submissions.count()
            
            student_data = {
                'id': str(student_user.id),
                'student_profile_id': str(enrollment.student_profile.id),
                'first_name': student_user.first_name,
                'last_name': student_user.last_name,
                'email': student_user.email,
                'child_first_name': enrollment.student_profile.child_first_name,
                'child_last_name': enrollment.student_profile.child_last_name,
                'grade_level': enrollment.student_profile.grade_level,
                'enrollment_date': enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None,
                'status': enrollment.status,
                'progress_percentage': float(enrollment.progress_percentage),
                'overall_grade': enrollment.overall_grade,
                'average_quiz_score': float(enrollment.average_quiz_score) if enrollment.average_quiz_score else None,
                'is_at_risk': enrollment.is_at_risk,
                'course_id': str(enrollment.course.id),
                'course_title': enrollment.course.title,
                'current_lesson_id': str(enrollment.current_lesson.id) if enrollment.current_lesson else None,
                'current_lesson_title': enrollment.current_lesson.title if enrollment.current_lesson else None,
                'completed_lessons_count': enrollment.completed_lessons_count,
                'total_lessons_count': enrollment.total_lessons_count,
                'last_accessed': enrollment.last_accessed.isoformat() if enrollment.last_accessed else None,
                'pending_assignment_count': assignment_count  # Add assignment count
            }
            students_data.append(student_data)
        
        # Get summary statistics
        total_enrollments = enrollments.count()
        active_students = enrollments.filter(status='active').count()
        completed_students = enrollments.filter(status='completed').count()
        at_risk_count = sum(1 for e in enrollments if e.is_at_risk)
        unique_students = enrollments.values('student_profile__user').distinct().count()
        
        response_data = {
            'courses': courses_data,
            'students': students_data,
            'summary': {
                'total_courses': len(courses_data),
                'total_enrollments': total_enrollments,
                'active_students': active_students,
                'completed_students': completed_students,
                'at_risk_students': at_risk_count,
                'unique_students': unique_students
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch teacher students master data', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def class_events(request, class_id):
    """
    GET: Get all events for a specific class
    POST: Create a new event for a class
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from .models import ClassEvent, Project, ProjectPlatform, Lesson
        from .serializers import ClassEventListSerializer, ClassEventCreateUpdateSerializer, ClassEventDetailSerializer, ProjectListSerializer, ProjectPlatformSerializer, LessonListSerializer
        
        # Verify the class belongs to the teacher
        class_instance = get_object_or_404(Class, id=class_id, teacher=request.user)
        
        if request.method == 'GET':
            events = ClassEvent.objects.filter(class_instance=class_instance).select_related(
                'lesson', 'project', 'project_platform'
            ).order_by('start_time')
            serializer = ClassEventListSerializer(events, many=True)
            
            # Get available projects for this course
            available_projects = Project.objects.filter(course=class_instance.course)
            projects_serializer = ProjectListSerializer(available_projects, many=True)
            
            # Get available platforms
            available_platforms = ProjectPlatform.objects.filter(is_active=True)
            platforms_serializer = ProjectPlatformSerializer(available_platforms, many=True)
            
            # Get available lessons for this course
            available_lessons = Lesson.objects.filter(course=class_instance.course).order_by('order')
            lessons_serializer = LessonListSerializer(available_lessons, many=True)
            
            return Response({
                'class_id': class_id,
                'class_name': class_instance.name,
                'course_id': str(class_instance.course.id),
                'course_name': class_instance.course.title,
                'events': serializer.data,
                'available_projects': projects_serializer.data,
                'available_platforms': platforms_serializer.data,
                'available_lessons': lessons_serializer.data
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            serializer = ClassEventCreateUpdateSerializer(
                data=request.data,
                context={'class_instance': class_instance}
            )
            if serializer.is_valid():
                event = serializer.save()
                response_serializer = ClassEventDetailSerializer(event)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Class.DoesNotExist:
        return Response(
            {'error': 'Class not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to process class events', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def class_event_detail(request, class_id, event_id):
    """
    GET: Get details of a specific event
    PUT: Update an event
    DELETE: Delete an event
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from .models import ClassEvent
        from .serializers import ClassEventDetailSerializer, ClassEventCreateUpdateSerializer
        
        # Verify the class belongs to the teacher
        class_instance = get_object_or_404(Class, id=class_id, teacher=request.user)
        
        # Get the specific event
        event = get_object_or_404(ClassEvent, id=event_id, class_instance=class_instance)
        
        if request.method == 'GET':
            serializer = ClassEventDetailSerializer(event)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        elif request.method == 'PUT':
            serializer = ClassEventCreateUpdateSerializer(
                event,
                data=request.data,
                context={'class_instance': class_instance},
                partial=True
            )
            if serializer.is_valid():
                updated_event = serializer.save()
                response_serializer = ClassEventDetailSerializer(updated_event)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            event.delete()
            return Response(
                {'message': 'Event deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
    
    except Class.DoesNotExist:
        return Response(
            {'error': 'Class not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except ClassEvent.DoesNotExist:
        return Response(
            {'error': 'Event not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to process event', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===== QUIZ GRADING ENDPOINTS =====

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def teacher_quiz_submissions(request):
    """
    Get all quiz submissions (attempts) for the teacher's courses
    Organized by lessons with ungraded and graded submissions
    """
    try:
        # Ensure user is a teacher
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can access quiz submissions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get teacher's courses
        teacher_courses = Course.objects.filter(teacher=request.user)
        
        # Check if filtering by specific student
        student_id = request.GET.get('student_id')
        student_filter = {}
        if student_id:
            student_filter['quiz__attempts__student_id'] = student_id
        
        # Get all lessons with quizzes for teacher's courses
        lessons_with_quizzes = Lesson.objects.filter(
            course__in=teacher_courses,
            quiz__isnull=False,
            **student_filter
        ).select_related('quiz', 'course').prefetch_related('quiz__attempts__student').distinct()
        
        lessons_data = []
        
        for lesson in lessons_with_quizzes:
            quiz = lesson.quiz
            
            # Get all quiz attempts for this quiz
            quiz_attempts_filter = {
                'quiz': quiz,
                'completed_at__isnull': False  # Only completed attempts
            }
            
            # Filter by student if specified
            if student_id:
                quiz_attempts_filter['student_id'] = student_id
                
            quiz_attempts = QuizAttempt.objects.filter(
                **quiz_attempts_filter
            ).select_related('student', 'enrollment').order_by('-completed_at')
            
            # Separate graded and ungraded attempts (using consolidated model)
            ungraded_attempts = []
            graded_attempts = []
            
            for attempt in quiz_attempts:
                # Check if this attempt has been graded (auto-graded or teacher-enhanced)
                is_graded = attempt.score is not None  # Auto-graded if score exists
                is_teacher_enhanced = attempt.is_teacher_graded  # Teacher enhanced if flag is True
                
                attempt_data = {
                    'id': attempt.id,
                    'student_id': attempt.student.id,
                    'student_name': attempt.student.get_full_name(),
                    'student_email': attempt.student.email,
                    'submitted_at': attempt.completed_at,
                    'time_spent': None,  # Calculate from started_at to completed_at
                    'score': attempt.final_score,  # Use computed property
                    'points_earned': attempt.final_points_earned,  # Use computed property
                    'passed': attempt.passed,
                    'answers': attempt.answers,
                    'attempt_number': attempt.attempt_number,
                    'is_teacher_enhanced': is_teacher_enhanced
                }
                
                # Calculate time spent
                if attempt.started_at and attempt.completed_at:
                    time_diff = attempt.completed_at - attempt.started_at
                    attempt_data['time_spent'] = int(time_diff.total_seconds() / 60)  # minutes
                
                if is_graded:
                    # Get the grade details from consolidated model
                    if is_teacher_enhanced and attempt.teacher_grade_data:
                        grade_data = attempt.teacher_grade_data
                        attempt_data.update({
                            'teacher_grade': {
                                'percentage': float(grade_data.get('percentage', attempt.score)),
                                'letter_grade': grade_data.get('letter_grade', None),
                                'points_earned': float(grade_data.get('points_earned', attempt.points_earned)),
                                'points_possible': float(grade_data.get('points_possible', attempt.quiz.total_points)),
                                'teacher_comments': grade_data.get('teacher_comments', ''),
                                'graded_date': grade_data.get('graded_date', attempt.completed_at.isoformat()),
                                'graded_by': grade_data.get('graded_by', 'Auto-graded')
                            }
                        })
                    else:
                        # Auto-graded only
                        attempt_data.update({
                            'teacher_grade': {
                                'percentage': float(attempt.score),
                                'letter_grade': None,
                                'points_earned': float(attempt.points_earned),
                                'points_possible': float(attempt.quiz.total_points),
                                'teacher_comments': '',
                                'graded_date': attempt.completed_at.isoformat(),
                                'graded_by': 'Auto-graded'
                            }
                        })
                    graded_attempts.append(attempt_data)
                else:
                    ungraded_attempts.append(attempt_data)
            
            # Only include lessons that have quiz attempts
            if ungraded_attempts or graded_attempts:
                lesson_data = {
                    'id': lesson.id,
                    'title': lesson.title,
                    'description': lesson.description,
                    'course_id': lesson.course.id,
                    'course_title': lesson.course.title,
                    'quiz': {
                        'id': quiz.id,
                        'title': quiz.title,
                        'description': quiz.description,
                        'time_limit': quiz.time_limit,
                        'passing_score': quiz.passing_score,
                        'total_points': quiz.total_points,
                        'question_count': quiz.question_count,
                        'questions': []  # We'll populate this when grading
                    },
                    'ungraded_attempts': ungraded_attempts,
                    'graded_attempts': graded_attempts,
                    'total_attempts': len(ungraded_attempts) + len(graded_attempts)
                }
                lessons_data.append(lesson_data)
        
        # Organize response
        response_data = {
            'lessons': lessons_data,
            'summary': {
                'total_lessons': len(lessons_data),
                'total_ungraded': sum(len(lesson['ungraded_attempts']) for lesson in lessons_data),
                'total_graded': sum(len(lesson['graded_attempts']) for lesson in lessons_data),
                'teacher_courses': [{'id': course.id, 'title': course.title} for course in teacher_courses]
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch quiz submissions', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def quiz_attempt_details(request, attempt_id):
    """
    Get detailed quiz attempt with questions and student answers for grading
    """
    try:
        # Ensure user is a teacher
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can access quiz attempts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the quiz attempt
        attempt = get_object_or_404(
            QuizAttempt.objects.select_related('quiz', 'student', 'enrollment'),
            id=attempt_id,
            quiz__lesson__course__teacher=request.user  # Ensure teacher owns the course
        )
        
        # Get quiz questions
        questions = Question.objects.filter(quiz=attempt.quiz).order_by('order')
        
        # Check if this attempt has been graded (using consolidated model)
        grade = None
        graded_questions_dict = {}
        
        # Check if teacher has enhanced the grading
        if attempt.is_teacher_graded and attempt.teacher_grade_data:
            grade = attempt.teacher_grade_data
            # Convert graded_questions list to dict for easy lookup
            for gq in grade.get('graded_questions', []):
                graded_questions_dict[str(gq.get('question_id'))] = gq
        elif attempt.score is not None:
            # Auto-graded quiz - create a grade object from the attempt data
            grade = {
                'percentage': attempt.score,
                'points_earned': attempt.points_earned,
                'points_possible': attempt.quiz.total_points,
                'teacher_comments': '',
                'private_notes': '',
                'graded_date': attempt.completed_at.isoformat(),
                'graded_by': 'Auto-graded',
                'graded_questions': []
            }
        
        # Prepare questions data with student answers
        questions_data = []
        for question in questions:
            question_data = {
                'id': question.id,
                'type': question.type,
                'question': question.question_text,  # Fixed field name
                'points': question.points,
                'order': question.order,
                'options': question.content.get('options', []) if question.type in ['multiple_choice', 'matching', 'ordering'] else None,
                'correct_answer': question.content.get('correct_answer', None),  # Get from content JSON field
                'explanation': question.explanation,
                'student_answer': attempt.answers.get(str(question.id), None) if attempt.answers else None
            }
            
            # Add grading information if available
            question_id_str = str(question.id)
            if question_id_str in graded_questions_dict:
                graded_question = graded_questions_dict[question_id_str]
                question_data.update({
                    'teacher_grade': {
                        'is_correct': graded_question.get('is_correct', False),
                        'teacher_feedback': graded_question.get('teacher_feedback', ''),
                        'points_earned': graded_question.get('points_earned', 0),
                        'points_possible': graded_question.get('points_possible', question.points)
                    }
                })
            else:
                question_data['teacher_grade'] = None
            questions_data.append(question_data)
        
        # Prepare response
        response_data = {
            'attempt': {
                'id': attempt.id,
                'student_name': attempt.student.get_full_name(),
                'student_email': attempt.student.email,
                'submitted_at': attempt.completed_at,
                'time_spent': None,
                'score': attempt.score,
                'points_earned': attempt.points_earned,
                'passed': attempt.passed,
                'attempt_number': attempt.attempt_number
            },
            'quiz': {
                'id': attempt.quiz.id,
                'title': attempt.quiz.title,
                'description': attempt.quiz.description,
                'time_limit': attempt.quiz.time_limit,
                'passing_score': attempt.quiz.passing_score,
                'total_points': attempt.quiz.total_points,
                'question_count': questions.count()
            },
            'lesson': {
                'id': attempt.quiz.lesson.id,
                'title': attempt.quiz.lesson.title,
                'course_title': attempt.quiz.lesson.course.title
            },
            'questions': questions_data,
            'grade': {
                'id': str(attempt.id) if grade else None,
                'percentage': float(grade.get('percentage', 0)) if grade else None,
                'letter_grade': grade.get('letter_grade', None) if grade else None,
                'teacher_comments': grade.get('teacher_comments', '') if grade else '',
                'private_notes': grade.get('private_notes', '') if grade else '',
                'graded_date': grade.get('graded_date', None) if grade else None,
                'graded_by': grade.get('graded_by', None) if grade else None,
                'is_graded': grade is not None,
                'is_teacher_graded': attempt.is_teacher_graded
            }
        }
        
        # Calculate time spent
        if attempt.started_at and attempt.completed_at:
            time_diff = attempt.completed_at - attempt.started_at
            response_data['attempt']['time_spent'] = int(time_diff.total_seconds() / 60)  # minutes
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch quiz attempt details', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def save_quiz_grade(request, attempt_id):
    """
    Save teacher's grading for a quiz attempt
    """
    try:
        # Ensure user is a teacher
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can grade quizzes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the quiz attempt
        attempt = get_object_or_404(
            QuizAttempt.objects.select_related('quiz', 'student', 'enrollment'),
            id=attempt_id,
            quiz__lesson__course__teacher=request.user  # Ensure teacher owns the course
        )
        
        # Get request data
        data = request.data
        required_fields = ['percentage', 'points_earned', 'points_possible']
        
        for field in required_fields:
            if field not in data:
                return Response(
                    {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate graded_questions if provided
        graded_questions = data.get('graded_questions', [])
        if graded_questions and not isinstance(graded_questions, list):
            return Response(
                {'error': 'graded_questions must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update the quiz attempt with teacher grading data
        attempt.is_teacher_graded = True
        attempt.teacher_grade_data = {
                'points_earned': data['points_earned'],
                'points_possible': data['points_possible'],
                'percentage': data['percentage'],
                'teacher_comments': data.get('teacher_comments', ''),
                'private_notes': data.get('private_notes', ''),
            'graded_questions': graded_questions,
            'graded_by': request.user.email,
            'graded_date': timezone.now().isoformat()
        }
        
        # Add to grading history
        attempt.grading_history.append({
            'date': timezone.now().isoformat(),
            'action': 'teacher_graded',
            'graded_by': request.user.email,
            'percentage': data['percentage'],
            'points_earned': data['points_earned'],
            'teacher_comments': data.get('teacher_comments', ''),
            'private_notes': data.get('private_notes', '')
        })
        
        attempt.save()
        
        # Update enrollment progress
        try:
            enrollment = attempt.enrollment
            enrollment.update_progress()
        except Exception as progress_error:
            print(f"Warning: Failed to update enrollment progress: {progress_error}")
            # Continue execution - this is not critical
        
        response_data = {
            'message': 'Quiz graded successfully',
            'grade': {
                'id': str(attempt.id),
                'percentage': float(data['percentage']),
                'points_earned': float(data['points_earned']),
                'points_possible': float(data['points_possible']),
                'teacher_comments': data.get('teacher_comments', ''),
                'graded_date': timezone.now().isoformat(),
                'is_teacher_graded': True
            },
            'attempt': {
                'id': str(attempt.id),
                'score': float(attempt.final_score),
                'points_earned': attempt.final_points_earned,
                'passed': attempt.passed,
                'is_teacher_graded': attempt.is_teacher_graded
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': 'Failed to save quiz grade', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===== STUDENT ENROLLMENT ENDPOINTS =====

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def student_enrolled_courses(request):
    """
    Get all courses the current student is enrolled in
    """
   
    
    try:
       
        # Get student profile
        student_profile = getattr(request.user, 'student_profile', None)
        
        
        if not student_profile:
            
            return Response({
                'enrolled_courses': [],
                'message': 'Student profile not found'
            }, status=status.HTTP_200_OK)
        
      
        # Get enrolled courses
        enrolled_courses = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            status__in=['active', 'completed']
        ).select_related('course', 'current_lesson').order_by('-enrollment_date')
        
     
        
        courses_data = []
        for i, enrollment in enumerate(enrolled_courses):
            course = enrollment.course
            
            
            try:
                # Get course image (fallback to placeholder)
                
                course_image = getattr(course, 'image', None)
                if course_image:
                    image_url = course_image.url if hasattr(course_image, 'url') else str(course_image)
                else:
                    image_url = "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=300&h=200&fit=crop"
                
                
                # Calculate next lesson
                print(f"Calculating next lesson...")
                next_lesson = "Course Completed!" if enrollment.status == 'completed' else (
                    enrollment.current_lesson.title if enrollment.current_lesson else "Start Learning"
                )
                
                actual_total_lessons = course.lessons.count()
                
                
                # Debug enrollment data
                
                
                # Get instructor name
                
                instructor_name = "Little Learners Tech"
                if hasattr(course, 'instructor') and course.instructor:
                    instructor_name = course.instructor.get_full_name() or course.instructor.email
                print(f"Instructor: {instructor_name}")
                
                print(f"Building course data...")
                course_data = {
                    'id': str(course.id),  # Ensure it's a string
                    'title': course.title,
                    'description': course.description,
                    'instructor': instructor_name,
                    'image': image_url,
                    'icon': course.icon,  # Add icon field
                    'progress': float(enrollment.progress_percentage),
                    'total_lessons': actual_total_lessons,  # Use actual count, not computed property
                    'completed_lessons': enrollment.completed_lessons_count,  # Use actual enrollment data
                    'next_lesson': next_lesson,
                    'status': enrollment.status,
                    'enrollment_date': enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None,
                    'last_accessed': enrollment.last_accessed.isoformat() if enrollment.last_accessed else None,
                    'overall_grade': enrollment.overall_grade,
                    'average_quiz_score': float(enrollment.average_quiz_score) if enrollment.average_quiz_score else None,
                    'difficulty': getattr(course, 'difficulty_level', 'beginner'),
                    'category': course.category,
                    'rating': get_course_average_rating(course),  # Calculate actual rating from reviews
                }
                courses_data.append(course_data)
                
                
            except Exception as course_error:
                print(f"ERROR processing course {course.title}: {course_error}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"Step 4: Returning response with {len(courses_data)} courses")
        response_data = {
            'enrolled_courses': courses_data,
            'total_enrolled': len(courses_data)
        }
        print(f"Response data: {response_data}")
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"CRITICAL ERROR in student_enrolled_courses: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': 'Failed to fetch enrolled courses', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def student_course_recommendations(request):
    """
    Get course recommendations for the current student
    """
    
    
    try:
        print("Step 1: Getting student profile...")
        # Get student profile
        student_profile = getattr(request.user, 'student_profile', None)
        print(f"Student profile found: {student_profile}")
        
        print("Step 2: Getting enrolled course IDs to exclude...")
        # Get already enrolled course IDs to exclude
        enrolled_course_ids = []
        if student_profile:
            enrolled_course_ids = list(
                EnrolledCourse.objects.filter(
                    student_profile=student_profile,
                    status__in=['active', 'completed']
                ).values_list('course_id', flat=True)
            )
        print(f"Enrolled course IDs to exclude: {enrolled_course_ids}")
        
        print("Step 3: Querying recommended courses...")
        # Get recommended courses (featured + not enrolled)
        recommended_courses = Course.objects.filter(
            status='published',  # Use status instead of is_published
            featured=True        # Use featured instead of is_featured
        ).exclude(id__in=enrolled_course_ids)[:6]
        
        print(f"Found {recommended_courses.count()} recommended courses")
        
        courses_data = []
        for i, course in enumerate(recommended_courses):
            print(f"Step 4.{i+1}: Processing course {course.title}...")
            
            try:
                # Get course image
                print(f"Getting course image...")
                course_image = getattr(course, 'image', None)
                if course_image:
                    image_url = course_image.url if hasattr(course_image, 'url') else str(course_image)
                else:
                    image_url = "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=300&h=200&fit=crop"
                print(f"Image URL: {image_url}")
                
                # Get instructor name
                print(f"Getting instructor name...")
                instructor_name = "Little Learners Tech"
                if hasattr(course, 'teacher') and course.teacher:  # Use 'teacher' instead of 'instructor'
                    instructor_name = course.teacher.get_full_name() or course.teacher.email
                print(f"Instructor: {instructor_name}")
                
                # Get course details
                print(f"Getting course details...")
                total_lessons = getattr(course, 'total_lessons', 12)
                duration = getattr(course, 'duration', '8 weeks')
                max_students = getattr(course, 'max_students', 12)
                difficulty = getattr(course, 'level', 'beginner')  # Use 'level' instead of 'difficulty_level'
                
                print(f"Course details - Lessons: {total_lessons}, Duration: {duration}, Max students: {max_students}")
                
                print(f"Building course data...")
                course_data = {
                    'id': str(course.id),
                    'uuid': str(course.id),
                    'title': course.title,
                    'description': course.description,
                    'instructor': instructor_name,
                    'image': image_url,
                    'icon': course.icon,  # Add icon field
                    'total_lessons': total_lessons,
                    'duration': duration,
                    'max_students': max_students,
                    'difficulty': difficulty,
                    'category': course.category,
                    'rating': get_course_average_rating(course),  # Calculate actual rating from reviews
                    'price': "Free" if not course.price or course.price == 0 else f"${course.price}",
                    'enrolled_students': 0,  # Can be calculated from enrollments
                }
                courses_data.append(course_data)
                
                
            except Exception as course_error:
                print(f"ERROR processing course {course.title}: {course_error}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"Step 5: Returning response with {len(courses_data)} courses")
        response_data = {
            'recommended_courses': courses_data,
            'total_recommendations': len(courses_data)
        }
        print(f"Response data: {response_data}")
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"CRITICAL ERROR in student_course_recommendations: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': 'Failed to fetch course recommendations', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def student_enroll_course(request, course_id):
    """
    Enroll the current student in a course
    """
    
    
    try:
        # Get class ID from request (course_id is now from URL)
        class_id = request.data.get('class_id')  # Optional for now
        
        print(f"Step 1: Getting student profile...")
        # Get student profile
        student_profile = getattr(request.user, 'student_profile', None)
        if not student_profile:
            return Response(
                {'error': 'Student profile not found. Please complete your profile setup.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"Step 2: Getting course...")
        # Get course using course_id from URL
        try:
            course = Course.objects.get(id=course_id, status='published')
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found or not available for enrollment'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        print(f"Step 3: Checking existing enrollment...")
        # Check if already enrolled
        existing_enrollment = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course=course
        ).first()
        
        if existing_enrollment:
            if existing_enrollment.status in ['active', 'completed']:
                return Response(
                    {'error': 'You are already enrolled in this course'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # Reactivate dropped/paused enrollment
                existing_enrollment.status = 'active'
                existing_enrollment.save()
                print(f"Reactivated existing enrollment")
        else:
            print(f"Step 4: Creating new enrollment...")
            # Create new enrollment
            existing_enrollment = EnrolledCourse.objects.create(
                student_profile=student_profile,
                course=course,
                status='active',
                enrolled_by=request.user,
                payment_status='free',  # Default to free for now
                total_lessons_count=course.total_lessons or 0
            )
            print(f"Created new enrollment: {existing_enrollment.id}")
            
            # If class is selected, add student to the class
            if class_id:
                try:
                    selected_class = Class.objects.get(id=class_id, course=course, is_active=True)
                    if selected_class.student_count < selected_class.max_capacity:
                        selected_class.students.add(request.user)
                        print(f"Added student to class: {selected_class.name}")
                    else:
                        print(f"Warning: Class {selected_class.name} is full, student not added to class")
                except Class.DoesNotExist:
                    print(f"Warning: Selected class {class_id} not found or not active")
                except Exception as e:
                    print(f"Warning: Failed to add student to class: {e}")
        
        print(f"Step 5: Preparing response...")
        # Return enrollment details
        response_data = {
            'message': f'Successfully enrolled in {course.title}',
            'enrollment': {
                'id': str(existing_enrollment.id),
                'course_id': str(course.id),
                'course_title': course.title,
                'status': existing_enrollment.status,
                'enrollment_date': existing_enrollment.enrollment_date.isoformat(),
                'progress': float(existing_enrollment.progress_percentage),
                'total_lessons': existing_enrollment.total_lessons_count,
                'completed_lessons': existing_enrollment.completed_lessons_count,
            }
        }
        
        print(f"Enrollment successful: {response_data}")
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"CRITICAL ERROR in student_enroll_course: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': 'Failed to enroll in course', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

   

@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Temporarily allow any for testing
def student_course_lessons(request, course_id):
    """
    Get all lessons for a course with progress information and current lesson details
    This is the first API call that returns everything needed for the course page
    """
    print(f"=== DEBUGGING student_course_lessons ===")
    
    
    try:
        # Get the course with lessons and current lesson details
        course = get_object_or_404(Course, id=course_id)
        
        # Check if student is enrolled
        student_profile = request.user.student_profile
        print(f"🔍 ...............Student profile found: {student_profile}..................")
        enrollment = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course=course,
            status__in=['active', 'completed']
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'You are not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Use the optimized serializer that includes lesson list and current lesson details
        serializer = CourseWithLessonsSerializer(
            course, 
            context={'student_profile': student_profile}
        )
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Course.DoesNotExist:
        return Response(
            {'error': 'Course not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"Error in student_course_lessons: {e}")
        return Response(
            {'error': 'Failed to fetch course lessons', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


    
class StudentLessonDetailView(APIView):
    """
    Class-based view for student lesson details
    Handles GET (lesson details) and POST (lesson completion)
    """
    permission_classes = [permissions.AllowAny]  # Temporarily allow any for testing
    
    def get(self, request, lesson_id):
        """
        Get detailed lesson information for enrolled students
        Returns comprehensive lesson data including materials, quiz, and class events
        """
        try:
            
            # Get the lesson
            lesson = get_object_or_404(Lesson, id=lesson_id)
           
            
            # Check if lesson has quiz
            try:
                quiz = lesson.quiz
                print(f"🔍 Quiz found: {quiz.title if quiz else 'None'}")
                if quiz:
                    print(f"🔍 Quiz questions count: {quiz.questions.count()}")
                    print(f"🔍 Quiz details: time_limit={quiz.time_limit}, passing_score={quiz.passing_score}")
            except Exception as e:
                print(f"❌ Error checking quiz: {e}")
            
            # Check if lesson has class event
            try:
                from courses.models import ClassEvent
                class_events = ClassEvent.objects.filter(lesson=lesson)
                print(f"🔍 Class events found: {class_events.count()}")
                for event in class_events:
                    print(f"🔍 Class event: {event.title} - {event.meeting_platform} - {event.meeting_link}")
            except Exception as e:
                print(f"❌ Error checking class events: {e}")
            
            # Check if lesson has materials
            try:
                from courses.models import LessonMaterial
                materials = LessonMaterialModel.objects.filter(lesson=lesson)
                print(f"🔍 Materials found: {materials.count()}")
                for material in materials:
                    print(f"🔍 Material: {material.title} - {material.material_type}")
            except Exception as e:
                print(f"❌ Error checking materials: {e}")
            
            # Check teacher info
            try:
                teacher_name = lesson.course.teacher.get_full_name() if lesson.course.teacher else 'Unknown'
                print(f"🔍 Teacher name: {teacher_name}")
            except Exception as e:
                print(f"❌ Error getting teacher name: {e}")
            
            # Serialize the lesson
            print(f"🔍 About to serialize lesson with LessonDetailSerializer")
            
            # Pre-compute quiz data (moved from serializer)
            quiz_data = None
            try:
                quiz = lesson.quiz
                if quiz:
                    
                    # Get questions
                    questions = quiz.questions.all().order_by('order')
                    
                    # Get student attempts if available (using request.user directly)
                    attempts = []
                    if request.user.is_authenticated:
                        attempts = QuizAttempt.objects.filter(
                            student=request.user,  # Direct reference to User
                            quiz=quiz
                        ).order_by('-started_at')
                        print(f"🔍 Student attempts found: {attempts.count()}")
                    
                    # Build quiz data
                    quiz_data = {
                        'id': str(quiz.id),
                        'title': quiz.title,
                        'description': quiz.description or '',
                        'time_limit': quiz.time_limit,
                        'passing_score': quiz.passing_score,
                        'max_attempts': quiz.max_attempts,
                        'show_correct_answers': quiz.show_correct_answers,
                        'randomize_questions': quiz.randomize_questions,
                        'total_points': quiz.total_points,
                        'question_count': quiz.question_count,
                        'questions': [
                            {
                                'id': str(q.id),
                                'question_text': q.question_text,
                                'type': q.type,
                                'content': q.content,
                                'points': q.points,
                                'explanation': q.explanation or '',
                                'order': q.order,
                            } for q in questions
                        ],
                        "user_attempts_count": len(attempts),
                        "user_attempts": [
                            {
                                "id": str(attempt.id),
                                "attempt_number": attempt.attempt_number,
                                "score": float(attempt.score) if attempt.score else None,
                                "points_earned": attempt.points_earned,
                                "passed": attempt.passed,
                                "answers": attempt.answers,
                                "started_at": attempt.started_at.isoformat(),
                                "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
                                "is_teacher_graded": attempt.is_teacher_graded,
                                "display_status": attempt.display_status
                            } for attempt in attempts
                        ],
                        'can_retake': len(attempts) < quiz.max_attempts if attempts else True,
                        'has_passed': any(attempt.passed for attempt in attempts),
                        'last_attempt': attempts[0].score if attempts else None,
                        'last_attempt_passed': attempts[0].passed if attempts else None,
                    }
                    print(f"🔍 Quiz data prepared: {quiz_data}")
                else:
                    print(f"🔍 No quiz found for lesson")
            except Exception as e:
                print(f"❌ Error preparing quiz data: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
            
            # Pre-compute assignment data (similar to quiz data)
            assignment_data = None
            try:
                from courses.models import Assignment, AssignmentQuestion
                assignment = getattr(lesson, 'assignment', None)
                print(f"🔍 Assignment found: {assignment.title if assignment else 'None'}")
                
                if assignment:
                    # Get assignment questions
                    questions = assignment.questions.all().order_by('order')
                    print(f"🔍 Assignment questions count: {questions.count()}")
                    
                    # Get student submissions if available
                    submissions = []
                    submission_data = None
                    if request.user.is_authenticated:
                        from courses.models import AssignmentSubmission
                        submissions = AssignmentSubmission.objects.filter(
                            assignment=assignment,
                            enrollment__student_profile__user=request.user
                        ).order_by('-submitted_at')
                        print(f"🔍 Student submissions found: {submissions.count()}")
                        
                        # Include the latest submission data
                        if submissions:
                            latest_submission = submissions[0]
                            submission_data = {
                                'id': str(latest_submission.id),
                                'attempt_number': latest_submission.attempt_number,
                                'status': latest_submission.status,
                                'submitted_at': latest_submission.submitted_at.isoformat(),
                                'answers': latest_submission.answers,
                                'is_graded': latest_submission.is_graded,
                                'points_earned': latest_submission.points_earned,
                                'points_possible': latest_submission.points_possible,
                                'percentage': latest_submission.percentage,
                                'passed': latest_submission.passed,
                            }
                            print(f"🔍 Latest submission data: {submission_data}")
                    
                    # Build assignment data
                    assignment_data = {
                        'id': str(assignment.id),
                        'title': assignment.title,
                        'description': assignment.description or '',
                        'assignment_type': assignment.assignment_type,
                        'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
                        'passing_score': assignment.passing_score,
                        'max_attempts': assignment.max_attempts,
                        'show_correct_answers': assignment.show_correct_answers,
                        'randomize_questions': assignment.randomize_questions,
                        'question_count': assignment.question_count,
                        'submission_count': assignment.submissions.count(),
                        'questions': [
                            {
                                'id': str(q.id),
                                'question_text': q.question_text,
                                'type': q.type,
                                'content': q.content,
                                'points': q.points,
                                'explanation': q.explanation or '',
                                'order': q.order,
                            } for q in questions
                        ],
                        'user_submissions_count': len(submissions),
                        'can_submit': len(submissions) < assignment.max_attempts if submissions else True,
                        'has_passed': any(submission.passed for submission in submissions),
                        'last_submission': submissions[0].submitted_at.isoformat() if submissions else None,
                        'last_submission_passed': submissions[0].passed if submissions else None,
                        'submission': submission_data,  # Include the submission data
                    }
                    print(f"🔍 Assignment data prepared: {assignment_data}")
                else:
                    print(f"🔍 No assignment found for lesson")
            except Exception as e:
                print(f"❌ Error preparing assignment data: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
            
            # Pre-compute class event data (moved from serializer)
            class_event_data = None
            if lesson.type == 'live_class':
                try:
                    from courses.models import ClassEvent
                    class_events = ClassEvent.objects.filter(lesson=lesson)
                    print(f"🔍 Class events found: {class_events.count()}")
                    
                    if class_events.exists():
                        class_event = class_events.first()
                        print(f"🔍 Class event found: {class_event.title}")
                        
                        now = timezone.now()
                        
                        # Calculate event status
                        if class_event.start_time <= now <= class_event.end_time:
                            event_status = 'ongoing'
                        elif class_event.start_time > now:
                            event_status = 'upcoming'
                        else:
                            event_status = 'completed'
                        
                        class_event_data = {
                            'id': str(class_event.id),
                            'title': class_event.title,
                            'description': class_event.description or '',
                            'start_time': class_event.start_time,
                            'end_time': class_event.end_time,
                            'platform': class_event.meeting_platform,
                            'meeting_url': class_event.meeting_link,
                            'status': event_status,
                            'can_join_early': class_event.start_time - timedelta(minutes=5) <= now,
                        }
                        print(f"🔍 Class event data prepared: {class_event_data}")
                except Exception as e:
                    print(f"❌ Error preparing class event data: {e}")
                    import traceback
                    print(f"❌ Traceback: {traceback.format_exc()}")
            
            # Pre-compute materials data (moved from serializer)
            materials_data = []
            is_material_available = False
            try:
                from courses.models import LessonMaterial
                # Use the many-to-many relationship properly
                materials = lesson.lesson_materials.all()
                print(f"🔍 Materials found: {materials.count()}")
                
                # Only include materials for live classes
                if lesson.type == 'live_class' and materials.exists():
                    is_material_available = True
                    materials_data = [
                        {
                            'id': str(m.id),
                            'title': m.title,
                            'description': m.description,
                            'material_type': m.material_type,
                            'file_url': m.file_url,
                            'file_size': m.file_size,
                            'file_size_mb': m.file_size_mb,
                            'file_extension': m.file_extension,
                            'order': m.order,
                            'created_at': m.created_at,
                            # Book-specific fields
                            'total_pages': m.book_pages.count() if m.material_type == 'book' else None,
                        } for m in materials
                    ]
                    
                    for material in materials:
                        print(f"🔍 Material: {material.title} - {material.material_type}")
                else:
                    print(f"🔍 No materials for non-live class or no materials found")
            except Exception as e:
                print(f"❌ Error preparing materials data: {e}")
            
            # Get teacher info
            teacher_name = None
            try:
                teacher_name = lesson.course.teacher.get_full_name() if lesson.course.teacher else 'Unknown'
                print(f"🔍 Teacher name: {teacher_name}")
            except Exception as e:
                print(f"❌ Error getting teacher name: {e}")
            
            # Get prerequisites
            prerequisites_data = []
            try:
                prerequisites = list(lesson.prerequisites.values_list('id', flat=True))
                print(f"🔍 Prerequisites found: {prerequisites_data}")
            except Exception as e:
                print(f"❌ Error getting prerequisites: {e}")
            
            # Pass all pre-computed data to serializer context
            context = {
                'request': request,
                'quiz_data': quiz_data,
                'assignment_data': assignment_data,
                'class_event_data': class_event_data,
                'materials_data': materials_data,
                'is_material_available': is_material_available,
                'teacher_name': teacher_name,
                'prerequisites_data': prerequisites_data,
            }
            
            serializer = LessonDetailSerializer(lesson, context=context)
            serialized_data = serializer.data
            
            
            
            return Response(serialized_data)
            
        except Exception as e:
            print(f"❌ ERROR in StudentLessonDetailView.get: {str(e)}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to get lesson details: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, lesson_id):
        """
        Mark a lesson as complete for the authenticated student
        """
        try:
            
            # Check authentication
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get the lesson
            lesson = get_object_or_404(Lesson, id=lesson_id)
            print(f"✅ Lesson found: {lesson.title} (ID: {lesson.id})")
            
            # Get student profile and enrollment
            try:
                student_profile = request.user.student_profile
                print(f"✅ Student profile found: {student_profile}")
            except Exception as e:
                print(f"❌ Error getting student profile: {e}")
                return Response(
                    {'error': 'Student profile not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if student is enrolled in this course
            enrollment = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                course=lesson.course,
                status__in=['active', 'completed']
            ).first()
            
            if not enrollment:
                print(f"❌ Student not enrolled in course: {lesson.course.title}")
                return Response(
                    {'error': 'You are not enrolled in this course'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            print(f"✅ Enrollment found: {enrollment}")
            print(f"✅ Current lesson: {enrollment.current_lesson}")
            print(f"✅ Completed lessons count: {enrollment.completed_lessons_count}")
            
            # Mark lesson as complete using the model method
            success, message = enrollment.mark_lesson_complete(lesson)
            
            if success:
                print(f"✅ Lesson marked as complete successfully: {message}")
                return Response({
                    'message': message,
                    'current_lesson': {
                        'id': str(enrollment.current_lesson.id) if enrollment.current_lesson else None,
                        'title': enrollment.current_lesson.title if enrollment.current_lesson else None,
                        'order': enrollment.current_lesson.order if enrollment.current_lesson else None,
                    } if enrollment.current_lesson else None,
                    'completed_lessons_count': enrollment.completed_lessons_count,
                    'progress_percentage': float(enrollment.progress_percentage),
                    'course_completed': enrollment.status == 'completed',
                }, status=status.HTTP_200_OK)
            else:
                print(f"❌ Failed to mark lesson as complete: {message}")
                return Response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            print(f"❌ ERROR in StudentLessonDetailView.post: {str(e)}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to mark lesson complete: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MaterialContentView(APIView):
    """
    Class-based view for material content
    Returns full material content based on material type
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, material_id):
        """
        Get full material content for a specific material
        Returns complete material data including pages, content, etc.
        """
        try:
            # Get the material
            material = get_object_or_404(LessonMaterialModel, id=material_id)
            
            # Check if user has access to this material
            # 1. Check if user is a teacher who owns the course containing this material
            # 2. Check if user is enrolled as a student in a course that uses this material
            has_access = False
            
            # Check teacher access - if user is teacher of any course that has lessons using this material
            if material.lessons.filter(course__teacher=request.user).exists():
                has_access = True
            
            # Check student access - if user is enrolled in any course that has lessons using this material
            if not has_access:
                user_enrollments = EnrolledCourse.objects.filter(
                    student_profile__user=request.user,
                    status__in=['active', 'completed']
                )
                for enrollment in user_enrollments:
                    if material.lessons.filter(course=enrollment.course).exists():
                        has_access = True
                        break
            
            if not has_access:
                return Response(
                    {'error': 'You do not have access to this material'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Build response based on material type
            response_data = {
                'id': str(material.id),
                'title': material.title,
                'description': material.description,
                'material_type': material.material_type,
                'file_url': material.file_url,
                'file_size': material.file_size,
                'file_size_mb': material.file_size_mb,
                'file_extension': material.file_extension,
                'order': material.order,
                'created_at': material.created_at.isoformat(),
            }
            
            # Add type-specific content
            if material.material_type == 'book':
                # Get all pages for the book
                pages = BookPage.objects.filter(book_material=material).order_by('page_number')
                response_data['total_pages'] = pages.count()
                response_data['pages'] = [
                    {
                        'id': str(page.id),
                        'page_number': page.page_number,
                        'title': page.title,
                        'content': page.content,
                        'is_required': page.is_required,
                        'created_at': page.created_at.isoformat()
                    } for page in pages
                ]
                
            elif material.material_type == 'note':
                # For notes, use description as content
                response_data['content'] = material.description or ''
                
            elif material.material_type == 'video':
                # For videos, try to get video material details (transcript, etc.)
                try:
                    video_material = VideoMaterial.objects.filter(
                        lesson_material=material
                    ).first()
                    if not video_material and material.file_url:
                        # Try to find by video URL if not linked by lesson_material
                        video_material = VideoMaterial.objects.filter(
                            video_url=material.file_url
                        ).first()
                    
                    if video_material:
                        response_data['video_material'] = {
                            'id': str(video_material.id),
                            'video_url': video_material.video_url,
                            'video_id': video_material.video_id,
                            'is_youtube': video_material.is_youtube,
                            'has_transcript': video_material.has_transcript,
                            'transcript_available_to_students': video_material.transcript_available_to_students,
                            # Only include transcript if it's available to students
                            'transcript': video_material.transcript if video_material.transcript_available_to_students else None,
                            'word_count': video_material.word_count if video_material.transcript_available_to_students else None,
                            'language': video_material.language if video_material.transcript_available_to_students else None,
                            'language_name': video_material.language_name if video_material.transcript_available_to_students else None,
                        }
                except Exception as e:
                    print(f"⚠️ Could not load video material details: {e}")
                    # Continue without video material details
                
                # Include basic file info
                response_data['content'] = material.description or ''
                
            else:
                # For other types, include basic file info
                response_data['content'] = material.description or ''
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except LessonMaterialModel.DoesNotExist:
            return Response(
                {'error': 'Material not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ ERROR in MaterialContentView.get: {str(e)}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to get material content: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_quiz_attempt(request, lesson_id):
    """
    Submit a quiz attempt for a specific lesson
    """
   
    
    try:
        # Get the lesson and quiz
        lesson = get_object_or_404(Lesson, id=lesson_id)
        quiz = get_object_or_404(Quiz, lesson=lesson)
        
        # Check if student is enrolled in this course
        student_profile = request.user.student_profile
        enrollment = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course=lesson.course,
            status__in=['active', 'completed']
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'You are not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get submitted answers
        answers = request.data.get('answers', {})
        time_taken = request.data.get('time_taken')
        

        
        # Calculate next attempt number
        existing_attempts = QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz
        ).count()
        next_attempt_number = existing_attempts + 1
        
        # Check if max attempts reached
        if next_attempt_number > quiz.max_attempts:
            return Response(
                {'error': f'Maximum attempts ({quiz.max_attempts}) reached for this quiz'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate score
        questions = quiz.questions.all().order_by('order')
        correct_answers = 0
        total_points = 0
        
        for question in questions:
            user_answer = answers.get(str(question.id))
            if user_answer:
                # 🔧 FIX: Normalize both answers by trimming whitespace and converting to lowercase
                normalized_user_answer = str(user_answer).strip().lower()
                normalized_correct_answer = str(question.content.get('correct_answer', '')).strip().lower()
                
                # Compare normalized answers
                is_correct = normalized_user_answer == normalized_correct_answer
                
                if is_correct:
                    correct_answers += 1
                    total_points += question.points
        
        # Calculate percentage score
        score_percentage = round((correct_answers / questions.count()) * 100) if questions.count() > 0 else 0
        passed = score_percentage >= quiz.passing_score
        
        # Ensure time_taken is a valid number
        if time_taken is None or time_taken == '':
            time_taken = 0
        try:
            time_taken = int(float(time_taken))
        except (ValueError, TypeError):
            time_taken = 0
        
        # Calculate started_at based on time_taken
        started_at = timezone.now() - timezone.timedelta(seconds=time_taken)
        
        # Create quiz attempt
        quiz_attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            enrollment=enrollment,
            attempt_number=next_attempt_number,
            started_at=started_at,
            completed_at=timezone.now(),
            score=score_percentage,
            points_earned=total_points,
            passed=passed,
            answers=answers,
            # Initialize teacher grading fields
            is_teacher_graded=False,
            teacher_grade_data={
                'auto_calculated_score': score_percentage,
                'auto_calculated_points': total_points,
                'auto_calculated_passed': passed,
                'teacher_comments': '',
                'graded_questions': []
            },
            grading_history=[{
                'date': timezone.now().isoformat(),
                'action': 'auto_graded',
                'score': score_percentage,
                'points_earned': total_points,
                'passed': passed
            }]
        )
        
        # Update enrollment quiz metrics
        print(f"🔍 DEBUG: Updating enrollment quiz metrics for {enrollment.student_profile.user.email}")
        print(f"🔍 DEBUG: Quiz score: {score_percentage}%, Passed: {passed}")
        
        try:
            # Update the enrollment's quiz performance metrics
            success = enrollment.update_quiz_performance(quiz_score=score_percentage, passed=passed)
            if success:
                print(f"✅ Successfully updated enrollment quiz metrics")
                print(f"🔍 DEBUG: New average quiz score: {enrollment.average_quiz_score}")
                print(f"🔍 DEBUG: Total quizzes taken: {enrollment.total_quizzes_taken}")
                print(f"🔍 DEBUG: Total quizzes passed: {enrollment.total_quizzes_passed}")
            else:
                print(f"❌ Failed to update enrollment quiz metrics")
        except Exception as e:
            print(f"❌ Error updating enrollment quiz metrics: {e}")
            import traceback
            traceback.print_exc()
        
        # Update lesson progress quiz performance
        try:
            from student.models import StudentLessonProgress
            lesson_progress, created = StudentLessonProgress.objects.get_or_create(
                enrollment=enrollment,
                lesson=lesson,
                defaults={'status': 'not_started'}
            )
            lesson_progress.update_quiz_performance(score_percentage, passed)
            print(f"✅ Successfully updated lesson progress quiz performance")
        except Exception as e:
            print(f"❌ Error updating lesson progress quiz performance: {e}")
            import traceback
            traceback.print_exc()
        
        # Prepare response data
        response_data = {
            'attempt_id': str(quiz_attempt.id),
            'score': score_percentage,
            'correct_answers': correct_answers,
            'total_questions': questions.count(),
            'points_earned': total_points,
            'passed': passed,
            'attempt_number': next_attempt_number,
            'max_attempts': quiz.max_attempts,
            'can_retake': next_attempt_number < quiz.max_attempts,
            'message': 'Quiz submitted successfully'
        }
        
        print(f"Quiz attempt created: {response_data}")
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"Error in submit_quiz_attempt: {e}")
        return Response(
            {'error': 'Failed to submit quiz attempt', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




@permission_classes([permissions.IsAuthenticated])
class TeacherDashboardAPIView(APIView):
    
    
    def get(self, request):
        teacher = request.user
        
        return Response({
            'header_data': self.get_header_data(teacher),
            'upcoming_classes': self.get_upcoming_classes(teacher),
            'recent_activity': self.get_recent_activity(teacher),
            'course_count': self.get_course_count(teacher),
            'teacher_settings': self.get_teacher_settings(teacher),
        })


    def get_header_data(self, teacher):
        """Get welcome message and quick stats"""
        return {
            'teacher_name': teacher.get_full_name() or teacher.first_name,
            'total_students': self.get_total_students(teacher),
            'active_courses': self.get_active_courses(teacher),
            'total_enrollments': self.get_total_enrollments(teacher),
            'monthly_revenue': self.get_monthly_revenue(teacher),
            'pending_assignment_count': self.get_pending_assignment_count(teacher),
        }

    def get_total_students(self, teacher):
        """Count total students across all teacher's courses"""
        # Debug: Check teacher's courses
        teacher_courses = Course.objects.filter(teacher=teacher)
        print(f"DEBUG TOTAL STUDENTS: Teacher {teacher.email} has {teacher_courses.count()} courses")
        
        # Debug: Check all enrollments for this teacher's courses
        enrollments = EnrolledCourse.objects.filter(course__teacher=teacher)
        print(f"DEBUG TOTAL STUDENTS: Found {enrollments.count()} total enrollments")
        
        # Debug: Check distinct students
        distinct_students = enrollments.values('student_profile__user').distinct()
        print(f"DEBUG TOTAL STUDENTS: Found {distinct_students.count()} distinct students")
        
        return distinct_students.count()

    def get_active_courses(self, teacher):
        """Count published/active courses"""
        return Course.objects.filter(
            teacher=teacher,
            status='published'
        ).count()

    def get_total_enrollments(self, teacher):
        """Count total enrollments across all teacher's courses"""
        from student.models import EnrolledCourse
        
        # Get all enrollments for this teacher's courses
        enrollments = EnrolledCourse.objects.filter(course__teacher=teacher)
        
        # Debug: Check enrollments
        print(f"DEBUG TOTAL ENROLLMENTS: Teacher {teacher.email} has {enrollments.count()} total enrollments")
        
        return enrollments.count()

    def get_monthly_revenue(self, teacher):
        """Calculate revenue for current month from course enrollments"""
        from datetime import datetime
        from django.db.models import Sum
        
        current_month = datetime.now().replace(day=1)
        
        # Get all enrollments for this month (assuming all enrollments are paid)
        monthly_enrollments = EnrolledCourse.objects.filter(
            course__teacher=teacher,
            enrollment_date__gte=current_month.date(),
            status='active'  # Only count active enrollments
        )
        
        # Calculate total revenue
        total_revenue = 0
        for enrollment in monthly_enrollments:
            total_revenue += float(enrollment.course.price)
        
        return total_revenue

    def get_pending_assignment_count(self, teacher):
        """Count pending assignment submissions (status='submitted', is_graded=False)"""
        from courses.models import AssignmentSubmission
        
        # Count submissions for teacher's courses that are submitted but not graded
        pending_count = AssignmentSubmission.objects.filter(
            assignment__lesson__course__teacher=teacher,
            status='submitted',
            is_graded=False
        ).count()
        
        return pending_count

    def get_upcoming_classes(self, teacher):
        """Get today's and upcoming live classes"""
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        end_of_week = today + timedelta(days=7)
        
        # Get ClassEvents with lesson_type='live' for teacher's courses
        live_classes = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher,
            lesson_type='live',
            start_time__date__range=[today, end_of_week]
        ).select_related('class_instance', 'class_instance__course').order_by('start_time')
        
        return {
            'today_classes': [
                {
                    'id': str(cls.id),
                    'title': cls.title,
                    'course_name': cls.class_instance.course.title,
                    'scheduled_date': cls.start_time.date().isoformat(),
                    'start_time': cls.start_time.isoformat(),
                    'end_time': cls.end_time.isoformat(),
                    'student_count': 0,  # Placeholder - no enrolled_students relationship in ClassEvent
                    'meeting_link': cls.meeting_link,
                    'meeting_platform': cls.meeting_platform,
                    'meeting_id': cls.meeting_id,
                    'meeting_password': cls.meeting_password,
                    'duration_minutes': cls.duration_minutes,
                    'description': cls.description,
                }
                for cls in live_classes.filter(start_time__date=today)
            ],
            'upcoming_classes': [
                {
                    'id': str(cls.id),
                    'title': cls.title,
                    'course_name': cls.class_instance.course.title,
                    'scheduled_date': cls.start_time.date().isoformat(),
                    'start_time': cls.start_time.isoformat(),
                    'end_time': cls.end_time.isoformat(),
                    'student_count': 0,  # Placeholder - no enrolled_students relationship in ClassEvent
                    'meeting_link': cls.meeting_link,
                    'meeting_platform': cls.meeting_platform,
                    'meeting_id': cls.meeting_id,
                    'meeting_password': cls.meeting_password,
                    'duration_minutes': cls.duration_minutes,
                    'description': cls.description,
                }
                for cls in live_classes.filter(start_time__date__gt=today)
            ],
            'total_count': live_classes.count()
        }

    def get_recent_activity(self, teacher):
        """Get recent activity across all teacher's courses"""
        from datetime import datetime, timedelta
        
        activities = []
        
        # Debug: Check teacher's courses
        teacher_courses = Course.objects.filter(teacher=teacher)
        print(f"DEBUG RECENT ACTIVITY: Teacher {teacher.email} has {teacher_courses.count()} courses")
        
        # Student enrollments
        enrollments = EnrolledCourse.objects.filter(
            course__teacher=teacher,
            enrollment_date__gte=datetime.now().date() - timedelta(days=7)
        ).select_related('student_profile__user', 'course')[:5]
        
        print(f"DEBUG RECENT ACTIVITY: Found {enrollments.count()} recent enrollments")
        
        for enrollment in enrollments:
            student_name = enrollment.student_profile.user.get_full_name() or enrollment.student_profile.user.first_name
            # Convert date to timezone-aware datetime for consistent sorting
            from django.utils import timezone as django_timezone
            enrollment_datetime = django_timezone.make_aware(
                datetime.combine(enrollment.enrollment_date, datetime.min.time())
            )
            activities.append({
                'id': enrollment.id,
                'type': 'enrollment',
                'message': f"New student enrolled in {enrollment.course.title}",
                'student_name': student_name,
                'course_name': enrollment.course.title,
                'timestamp': enrollment_datetime,
                'icon': 'user-plus',
                'time_ago': self.get_time_ago(enrollment.enrollment_date)
            })
        
        
        # Course reviews
        reviews = CourseReview.objects.filter(
            course__teacher=teacher,
            created_at__gte=datetime.now() - timedelta(days=7)
        ).select_related('course')[:5]
        
        for review in reviews:
            activities.append({
                'id': review.id,
                'type': 'review',
                'message': f"New {review.rating}-star review for {review.course.title}",
                'student_name': review.student_name,
                'course_name': review.course.title,
                'rating': review.rating,
                'timestamp': review.created_at,
                'icon': 'star',
                'time_ago': self.get_time_ago(review.created_at)
            })
        
        # Sort by timestamp and return latest 10
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        return activities[:10]

    def get_time_ago(self, timestamp):
        """Helper method to format time ago"""
        from datetime import datetime, date
        
        # Handle both date and datetime objects
        if isinstance(timestamp, date) and not isinstance(timestamp, datetime):
            # For date-only fields, calculate based on days difference
            today = date.today()
            diff_days = (today - timestamp).days
            
            if diff_days == 0:
                return "Today"
            elif diff_days == 1:
                return "Yesterday"
            elif diff_days < 7:
                return f"{diff_days} days ago"
            elif diff_days < 30:
                weeks = diff_days // 7
                return f"{weeks} week{'s' if weeks > 1 else ''} ago"
            else:
                months = diff_days // 30
                return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            # For datetime fields, use the original calculation
            now = datetime.now(timestamp.tzinfo) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo else datetime.now()
            diff = now - timestamp
            
            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            else:
                return "Just now"

    def get_course_count(self, teacher):
        """Get total course count for teacher"""
        return Course.objects.filter(teacher=teacher).count()

    def get_teacher_settings(self, teacher):
        """Get teacher settings from UserDashboardSettings"""
        from settings.models import UserDashboardSettings
        
        try:
            settings = UserDashboardSettings.get_or_create_settings(teacher)
            return {
                'default_quiz_points': settings.default_quiz_points,
                'default_assignment_points': settings.default_assignment_points,
                'default_course_passing_score': settings.default_course_passing_score,
                'default_quiz_time_limit': settings.default_quiz_time_limit,
                'auto_grade_multiple_choice': settings.auto_grade_multiple_choice,
                'show_correct_answers_by_default': settings.show_correct_answers_by_default,
                'theme_preference': settings.theme_preference,
                'notifications_enabled': settings.notifications_enabled,
            }
        except Exception as e:
            print(f"Error getting teacher settings: {e}")
            # Return default values if settings fail
            return {
                'default_quiz_points': 1,
                'default_assignment_points': 5,
                'default_course_passing_score': 70,
                'default_quiz_time_limit': 10,
                'auto_grade_multiple_choice': False,
                'show_correct_answers_by_default': True,
                'theme_preference': 'system',
                'notifications_enabled': True,
            }


# ===== COMPREHENSIVE STUDENT DASHBOARD =====

class StudentCourseDashboardView(APIView):
    """
    Comprehensive student course dashboard - returns everything in one call:
    - Enrolled courses with progress
    - Recommended courses with billing & class data
    - All necessary data for enrollment flow
    
    This eliminates multiple API calls and improves performance.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Get comprehensive student dashboard data
        """
        try:
            print("=== Student Course Dashboard API ===")
            
            # Get student profile
            student_profile = getattr(request.user, 'student_profile', None)
            print(f"Student profile: {student_profile}")
            
            # Initialize response data
            response_data = {}
            
            # 1. GET ENROLLED COURSES
            print("Step 1: Getting enrolled courses...")
            enrolled_courses_data = self.get_enrolled_courses_data(student_profile)
            response_data['enrolled_courses'] = enrolled_courses_data['courses']
            response_data['total_enrolled'] = enrolled_courses_data['total']
            
            # 2. GET RECOMMENDED COURSES (with comprehensive data)
            print("Step 2: Getting recommended courses with billing and classes...")
            recommended_courses_data = self.get_recommended_courses_data(student_profile, request.user)
            response_data['recommended_courses'] = recommended_courses_data['courses']
            response_data['total_recommendations'] = recommended_courses_data['total']
            
            # 3. ADD DASHBOARD METADATA
            response_data['dashboard_metadata'] = {
                'user_id': str(request.user.id),
                'student_profile_id': str(student_profile.id) if student_profile else None,
                'generated_at': timezone.now().isoformat(),
                'api_version': '2.0'
            }
            
            print(f"Dashboard response complete: {len(response_data['enrolled_courses'])} enrolled, {len(response_data['recommended_courses'])} recommended")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"CRITICAL ERROR in StudentCourseDashboardView: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to fetch student dashboard data', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_enrolled_courses_data(self, student_profile):
        """
        Get enrolled courses data with comprehensive information
        """
        try:
            if not student_profile:
                return {'courses': [], 'total': 0}
            
            # Get enrolled courses
            enrolled_courses = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status__in=['active', 'completed']
            ).select_related('course', 'current_lesson').order_by('-enrollment_date')
            
            courses_data = []
            for enrollment in enrolled_courses:
                course = enrollment.course
                
                try:
                    # Get course image
                    course_image = getattr(course, 'image', None)
                    if course_image:
                        image_url = course_image.url if hasattr(course_image, 'url') else str(course_image)
                    else:
                        image_url = "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=300&h=200&fit=crop"
                    
                    # Calculate next lesson
                    next_lesson = "Course Completed!" if enrollment.status == 'completed' else (
                        enrollment.current_lesson.title if enrollment.current_lesson else "Start Learning"
                    )
                    
                    # Get instructor name
                    instructor_name = "Little Learners Tech"
                    if hasattr(course, 'teacher') and course.teacher:
                        instructor_name = course.teacher.get_full_name() or course.teacher.email
                    
                    # Build course data
                    course_data = {
                        'id': str(course.id),
                        'title': course.title,
                        'description': course.description,
                        'instructor': instructor_name,
                        'image': image_url,
                        'icon': course.icon,
                        'progress': float(enrollment.progress_percentage),
                        'total_lessons': course.lessons.count(),
                        'completed_lessons': enrollment.completed_lessons_count,
                        'next_lesson': next_lesson,
                        'status': enrollment.status,
                        'enrollment_date': enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None,
                        'last_accessed': enrollment.last_accessed.isoformat() if enrollment.last_accessed else None,
                        'overall_grade': enrollment.overall_grade,
                        'average_quiz_score': float(enrollment.average_quiz_score) if enrollment.average_quiz_score else None,
                        'difficulty': getattr(course, 'level', 'beginner'),
                        'category': course.category,
                        'rating': get_course_average_rating(course),
                        
                        # Add billing data for enrolled courses (for potential upgrades/changes)
                        'billing': self.get_course_billing_data(course)
                    }
                    courses_data.append(course_data)
                    
                except Exception as course_error:
                    print(f"ERROR processing enrolled course {course.title}: {course_error}")
                    continue
            
            return {'courses': courses_data, 'total': len(courses_data)}
            
        except Exception as e:
            print(f"Error getting enrolled courses: {e}")
            return {'courses': [], 'total': 0}
    
    def get_recommended_courses_data(self, student_profile, user):
        """
        Get recommended courses with comprehensive billing and class data
        """
        try:
            # Get enrolled course IDs to exclude
            enrolled_course_ids = []
            if student_profile:
                enrolled_course_ids = list(
                    EnrolledCourse.objects.filter(
                        student_profile=student_profile,
                        status__in=['active', 'completed']
                    ).values_list('course_id', flat=True)
                )
            
            # Get recommended courses (featured + not enrolled)
            recommended_courses = Course.objects.filter(
                status='published',
                featured=True
            ).exclude(id__in=enrolled_course_ids)[:6]
            
            courses_data = []
            for course in recommended_courses:
                try:
                    # Get course image
                    course_image = getattr(course, 'image', None)
                    if course_image:
                        image_url = course_image.url if hasattr(course_image, 'url') else str(course_image)
                    else:
                        image_url = "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=300&h=200&fit=crop"
                    
                    # Get instructor name
                    instructor_name = "Little Learners Tech"
                    if hasattr(course, 'teacher') and course.teacher:
                        instructor_name = course.teacher.get_full_name() or course.teacher.email
                    
                    # Build comprehensive course data
                    course_data = {
                        'id': str(course.id),
                        'uuid': str(course.id),
                        'title': course.title,
                        'description': course.description,
                        'instructor': instructor_name,
                        'image': image_url,
                        'icon': course.icon,
                        'total_lessons': getattr(course, 'total_lessons', 12),
                        'duration': getattr(course, 'duration', '8 weeks'),
                        'max_students': getattr(course, 'max_students', 12),
                        'difficulty': getattr(course, 'level', 'beginner'),
                        'category': course.category,
                        'rating': get_course_average_rating(course),
                        'price': float(course.price) if course.price else 0,
                        'enrolled_students': 0,  # Can be calculated from enrollments
                        
                        # COMPREHENSIVE DATA (eliminates additional API calls)
                        'billing': self.get_course_billing_data(course),
                        'available_classes': self.get_course_available_classes_data(course),
                        'enrollment_status': self.get_course_enrollment_status(course, user)
                    }
                    courses_data.append(course_data)
                    
                except Exception as course_error:
                    print(f"ERROR processing recommended course {course.title}: {course_error}")
                    continue
            
            return {'courses': courses_data, 'total': len(courses_data)}
            
        except Exception as e:
            print(f"Error getting recommended courses: {e}")
            return {'courses': [], 'total': 0}
    
    def get_course_billing_data(self, course):
        """
        Get comprehensive billing information for a course
        """
        try:
            billing_product = getattr(course, 'billing_product', None)
            if not billing_product:
                return None
            
            # Calculate prices using existing logic
            from .price_calculator import calculate_course_prices
            prices = calculate_course_prices(float(course.price), getattr(course, 'duration_weeks', 8))
            
            # Get Stripe price IDs
            one_time_price = billing_product.prices.filter(billing_period='one_time', is_active=True).first()
            monthly_price = billing_product.prices.filter(billing_period='monthly', is_active=True).first()
            
            billing_data = {
                "stripe_product_id": billing_product.stripe_product_id,
                "pricing_options": {
                    "one_time": {
                        "amount": prices['one_time_price'],
                        "currency": "usd",
                        "stripe_price_id": one_time_price.stripe_price_id if one_time_price else None,
                        "savings": round(prices['monthly_total'] - prices['one_time_price'], 2) if prices['total_months'] > 1 else 0
                    }
                },
                "trial": {
                    "duration_days": 14,
                    "available": True,
                    "requires_payment_method": True
                }
            }
            
            # Add monthly option if available
            if prices['total_months'] > 1 and monthly_price:
                billing_data["pricing_options"]["monthly"] = {
                    "amount": prices['monthly_price'],
                    "currency": "usd",
                    "stripe_price_id": monthly_price.stripe_price_id,
                    "total_months": prices['total_months'],
                    "total_amount": prices['monthly_total']
                }
            
            return billing_data
            
        except Exception as e:
            print(f"Error getting billing data for course {course.id}: {e}")
            return None
    
    def get_course_available_classes_data(self, course):
        """
        Get available classes for a course (eliminates separate API call)
        Uses the same logic as course_available_classes function
        """
        try:
            from courses.models import Class, ClassSession
            
            # Get active classes for this course that have available spots
            # Use the same logic as the working course_available_classes function
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
                        'id': cls.id,
                        'name': cls.name,
                        'description': cls.description,
                        'max_capacity': cls.max_capacity,
                        'student_count': cls.student_count,
                        'course_id': cls.course.id,
                        'course_title': cls.course.title,
                        'sessions': sessions_info,
                        'formatted_schedule': cls.formatted_schedule,
                        'session_count': cls.session_count,
                        'teacher_name': cls.teacher.get_full_name() or cls.teacher.email,
                        'available_spots': cls.available_spots
                    })
            
            return available_classes
            
        except Exception as e:
            print(f"Error getting available classes for course {course.title}: {e}")
            return []
    
    def get_course_enrollment_status(self, course, user):
        """
        Check user's enrollment status for a course
        """
        try:
            student_profile = getattr(user, 'student_profile', None)
            if not student_profile:
                return {
                    "is_enrolled": False,
                    "can_enroll": True,
                    "enrollment_date": None,
                    "status": None
                }
            
            enrollment = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                course=course
            ).first()
            
            return {
                "is_enrolled": enrollment is not None,
                "can_enroll": enrollment is None,
                "enrollment_date": enrollment.enrollment_date.isoformat() if enrollment else None,
                "status": enrollment.status if enrollment else None
            }
            
        except Exception as e:
            print(f"Error getting enrollment status: {e}")
            return {
                "is_enrolled": False,
                "can_enroll": True,
                "enrollment_date": None,
                "status": None
            }


class LessonMaterial(APIView):
    """
    Lesson material management
    
    GET: List materials for a lesson
    POST: Create material for a lesson
    PUT: Update specific material
    DELETE: Delete specific material
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, lesson_id):
        """
        GET: Retrieve materials for a specific lesson
        
        Query Parameters:
        - lightweight=true: Returns only metadata (names, types, IDs) - faster
        - lightweight=false: Returns full material data (default)
        """
        try:
            lesson = get_object_or_404(Lesson, id=lesson_id)
            
            # Check if user has access to this lesson
            if not self._user_has_access(request.user, lesson):
                return Response(
                    {'error': 'You do not have permission to access this lesson'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if lightweight mode is requested
            lightweight = request.GET.get('lightweight', 'false').lower() == 'true'
            
            # Get materials for this lesson
            materials = lesson.lesson_materials.all().order_by('order')
            
            if lightweight:
                # Return only metadata for fast loading
                materials_data = []
                for material in materials:
                    material_data = {
                        'id': str(material.id),
                        'title': material.title,
                        'description': material.description,
                        'material_type': material.material_type,
                        'is_required': material.is_required,
                        'is_downloadable': material.is_downloadable,
                        'order': material.order,
                        'created_at': material.created_at.isoformat(),
                    }
                    
                    # Add type-specific metadata
                    if material.material_type == 'book':
                        # Get book page count without loading full content
                        page_count = BookPage.objects.filter(book_material=material).count()
                        material_data['total_pages'] = page_count
                        material_data['has_pages'] = page_count > 0
                    elif material.material_type == 'note':
                        # For notes, we might want to show if content exists
                        material_data['has_content'] = bool(material.content)
                    elif material.material_type in ['document', 'pdf', 'presentation']:
                        # For files, show file info
                        material_data['file_size_mb'] = material.file_size_mb
                        material_data['file_extension'] = material.file_extension
                    
                    materials_data.append(material_data)
            else:
                # Return full material data (existing behavior)
                materials_data = [{
                    'id': str(material.id),
                    'title': material.title,
                    'description': material.description,
                    'material_type': material.material_type,
                    'file_url': material.file_url,
                    'file_size': material.file_size,
                    'file_size_mb': material.file_size_mb,
                    'file_extension': material.file_extension,
                    'is_required': material.is_required,
                    'is_downloadable': material.is_downloadable,
                    'order': material.order,
                    'created_at': material.created_at.isoformat(),
                    'updated_at': material.updated_at.isoformat()
                } for material in materials]
            
            return Response({
                'lesson_id': str(lesson.id),
                'lesson_title': lesson.title,
                'materials': materials_data,
                'total_count': materials.count(),
                'lightweight': lightweight
            }, status=status.HTTP_200_OK)
            
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to retrieve materials: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, lesson_id):
        """
        POST: Create material for a lesson
        """
        try:
            lesson = get_object_or_404(Lesson, id=lesson_id)
            
            # Check if user has permission to modify this lesson
            if not self._user_can_modify(request.user, lesson):
                return Response(
                    {'error': 'You do not have permission to modify this lesson'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if this is a book creation (with pages)
            material_type = request.data.get('material_type', '')
            pages_data = request.data.get('pages', [])
            
            if material_type == 'book' and pages_data:
                # Use BookCreationSerializer for complete book creation
                from .serializers import BookCreationSerializer
                serializer = BookCreationSerializer(data=request.data)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                material = serializer.save()
                material.lessons.add(lesson)
                
                # Return book with pages
                return Response({
                    'message': 'Book created successfully',
                    'material': {
                        'id': str(material.id),
                        'title': material.title,
                        'description': material.description,
                        'material_type': material.material_type,
                        'file_url': material.file_url,
                        'file_size': material.file_size,
                        'file_size_mb': material.file_size_mb,
                        'file_extension': material.file_extension,
                        'is_required': material.is_required,
                        'is_downloadable': material.is_downloadable,
                        'order': material.order,
                        'created_at': material.created_at.isoformat(),
                        'total_pages': len(material.created_pages),
                        'pages': [{
                            'id': str(page.id),
                            'page_number': page.page_number,
                            'title': page.title,
                            'content': page.content,
                            'is_required': page.is_required,
                            'created_at': page.created_at.isoformat()
                        } for page in material.created_pages]
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                # Use regular LessonMaterialCreateSerializer for other materials
                from .serializers import LessonMaterialCreateSerializer
                serializer = LessonMaterialCreateSerializer(data=request.data)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                material = serializer.save()
                material.lessons.add(lesson)
            
            return Response({
                'message': 'Material created successfully',
                'material': {
                    'id': str(material.id),
                    'title': material.title,
                    'description': material.description,
                    'material_type': material.material_type,
                    'file_url': material.file_url,
                    'file_size': material.file_size,
                    'file_size_mb': material.file_size_mb,
                    'file_extension': material.file_extension,
                    'is_required': material.is_required,
                    'is_downloadable': material.is_downloadable,
                    'order': material.order,
                    'created_at': material.created_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to create material: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, material_id):
        """
        PUT: Update specific material
        """
        try:
            try:
                material = LessonMaterialModel.objects.get(id=material_id)
            except LessonMaterialModel.DoesNotExist:
                return Response(
                    {'error': 'Material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user can modify (check if user teaches any of the lessons this material belongs to)
            can_modify = any(self._user_can_modify(request.user, lesson) for lesson in material.lessons.all())
            if not can_modify:
                return Response(
                    {'error': 'You do not have permission to modify this material'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # For document materials, handle file deletion when file_url changes
            old_file_url = None
            if material.material_type == 'document':
                old_file_url = material.file_url
                new_file_url = request.data.get('file_url')
                
                # If file_url is being changed or removed, delete old DocumentMaterial and file
                if old_file_url and (new_file_url != old_file_url or new_file_url is None or new_file_url == ''):
                    try:
                        from .models import DocumentMaterial
                        # Try to find DocumentMaterial linked to this LessonMaterial
                        document_material = DocumentMaterial.objects.filter(lesson_material=material).first()
                        
                        # If not found by relationship, try to find by file_url
                        if not document_material and old_file_url:
                            document_material = DocumentMaterial.objects.filter(file_url=old_file_url).first()
                        
                        # If found, delete it (this will trigger file deletion from GCS)
                        if document_material:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.info(f"Deleting old DocumentMaterial {document_material.id} for file replacement")
                            document_material.delete()
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error deleting old DocumentMaterial during update: {e}")
                        # Continue with update even if old file deletion fails
            
            # Validate and update material using serializer
            from .serializers import LessonMaterialUpdateSerializer
            serializer = LessonMaterialUpdateSerializer(material, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            material = serializer.save()
            
            return Response({
                'message': 'Material updated successfully',
                'material': {
                    'id': str(material.id),
                    'title': material.title,
                    'description': material.description,
                    'material_type': material.material_type,
                    'file_url': material.file_url,
                    'file_size': material.file_size,
                    'file_size_mb': material.file_size_mb,
                    'file_extension': material.file_extension,
                    'is_required': material.is_required,
                    'is_downloadable': material.is_downloadable,
                    'order': material.order,
                    'updated_at': material.updated_at.isoformat()
                }
            }, status=status.HTTP_200_OK)
            
        except LessonMaterialModel.DoesNotExist:
            return Response(
                {'error': 'Material not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to update material: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, material_id):
        """
        DELETE: Delete specific material
        """
        try:
            try:
                material = LessonMaterialModel.objects.get(id=material_id)
            except LessonMaterialModel.DoesNotExist:
                return Response(
                    {'error': 'Material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user has permission to modify any lesson this material belongs to
            can_modify = any(self._user_can_modify(request.user, lesson) for lesson in material.lessons.all())
            if not can_modify:
                return Response(
                    {'error': 'You do not have permission to delete this material'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # For document materials, find and delete associated DocumentMaterial before deleting LessonMaterial
            # This ensures the file is deleted from GCS
            if material.material_type == 'document':
                try:
                    from .models import DocumentMaterial
                    import logging
                    logger = logging.getLogger(__name__)
                    
                    # Try to find DocumentMaterial linked to this LessonMaterial
                    document_material = DocumentMaterial.objects.filter(lesson_material=material).first()
                    
                    # If not found by relationship, try to find by file_url
                    if not document_material and material.file_url:
                        document_material = DocumentMaterial.objects.filter(file_url=material.file_url).first()
                    
                    # If still not found, try to find by file_name (extract from file_url)
                    if not document_material and material.file_url:
                        # Extract file path from GCS URL
                        # URL format: https://storage.googleapis.com/bucket-name/path/to/file
                        try:
                            from urllib.parse import urlparse
                            parsed_url = urlparse(material.file_url)
                            # Get path after bucket name (e.g., /documents/uuid-filename.pdf)
                            path_parts = parsed_url.path.split('/', 2)
                            if len(path_parts) >= 3:
                                file_path = path_parts[2]  # Get everything after /bucket-name/
                                document_material = DocumentMaterial.objects.filter(file_name=file_path).first()
                        except Exception as e:
                            logger.warning(f"Could not parse file_url to find DocumentMaterial: {e}")
                    
                    # If found, delete it (this will trigger file deletion from GCS via DocumentMaterial.delete())
                    if document_material:
                        logger.info(f"Found DocumentMaterial {document_material.id} for LessonMaterial {material_id}, deleting...")
                        document_material.delete()
                        logger.info(f"Successfully deleted DocumentMaterial {document_material.id} and file from GCS")
                    else:
                        logger.warning(f"Could not find DocumentMaterial for LessonMaterial {material_id} with file_url: {material.file_url}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error deleting DocumentMaterial for LessonMaterial {material_id}: {e}")
                    # Continue with LessonMaterial deletion even if DocumentMaterial deletion fails
            
            # Delete the LessonMaterial (this will cascade delete related DocumentMaterial if linked)
            material.delete()
            
            return Response({
                'message': 'Material deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except LessonMaterialModel.DoesNotExist:
            return Response(
                {'error': 'Material not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to delete material: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _user_has_access(self, user, lesson):
        """Check if user has access to view this lesson"""
        # Teachers can access lessons they created
        if user.role == 'teacher' and lesson.course.teacher == user:
            return True
        
        # Students can access lessons in courses they're enrolled in
        if user.role == 'student':
            from student.models import EnrolledCourse
            return EnrolledCourse.objects.filter(
                student_profile__user=user,
                course=lesson.course,
                status__in=['active', 'completed']
            ).exists()
        
        return False
    
    def _user_can_modify(self, user, lesson):
        """Check if user can modify this lesson"""
        return user.role == 'teacher' and lesson.course.teacher == user


class BookPageView(APIView):
    """
    Book page management with pagination support
    
    GET: Get specific page or paginated book content
    POST: Create new page (for new books)
    PUT: Update existing page (for existing books)
    DELETE: Delete page
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, material_id, page_number=None):
        """
        GET: Retrieve book page(s)
        - If page_number provided: Get specific page
        - If no page_number: Get all pages at once
        """
        try:
            # Get book material
            try:
                book_material = LessonMaterialModel.objects.get(
                    id=material_id, 
                    material_type='book'
                )
            except Exception as e:
                return Response(
                    {'error': 'Book material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check access permissions (check if user has access to any lesson this material belongs to)
            has_access = any(self._user_has_access(request.user, lesson) for lesson in book_material.lessons.all())
            if not has_access:
                return Response(
                    {'error': 'You do not have permission to access this book'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if page_number:
                # Get specific page
                return self._get_specific_page(book_material, page_number)
            else:
                # Get all pages at once - using direct query to avoid related_name issues
                try:
                    pages = BookPage.objects.filter(book_material=book_material).order_by('page_number')
                    pages_data = []
                    for page in pages:
                        pages_data.append({
                            'id': str(page.id),
                            'page_number': page.page_number,
                            'title': page.title,
                            'content': page.content,
                            'is_required': page.is_required,
                            'created_at': page.created_at.isoformat(),
                            'updated_at': page.updated_at.isoformat()
                        })
                    
                    return Response({
                        'book_id': str(book_material.id),
                        'book_title': book_material.title,
                        'total_pages': len(pages_data),
                        'pages': pages_data
                    }, status=status.HTTP_200_OK)
                except Exception as page_error:
                    return Response({
                        'error': f'Failed to retrieve pages: {str(page_error)}',
                        'book_id': str(book_material.id),
                        'book_title': book_material.title,
                        'total_pages': 0,
                        'pages': []
                    }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response(
                {'error': f'Failed to retrieve book pages: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, material_id):
        """
        POST: Create new page for book
        """
        try:
            try:
                book_material = LessonMaterialModel.objects.get(
                    id=material_id, 
                    material_type='book'
                )
            except LessonMaterialModel.DoesNotExist:
                return Response(
                    {'error': 'Book material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user can modify
            can_modify = any(self._user_can_modify(request.user, lesson) for lesson in book_material.lessons.all())
            if not can_modify:
                return Response(
                    {'error': 'You do not have permission to modify this book'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get next page number
            last_page = BookPage.objects.filter(book_material=book_material).order_by('-page_number').first()
            next_page_number = (last_page.page_number + 1) if last_page else 1
            
            # Validate and create page using serializer
            from .serializers import BookPageCreateSerializer
            serializer = BookPageCreateSerializer(
                data=request.data,
                context={
                    'book_material': book_material,
                    'page_number': next_page_number
                }
            )
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            page = serializer.save()
            
            return Response({
                'message': 'Page created successfully',
                'page': {
                    'id': str(page.id),
                    'page_number': page.page_number,
                    'title': page.title,
                    'content': page.content,
                    'is_required': page.is_required,
                    'created_at': page.created_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to create page: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, material_id, page_number):
        """
        PUT: Update existing page
        """
        try:
            try:
                book_material = LessonMaterialModel.objects.get(
                    id=material_id, 
                    material_type='book'
                )
            except LessonMaterialModel.DoesNotExist:
                return Response(
                    {'error': 'Book material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                page = BookPage.objects.get(
                    book_material=book_material,
                    page_number=page_number
                )
            except BookPage.DoesNotExist:
                return Response(
                    {'error': f'Page {page_number} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user can modify
            can_modify = any(self._user_can_modify(request.user, lesson) for lesson in book_material.lessons.all())
            if not can_modify:
                return Response(
                    {'error': 'You do not have permission to modify this page'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Validate and update page using serializer
            from .serializers import BookPageUpdateSerializer
            serializer = BookPageUpdateSerializer(page, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            page = serializer.save()
            
            return Response({
                'message': 'Page updated successfully',
                'page': {
                    'id': str(page.id),
                    'page_number': page.page_number,
                    'title': page.title,
                    'content': page.content,
                    'image_url': page.image_url,
                    'audio_url': page.audio_url,
                    'is_required': page.is_required,
                    'updated_at': page.updated_at.isoformat()
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to update page: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_specific_page(self, book_material, page_number):
        """Get specific page with navigation info"""
        try:
            page = BookPage.objects.get(
                book_material=book_material,
                page_number=page_number
            )
            
            # Get navigation info
            total_pages = BookPage.objects.filter(book_material=book_material).count()
            has_next = BookPage.objects.filter(
                book_material=book_material,
                page_number=page_number + 1
            ).exists()
            has_previous = BookPage.objects.filter(
                book_material=book_material,
                page_number=page_number - 1
            ).exists()
            
            return Response({
                'book': {
                    'id': str(book_material.id),
                    'title': book_material.title,
                    'total_pages': total_pages
                },
                'page': {
                    'id': str(page.id),
                    'page_number': page.page_number,
                    'title': page.title,
                    'content': page.content,
                    'image_url': page.image_url,
                    'audio_url': page.audio_url,
                    'is_required': page.is_required,
                    'created_at': page.created_at.isoformat(),
                    'updated_at': page.updated_at.isoformat()
                },
                'navigation': {
                    'current_page': page_number,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_previous': has_previous,
                    'next_page': page_number + 1 if has_next else None,
                    'previous_page': page_number - 1 if has_previous else None
                }
            }, status=status.HTTP_200_OK)
            
        except BookPage.DoesNotExist:
            return Response(
                {'error': f'Page {page_number} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _get_paginated_pages(self, request, book_material):
        """Get paginated list of pages"""
        from django.core.paginator import Paginator
        
        page_number = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        
        try:
            # Get pages for this book material
            pages = BookPage.objects.filter(book_material=book_material).order_by('page_number')
            paginator = Paginator(pages, per_page)
            page_obj = paginator.get_page(page_number)
        except Exception as e:
            return Response(
                {'error': f'Failed to paginate pages: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        pages_data = [{
            'id': str(page.id),
            'page_number': page.page_number,
            'title': page.title,
            'content': page.content[:200] + '...' if len(page.content) > 200 else page.content,
            'image_url': page.image_url,
            'audio_url': page.audio_url,
            'is_required': page.is_required,
            'created_at': page.created_at.isoformat()
        } for page in page_obj]
        
        return Response({
            'book': {
                'id': str(book_material.id),
                'title': book_material.title,
                'description': book_material.description
            },
            'pages': pages_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'per_page': per_page
            }
        }, status=status.HTTP_200_OK)
    
    def _user_has_access(self, user, lesson):
        """Check if user has access to view this lesson"""
        if user.role == 'teacher' and lesson.course.teacher == user:
            return True
        
        if user.role == 'student':
            from student.models import EnrolledCourse
            enrolled = EnrolledCourse.objects.filter(
                student_profile__user=user,
                course=lesson.course,
                status__in=['active', 'completed']
            ).exists()
            return enrolled
        
        return False
    
    def delete(self, request, material_id, page_number):
        """
        DELETE: Delete specific page
        """
        try:
            try:
                book_material = LessonMaterialModel.objects.get(
                    id=material_id, 
                    material_type='book'
                )
            except LessonMaterialModel.DoesNotExist:
                return Response(
                    {'error': 'Book material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                page = BookPage.objects.get(
                    book_material=book_material,
                    page_number=page_number
                )
            except BookPage.DoesNotExist:
                return Response(
                    {'error': f'Page {page_number} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user can modify
            can_modify = any(self._user_can_modify(request.user, lesson) for lesson in book_material.lessons.all())
            if not can_modify:
                return Response(
                    {'error': 'You do not have permission to delete this page'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Delete the page
            page.delete()
            
            return Response({
                'message': f'Page {page_number} deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to delete page: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _user_can_modify(self, user, lesson):
        """Check if user can modify this lesson"""
        return user.role == 'teacher' and lesson.course.teacher == user
