from django.shortcuts import get_object_or_404
from django.db import models
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import Course, Lesson, Quiz, Question, Note, CourseIntroduction, Class, CourseEnrollment, QuizAttempt
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateUpdateSerializer,
    FrontendCourseSerializer, FeaturedCoursesSerializer,
    LessonListSerializer, LessonDetailSerializer, LessonCreateUpdateSerializer,
    LessonReorderSerializer, QuizListSerializer, QuizDetailSerializer,
    QuizCreateUpdateSerializer, QuestionListSerializer, QuestionDetailSerializer,
    QuestionCreateUpdateSerializer, NoteSerializer, NoteCreateSerializer,
    CourseIntroductionSerializer, CourseIntroductionCreateSerializer, CourseIntroductionDetailSerializer,
    ClassListSerializer, ClassDetailSerializer, ClassCreateUpdateSerializer,
    StudentBasicSerializer, TeacherStudentDetailSerializer, TeacherStudentSummarySerializer
)


class CoursesPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


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
        courses = Course.objects.filter(status='published').select_related('introduction').order_by('-featured', '-created_at')
        
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
    Get detailed course introduction for course details modal
    """
    try:
        course = get_object_or_404(Course, id=course_id, status='published')
        
        # Get or create course introduction
        introduction, created = CourseIntroduction.objects.get_or_create(
            course=course,
            defaults={
                'overview': course.long_description or course.description,
                'learning_objectives': course.features or [],
                'prerequisites': '',
                'duration_weeks': 8,
                'max_students': course.max_students,
                'sessions_per_week': 2,
                'total_projects': 5,
                'value_propositions': [],
                'reviews': []
            }
        )
        
        # Prefetch related reviews
        introduction = CourseIntroduction.objects.select_related('course').prefetch_related('course__reviews').get(id=introduction.id)
        
        serializer = CourseIntroductionDetailSerializer(introduction)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch course introduction', 'details': str(e)},
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
                response_serializer = CourseDetailSerializer(course)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to create course', 'details': str(e)},
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
            
            # Update lesson orders
            for lesson_data in lessons_data:
                lesson_id = lesson_data['id']
                new_order = int(lesson_data['order'])
                
                try:
                    lesson = course.lessons.get(id=lesson_id)
                    lesson.order = new_order
                    lesson.save()
                except Lesson.DoesNotExist:
                    return Response(
                        {'error': f'Lesson with id {lesson_id} not found in this course'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
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
    GET: Get quiz for a specific lesson (if exists)
    POST: Create a new quiz for the lesson
    """
    # Get the lesson and verify teacher ownership
    try:
        lesson = get_object_or_404(Lesson, id=lesson_id)
    except Lesson.DoesNotExist:
        return Response(
            {'error': 'Lesson not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Only the course teacher can manage lesson quizzes
    if lesson.course.teacher != request.user:
        return Response(
            {'error': 'Only the course teacher can manage lesson quizzes'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            # Check if quiz exists for this lesson
            if hasattr(lesson, 'quiz'):
                serializer = QuizDetailSerializer(lesson.quiz)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'message': 'No quiz found for this lesson', 'quiz': None},
                    status=status.HTTP_200_OK
                )
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch quiz', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            # Check if quiz already exists
            if hasattr(lesson, 'quiz'):
                return Response(
                    {'error': 'Quiz already exists for this lesson'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = QuizCreateUpdateSerializer(data=request.data)
            if serializer.is_valid():
                quiz = serializer.save(lesson=lesson)
                response_serializer = QuizDetailSerializer(quiz)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
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
    GET: Get course introduction data
    PUT: Update course introduction data
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
    
    # Get or create introduction
    introduction, created = CourseIntroduction.objects.get_or_create(
        course=course,
        defaults={
            'overview': course.long_description or course.description,
            'learning_objectives': [
                'Visual block-based coding',
                'Game creation', 
                'Problem-solving skills',
                'Interactive storytelling',
                'Animation basics'
            ],
            'prerequisites': 'No prior experience required',
            'duration_weeks': int(course.duration.split()[0]) if course.duration and course.duration.split() else 8,
            'max_students': course.max_students,
            'sessions_per_week': int(course.schedule.split()[0]) if course.schedule and course.schedule.split() else 2,
            'total_projects': 5,
            'value_propositions': [
                {
                    'title': 'Hands-On Learning',
                    'description': 'Interactive projects and real-world applications',
                    'icon': 'play'
                },
                {
                    'title': 'Small Classes',
                    'description': 'Personalized attention for every student',
                    'icon': 'users'
                },
                {
                    'title': 'Certification',
                    'description': 'Recognized completion certificate',
                    'icon': 'award'
                }
            ]
        }
    )
    
    # Always sync with current course data (for existing introductions)
    if not created:
        # Update introduction with current course data
        introduction.overview = course.long_description or course.description
        introduction.max_students = course.max_students
        
        # Parse duration from course.duration (e.g., "8 weeks" -> 8)
        if course.duration and course.duration.split():
            try:
                introduction.duration_weeks = int(course.duration.split()[0])
            except (ValueError, IndexError):
                pass
        
        # Parse sessions from course.schedule (e.g., "2 sessions per week" -> 2)
        if course.schedule and course.schedule.split():
            try:
                introduction.sessions_per_week = int(course.schedule.split()[0])
            except (ValueError, IndexError):
                pass
        
        introduction.save()
    
    if request.method == 'GET':
        try:
            serializer = CourseIntroductionSerializer(introduction)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve course introduction', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        try:
            serializer = CourseIntroductionCreateSerializer(
                introduction,
                data=request.data,
                partial=True
            )
            if serializer.is_valid():
                updated_intro = serializer.save()
                
                # Sync changes back to main course
                try:
                    course = updated_intro.course
                    
                    # Update course fields based on introduction changes
                    if 'overview' in request.data:
                        course.long_description = updated_intro.overview
                    
                    if 'max_students' in request.data:
                        course.max_students = updated_intro.max_students
                    
                    if 'duration_weeks' in request.data:
                        course.duration = f"{updated_intro.duration_weeks} weeks"
                    
                    if 'sessions_per_week' in request.data:
                        course.schedule = f"{updated_intro.sessions_per_week} sessions per week"
                    
                    course.save()
                except Exception as e:
                    # Log error but don't fail the introduction update
                    print(f"Warning: Failed to sync introduction changes to course: {e}")
                
                response_serializer = CourseIntroductionSerializer(updated_intro)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
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
            classes = Class.objects.filter(teacher=request.user).select_related('course', 'teacher').prefetch_related('students').order_by('-created_at')
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
            Class, 
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
        from .models import ClassEvent
        from .serializers import ClassEventListSerializer, ClassEventCreateUpdateSerializer, ClassEventDetailSerializer
        
        # Verify the class belongs to the teacher
        class_instance = get_object_or_404(Class, id=class_id, teacher=request.user)
        
        if request.method == 'GET':
            events = ClassEvent.objects.filter(class_instance=class_instance).select_related('lesson').order_by('start_time')
            serializer = ClassEventListSerializer(events, many=True)
            return Response({
                'class_id': class_id,
                'class_name': class_instance.name,
                'events': serializer.data
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
            
            # Separate graded and ungraded attempts
            # Check if there's a corresponding StudentGrade record
            from student.models import StudentGrade
            
            ungraded_attempts = []
            graded_attempts = []
            
            for attempt in quiz_attempts:
                # Check if this attempt has been graded
                has_grade = StudentGrade.objects.filter(
                    quiz_attempt=attempt,
                    grade_type='quiz'
                ).exists()
                
                attempt_data = {
                    'id': attempt.id,
                    'student_id': attempt.student.id,
                    'student_name': attempt.student.get_full_name(),
                    'student_email': attempt.student.email,
                    'submitted_at': attempt.completed_at,
                    'time_spent': None,  # Calculate from started_at to completed_at
                    'score': attempt.score,
                    'points_earned': attempt.points_earned,
                    'passed': attempt.passed,
                    'answers': attempt.answers,
                    'attempt_number': attempt.attempt_number
                }
                
                # Calculate time spent
                if attempt.started_at and attempt.completed_at:
                    time_diff = attempt.completed_at - attempt.started_at
                    attempt_data['time_spent'] = int(time_diff.total_seconds() / 60)  # minutes
                
                if has_grade:
                    # Get the grade details
                    grade = StudentGrade.objects.get(quiz_attempt=attempt, grade_type='quiz')
                    attempt_data.update({
                        'teacher_grade': {
                            'percentage': float(grade.percentage),
                            'letter_grade': grade.letter_grade,
                            'points_earned': float(grade.points_earned),
                            'points_possible': float(grade.points_possible),
                            'teacher_comments': grade.teacher_comments,
                            'graded_date': grade.graded_date,
                            'graded_by': grade.graded_by.get_full_name()
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
        
        # Check if this attempt has been graded
        from student.models import StudentGrade
        grade = None
        graded_questions_dict = {}
        
        try:
            grade = StudentGrade.objects.get(quiz_attempt=attempt, grade_type='quiz')
            # Convert graded_questions list to dict for easy lookup
            for gq in grade.graded_questions:
                graded_questions_dict[str(gq.get('question_id'))] = gq
        except StudentGrade.DoesNotExist:
            pass
        
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
                'id': grade.id if grade else None,
                'percentage': float(grade.percentage) if grade else None,
                'letter_grade': grade.letter_grade if grade else None,
                'teacher_comments': grade.teacher_comments if grade else '',
                'private_notes': grade.private_notes if grade else '',
                'graded_date': grade.graded_date if grade else None,
                'graded_by': grade.graded_by.get_full_name() if grade else None,
                'is_graded': grade is not None
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
        
        # Import StudentGrade model
        from student.models import StudentGrade
        
        # Create or update the grade record
        grade, created = StudentGrade.objects.get_or_create(
            quiz_attempt=attempt,
            grade_type='quiz',
            defaults={
                'student': attempt.student,
                'course': attempt.quiz.lesson.course,
                'lesson': attempt.quiz.lesson,
                'title': f"{attempt.quiz.title} - Attempt {attempt.attempt_number}",
                'description': f"Quiz attempt for {attempt.quiz.lesson.title}",
                'points_earned': data['points_earned'],
                'points_possible': data['points_possible'],
                'percentage': data['percentage'],
                'assigned_date': attempt.started_at.date(),
                'submitted_date': attempt.completed_at,
                'graded_by': request.user,
                'teacher_comments': data.get('teacher_comments', ''),
                'private_notes': data.get('private_notes', ''),
                'graded_questions': graded_questions
            }
        )
        
        if not created:
            # Update existing grade
            grade.points_earned = data['points_earned']
            grade.points_possible = data['points_possible']
            grade.percentage = data['percentage']
            grade.teacher_comments = data.get('teacher_comments', '')
            grade.private_notes = data.get('private_notes', '')
            grade.graded_questions = graded_questions
            grade.graded_by = request.user
            grade.save()
        
        # Update the quiz attempt if needed
        attempt.score = data['percentage']
        attempt.points_earned = data['points_earned']
        attempt.passed = data['percentage'] >= attempt.quiz.passing_score
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
                'id': str(grade.id),  # Convert UUID to string
                'percentage': float(grade.percentage),
                'letter_grade': grade.letter_grade,
                'points_earned': float(grade.points_earned),
                'points_possible': float(grade.points_possible),
                'teacher_comments': grade.teacher_comments,
                'graded_date': grade.graded_date.isoformat() if grade.graded_date else None,  # Convert datetime to ISO string
                'created': created
            },
            'attempt': {
                'id': str(attempt.id),  # Convert UUID to string
                'score': float(attempt.score) if attempt.score else 0,
                'points_earned': attempt.points_earned,
                'passed': attempt.passed
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': 'Failed to save quiz grade', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
