from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from django.utils import timezone
from django.db import models

from .models import EnrolledCourse, LessonAssessment, TeacherAssessment, QuizQuestionFeedback, QuizAttemptFeedback
from courses.models import Class, ClassEvent, Course, Lesson
from settings.models import UserDashboardSettings
from .serializers import (
    EnrolledCourseListSerializer, 
    EnrolledCourseDetailSerializer, 
    EnrolledCourseCreateUpdateSerializer,
    QuizQuestionFeedbackDetailSerializer,
    QuizQuestionFeedbackCreateUpdateSerializer,
    QuizAttemptFeedbackDetailSerializer,
    QuizAttemptFeedbackCreateUpdateSerializer,
    StudentFeedbackOverviewSerializer,
    StudentScheduleSerializer,
    # Dashboard Overview Serializers
    DashboardStatisticsSerializer,
    AudioVideoLessonSerializer,
    LiveLessonSerializer,
    TextLessonSerializer,
    InteractiveLessonSerializer,
    AchievementSerializer,
    DashboardOverviewSerializer
)


class StudentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def enrolled_courses(request):
    """
    GET: List enrolled courses (filtered by user role)
    POST: Create new enrollment (teachers/admins only)
    """
    if request.method == 'GET':
        try:
            # Filter based on user role
            if request.user.role == 'student':
                enrollments = EnrolledCourse.objects.filter(
                    student_profile__user=request.user
                ).order_by('-enrollment_date')
            elif request.user.role == 'teacher':
                enrollments = EnrolledCourse.objects.filter(
                    course__teacher=request.user
                ).order_by('-enrollment_date')
            else:
                enrollments = EnrolledCourse.objects.all().order_by('-enrollment_date')
            
            paginator = StudentPagination()
            page = paginator.paginate_queryset(enrollments, request)
            
            if page is not None:
                serializer = EnrolledCourseListSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = EnrolledCourseListSerializer(enrollments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch enrolled courses', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        if request.user.role not in ['teacher', 'admin']:
            return Response(
                {'error': 'Only teachers and admins can create enrollments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            serializer = EnrolledCourseCreateUpdateSerializer(
                data=request.data,
                context={'request': request}
            )
            if serializer.is_valid():
                enrollment = serializer.save(enrolled_by=request.user)
                response_serializer = EnrolledCourseDetailSerializer(enrollment)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to create enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def enrolled_course_detail(request, enrollment_id):
    """
    GET: Retrieve enrollment details
    PUT: Update enrollment
    DELETE: Delete enrollment
    """
    try:
        if request.user.role == 'student':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                student_profile__user=request.user
            )
        elif request.user.role == 'teacher':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                course__teacher=request.user
            )
        else:
            enrollment = get_object_or_404(EnrolledCourse, id=enrollment_id)
    except Exception:
        return Response(
            {'error': 'Enrollment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            serializer = EnrolledCourseDetailSerializer(enrollment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch enrollment details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        if request.user.role not in ['teacher', 'admin']:
            return Response(
                {'error': 'Only teachers and admins can update enrollments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            serializer = EnrolledCourseCreateUpdateSerializer(
                enrollment, 
                data=request.data, 
                context={'request': request},
                partial=True
            )
            if serializer.is_valid():
                updated_enrollment = serializer.save()
                response_serializer = EnrolledCourseDetailSerializer(updated_enrollment)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        if request.user.role not in ['teacher', 'admin']:
            return Response(
                {'error': 'Only teachers and admins can delete enrollments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            enrollment.delete()
            return Response(
                {'message': 'Enrollment deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def lesson_assessments(request, enrollment_id):
    """
    GET: List lesson assessments for a specific enrollment
    POST: Create new lesson assessment
    """
    try:
        # Get enrollment and verify access
        if request.user.role == 'student':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                student_profile__user=request.user
            )
        elif request.user.role == 'teacher':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                course__teacher=request.user
            )
        else:
            enrollment = get_object_or_404(EnrolledCourse, id=enrollment_id)
    except Exception:
        return Response(
            {'error': 'Enrollment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            assessments = LessonAssessment.objects.filter(enrollment=enrollment).order_by('-created_at')
            data = []
            for assessment in assessments:
                data.append({
                    'id': assessment.id,
                    'title': assessment.title,
                    'content': assessment.content,
                    'assessment_type': assessment.assessment_type,
                    'lesson_title': assessment.lesson.title,
                    'teacher_name': assessment.teacher.get_full_name(),
                    'created_at': assessment.created_at,
                    'quiz_attempt_id': assessment.quiz_attempt.id if assessment.quiz_attempt else None
                })
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch lesson assessments', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can create lesson assessments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Create lesson assessment
            assessment = LessonAssessment.objects.create(
                enrollment=enrollment,
                lesson_id=request.data.get('lesson_id'),
                teacher=request.user,
                title=request.data.get('title', ''),
                content=request.data.get('content', ''),
                assessment_type=request.data.get('assessment_type', 'general'),
                quiz_attempt_id=request.data.get('quiz_attempt_id')
            )
            
            # Update enrollment metrics
            enrollment.update_assessment_metrics('lesson')
            
            return Response({
                'id': assessment.id,
                'message': 'Lesson assessment created successfully'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': 'Failed to create lesson assessment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def teacher_assessments(request, enrollment_id):
    """
    GET: List teacher assessments for a specific enrollment
    POST: Create new teacher assessment
    """
    try:
        # Get enrollment and verify access
        if request.user.role == 'student':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                student_profile__user=request.user
            )
        elif request.user.role == 'teacher':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                course__teacher=request.user
            )
        else:
            enrollment = get_object_or_404(EnrolledCourse, id=enrollment_id)
    except Exception:
        return Response(
            {'error': 'Enrollment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            assessments = TeacherAssessment.objects.filter(enrollment=enrollment).order_by('-created_at')
            data = []
            for assessment in assessments:
                data.append({
                    'id': assessment.id,
                    'academic_performance': assessment.academic_performance,
                    'participation_level': assessment.participation_level,
                    'strengths': assessment.strengths,
                    'weaknesses': assessment.weaknesses,
                    'recommendations': assessment.recommendations,
                    'general_comments': assessment.general_comments,
                    'teacher_name': assessment.teacher.get_full_name(),
                    'created_at': assessment.created_at
                })
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch teacher assessments', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can create teacher assessments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Create teacher assessment
            assessment = TeacherAssessment.objects.create(
                enrollment=enrollment,
                teacher=request.user,
                academic_performance=request.data.get('academic_performance', 'satisfactory'),
                participation_level=request.data.get('participation_level', 'moderate'),
                strengths=request.data.get('strengths', ''),
                weaknesses=request.data.get('weaknesses', ''),
                recommendations=request.data.get('recommendations', ''),
                general_comments=request.data.get('general_comments', '')
            )
            
            # Update enrollment metrics
            enrollment.update_assessment_metrics('teacher')
            
            return Response({
                'id': assessment.id,
                'message': 'Teacher assessment created successfully'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': 'Failed to create teacher assessment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def student_assessments_overview(request, student_id):
    """
    GET: Get all assessments for a specific student across all courses
    """
    try:
        print(f"🔍 ...............student_assessments_overview called with student_id: {student_id}..................")
        print(f"🔍 ...............User role: {request.user.role}..................")
        
        if request.user.role == 'student':
            if request.user.student_profile.id != student_id:
                return Response(
                    {'error': 'You can only view your own assessments'},
                    status=status.HTTP_403_FORBIDDEN
                )
            enrollments = EnrolledCourse.objects.filter(
                student_profile__user=request.user
            )
        elif request.user.role == 'teacher':
            enrollments = EnrolledCourse.objects.filter(
                student_profile__user_id=student_id,
                course__teacher=request.user
            )
        else:
            enrollments = EnrolledCourse.objects.filter(student_profile__user_id=student_id)
        
        print(f"🔍 ...............Found {enrollments.count()} enrollments..................")
        
        if not enrollments.exists():
            return Response(
                {'error': 'No enrollments found for this student'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all assessments for this student
        lesson_assessments = LessonAssessment.objects.filter(
            enrollment__in=enrollments
        ).select_related('enrollment', 'lesson', 'teacher').order_by('-created_at')
        
        teacher_assessments = TeacherAssessment.objects.filter(
            enrollment__in=enrollments
        ).select_related('enrollment', 'teacher').order_by('-created_at')
        
        print(f"🔍 ...............Found {lesson_assessments.count()} lesson assessments..................")
        print(f"🔍 ...............Found {teacher_assessments.count()} teacher assessments..................")
        
        data = {
            'lesson_assessments': [],
            'teacher_assessments': [],
            'total_assessments': lesson_assessments.count() + teacher_assessments.count()
        }
        
        for assessment in lesson_assessments:
            data['lesson_assessments'].append({
                'id': assessment.id,
                'title': assessment.title,
                'content': assessment.content,
                'assessment_type': assessment.assessment_type,
                'lesson_title': assessment.lesson.title,
                'course_title': assessment.enrollment.course.title,
                'teacher_name': assessment.teacher.get_full_name(),
                'created_at': assessment.created_at
            })
        
        for assessment in teacher_assessments:
            data['teacher_assessments'].append({
                'id': assessment.id,
                'academic_performance': assessment.academic_performance,
                'participation_level': assessment.participation_level,
                'strengths': assessment.strengths,
                'weaknesses': assessment.weaknesses,
                'recommendations': assessment.recommendations,
                'general_comments': assessment.general_comments,
                'course_title': assessment.enrollment.course.title,
                'teacher_name': assessment.teacher.get_full_name(),
                'created_at': assessment.created_at
            })
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch student assessments overview', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_lesson_assessment_direct(request):
    """
    POST: Create lesson assessment directly using student_id, course_id, and lesson_id
    This bypasses the need to know the enrollment ID upfront
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can create lesson assessments'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        student_id = request.data.get('student_id')
        course_id = request.data.get('course_id')
        lesson_id = request.data.get('lesson_id')
        
        if not all([student_id, course_id, lesson_id]):
            return Response(
                {'error': 'Missing required fields: student_id, course_id, lesson_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find the enrollment for this student and course
        try:
            # The student_id is actually the User ID, so we need to find StudentProfile by user_id
            from users.models import StudentProfile
            student_profile = StudentProfile.objects.get(user_id=student_id)
            
            enrollment = EnrolledCourse.objects.get(
                student_profile=student_profile,
                course_id=course_id
            )
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': f'StudentProfile with user_id {student_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except EnrolledCourse.DoesNotExist:
            return Response(
                {'error': 'No enrollment found for this student and course'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify the teacher has access to this course
        if enrollment.course.teacher != request.user:
            return Response(
                {'error': 'You do not have access to this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create lesson assessment
        assessment = LessonAssessment.objects.create(
            enrollment=enrollment,
            lesson_id=lesson_id,
            teacher=request.user,
            title=request.data.get('title', ''),
            content=request.data.get('content', ''),
            assessment_type=request.data.get('assessment_type', 'general'),
            quiz_attempt_id=request.data.get('quiz_attempt_id')
        )
        
        # Update enrollment metrics
        enrollment.update_assessment_metrics('lesson')
        
        return Response({
            'id': assessment.id,
            'message': 'Lesson assessment created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to create lesson assessment', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_teacher_assessment_direct(request):
    """
    POST: Create teacher assessment directly using student_id and course_id
    This bypasses the need to know the enrollment ID upfront
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can create teacher assessments'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        student_id = request.data.get('student_id')
        course_id = request.data.get('course_id')
        
        if not all([student_id, course_id]):
            return Response(
                {'error': 'Missing required fields: student_id, course_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find the enrollment for this student and course
        try:
            # The student_id is actually the User ID, so we need to find StudentProfile by user_id
            from users.models import StudentProfile
            student_profile = StudentProfile.objects.get(user_id=student_id)
            
            enrollment = EnrolledCourse.objects.get(
                student_profile=student_profile,
                course_id=course_id
            )
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': f'StudentProfile with user_id {student_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except EnrolledCourse.DoesNotExist:
            return Response(
                {'error': 'No enrollment found for this student and course'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify the teacher has access to this course
        if enrollment.course.teacher != request.user:
            return Response(
                {'error': 'You do not have access to this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create teacher assessment
        assessment = TeacherAssessment.objects.create(
            enrollment=enrollment,
            teacher=request.user,
            academic_performance=request.data.get('academic_performance', 'satisfactory'),
            participation_level=request.data.get('participation_level', 'moderate'),
            strengths=request.data.get('strengths', ''),
            weaknesses=request.data.get('weaknesses', ''),
            recommendations=request.data.get('recommendations', ''),
            general_comments=request.data.get('general_comments', '')
        )
        
        # Update enrollment metrics
        enrollment.update_assessment_metrics('teacher')
        
        return Response({
            'id': assessment.id,
            'message': 'Teacher assessment created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to create teacher assessment', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_teacher_assessment(request, assessment_id):
    """
    PUT: Update an existing teacher assessment
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can update teacher assessments'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get the assessment and verify ownership
        assessment = TeacherAssessment.objects.get(id=assessment_id)
        
        # Verify the teacher owns this assessment
        if assessment.teacher != request.user:
            return Response(
                {'error': 'You can only update your own assessments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update the assessment
        assessment.academic_performance = request.data.get('academic_performance', assessment.academic_performance)
        assessment.participation_level = request.data.get('participation_level', assessment.participation_level)
        assessment.strengths = request.data.get('strengths', assessment.strengths)
        assessment.weaknesses = request.data.get('weaknesses', assessment.weaknesses)
        assessment.recommendations = request.data.get('recommendations', assessment.recommendations)
        assessment.general_comments = request.data.get('general_comments', assessment.general_comments)
        assessment.save()
        
        return Response({
            'id': assessment.id,
            'message': 'Teacher assessment updated successfully'
        }, status=status.HTTP_200_OK)
        
    except TeacherAssessment.DoesNotExist:
        return Response(
            {'error': 'Assessment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to update teacher assessment', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_lesson_assessment(request, assessment_id):
    """
    PUT: Update an existing lesson assessment
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can update lesson assessments'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get the assessment and verify ownership
        assessment = LessonAssessment.objects.get(id=assessment_id)
        
        # Verify the teacher owns this assessment
        if assessment.teacher != request.user:
            return Response(
                {'error': 'You can only update your own assessments'},
                status=status.HTTP_403_FORBIDDEN
        )
        
        # Update the assessment
        assessment.title = request.data.get('title', assessment.title)
        assessment.content = request.data.get('content', assessment.content)
        assessment.assessment_type = request.data.get('assessment_type', assessment.assessment_type)
        assessment.save()
        
        return Response({
            'id': assessment.id,
            'message': 'Lesson assessment updated successfully'
        }, status=status.HTTP_200_OK)
        
    except LessonAssessment.DoesNotExist:
        return Response(
            {'error': 'Assessment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to update lesson assessment', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def quiz_question_feedback(request, quiz_attempt_id, question_id):
    """
    GET: Retrieve feedback for a specific question in a quiz attempt
    POST: Create or update feedback for a specific question
    """
    try:
        # Ensure user is a teacher
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can manage question feedback'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the quiz attempt and verify teacher access
        from courses.models import QuizAttempt
        quiz_attempt = get_object_or_404(
            QuizAttempt.objects.select_related('quiz__lesson__course'),
            id=quiz_attempt_id,
            quiz__lesson__course__teacher=request.user
        )
        
        # Get the question
        from courses.models import Question
        question = get_object_or_404(Question, id=question_id, quiz=quiz_attempt.quiz)
        
        if request.method == 'GET':
            # Retrieve existing feedback
            try:
                feedback = QuizQuestionFeedback.objects.get(
                    quiz_attempt=quiz_attempt,
                    question=question,
                    teacher=request.user
                )
                
                serializer = QuizQuestionFeedbackDetailSerializer(feedback)
                return Response(serializer.data, status=status.HTTP_200_OK)
                
            except QuizQuestionFeedback.DoesNotExist:
                return Response({
                    'feedback_text': '',
                    'points_earned': None,
                    'points_possible': question.points,
                    'is_correct': None
                }, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            # Use serializer for data validation and creation/update
            serializer = QuizQuestionFeedbackCreateUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Get or create feedback
            feedback, created = QuizQuestionFeedback.objects.get_or_create(
                quiz_attempt=quiz_attempt,
                question=question,
                teacher=request.user,
                defaults=serializer.validated_data
            )
            
            if not created:
                # Update existing feedback
                for field, value in serializer.validated_data.items():
                    setattr(feedback, field, value)
                feedback.save()
            
            # Return the updated feedback using detail serializer
            response_serializer = QuizQuestionFeedbackDetailSerializer(feedback)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
    
    except Exception as e:
        return Response(
            {'error': 'Failed to manage question feedback', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def quiz_attempt_feedback(request, quiz_attempt_id):
    """
    GET: Retrieve overall feedback for a quiz attempt
    POST: Create or update overall feedback for a quiz attempt
    """
    try:
        # Ensure user is a teacher
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can manage quiz attempt feedback'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the quiz attempt and verify teacher access
        from courses.models import QuizAttempt
        quiz_attempt = get_object_or_404(
            QuizAttempt.objects.select_related('quiz__lesson__course'),
            id=quiz_attempt_id,
            quiz__lesson__course__teacher=request.user
        )
        
        if request.method == 'GET':
            # Retrieve existing feedback
            try:
                feedback = QuizAttemptFeedback.objects.get(
                    quiz_attempt=quiz_attempt,
                    teacher=request.user
                )
                
                serializer = QuizAttemptFeedbackDetailSerializer(feedback)
                return Response(serializer.data, status=status.HTTP_200_OK)
                
            except QuizAttemptFeedback.DoesNotExist:
                return Response({
                    'feedback_text': '',
                    'overall_rating': None,
                    'strengths_highlighted': '',
                    'areas_for_improvement': '',
                    'study_recommendations': '',
                    'private_notes': ''
                }, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            # Use serializer for data validation and creation/update
            serializer = QuizAttemptFeedbackCreateUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Get or create feedback
            feedback, created = QuizAttemptFeedback.objects.get_or_create(
                quiz_attempt=quiz_attempt,
                teacher=request.user,
                defaults=serializer.validated_data
            )
            
            if not created:
                # Update existing feedback
                for field, value in serializer.validated_data.items():
                    setattr(feedback, field, value)
                feedback.save()
            
            # Return the updated feedback using detail serializer
            response_serializer = QuizAttemptFeedbackDetailSerializer(feedback)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
    
    except Exception as e:
        return Response(
            {'error': 'Failed to manage quiz attempt feedback', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def student_feedback_overview(request, student_id):
    """
    GET: Retrieve all feedback for a specific student across all assessments
    """
    try:
        # Ensure user is a teacher
        if request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can view student feedback'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get student profile and verify teacher access
        from users.models import StudentProfile
        student_profile = get_object_or_404(StudentProfile, user_id=student_id)
        
        # Get enrollments for courses taught by this teacher
        enrollments = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course__teacher=request.user
        )
        
        if not enrollments.exists():
            return Response(
                {'error': 'No enrollments found for this student in your courses'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all feedback for this student
        question_feedbacks = QuizQuestionFeedback.objects.filter(
            quiz_attempt__enrollment__in=enrollments
        ).select_related('quiz_attempt__quiz__lesson', 'teacher').order_by('-created_at')
        
        attempt_feedbacks = QuizAttemptFeedback.objects.filter(
            quiz_attempt__enrollment__in=enrollments
        ).select_related('quiz_attempt__quiz__lesson', 'teacher').order_by('-created_at')
        
        # Use serializer for consistent data formatting
        data = {
            'question_feedbacks': QuizQuestionFeedbackListSerializer(question_feedbacks, many=True).data,
            'attempt_feedbacks': QuizAttemptFeedbackListSerializer(attempt_feedbacks, many=True).data,
            'total_feedbacks': question_feedbacks.count() + attempt_feedbacks.count()
        }
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch student feedback overview', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class TeacherStudentRecord(APIView):
    """
    Class-based view that returns complete student record for teacher management
    Consolidates all student data into a single, organized response
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, student_id):
        """
        GET: Retrieve complete student record for teacher management
        """
        try:
            # Verify user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access student records'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get course filter from query params
            course_id = request.GET.get('course_id')
            
            # Get student profile
            from users.models import StudentProfile
            student_profile = get_object_or_404(StudentProfile, user_id=student_id)
            
            # Get enrollments (filtered by course if specified)
            if course_id:
                enrollments = EnrolledCourse.objects.filter(
                    student_profile__user_id=student_id,
                    course__teacher=request.user,
                    course_id=course_id
                )
            else:
                enrollments = EnrolledCourse.objects.filter(
                    student_profile__user_id=student_id,
                    course__teacher=request.user
                )
            
            if not enrollments.exists():
                return Response(
                    {'error': 'No enrollments found for this student in your courses'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Build complete student record
            student_record = {
                'basic_info': self.get_student_basic_info(student_profile, enrollments.first()),
                'performance_metrics': self.get_performance_metrics(enrollments.first()),
                'teacher_assessments': self.get_teacher_assessments(enrollments),
                'lesson_assessments': self.get_lesson_assessments(enrollments),
                'quiz_overview': self.get_quiz_overview(enrollments),
                'course_progress': self.get_course_progress(enrollments.first())
            }
            
            return Response(student_record, status=status.HTTP_200_OK)
            
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch student record', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_student_basic_info(self, student_profile, enrollment):
        """Get basic student information"""
        user = student_profile.user
        return {
            'id': str(user.id),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name(),
            'email': user.email,
            'grade_level': student_profile.grade_level,
            'enrollment_date': enrollment.enrollment_date.isoformat() if enrollment else None,
            'child_first_name': student_profile.child_first_name,
            'child_last_name': student_profile.child_last_name
        }
    
    def get_performance_metrics(self, enrollment):
        """Get performance metrics for the student"""
        if not enrollment:
            return {}
        
        return {
            'progress_percentage': float(enrollment.progress_percentage),
            'overall_grade': enrollment.overall_grade,
            'average_quiz_score': float(enrollment.average_quiz_score) if enrollment.average_quiz_score else None,
            'is_at_risk': enrollment.is_at_risk,
            'completed_lessons_count': enrollment.completed_lessons_count,
            'total_lessons_count': enrollment.total_lessons_count,
            'last_accessed': enrollment.last_accessed.isoformat() if enrollment.last_accessed else None
        }
    
    def get_teacher_assessments(self, enrollments):
        """Get all teacher assessments for the student"""
        assessments = TeacherAssessment.objects.filter(
            enrollment__in=enrollments
        ).select_related('enrollment', 'teacher').order_by('-created_at')
        
        return [{
            'id': assessment.id,
            'academic_performance': assessment.academic_performance,
            'participation_level': assessment.participation_level,
            'strengths': assessment.strengths,
            'weaknesses': assessment.weaknesses,
            'recommendations': assessment.recommendations,
            'general_comments': assessment.general_comments,
            'course_title': assessment.enrollment.course.title,
            'teacher_name': assessment.teacher.get_full_name(),
            'created_at': assessment.created_at.isoformat()
        } for assessment in assessments]
    
    def get_lesson_assessments(self, enrollments):
        """Get all lesson assessments for the student"""
        assessments = LessonAssessment.objects.filter(
            enrollment__in=enrollments
        ).select_related('enrollment', 'lesson', 'teacher').order_by('-created_at')
        
        return [{
            'id': assessment.id,
            'title': assessment.title,
            'content': assessment.content,
            'assessment_type': assessment.assessment_type,
            'lesson_title': assessment.lesson.title,
            'course_title': assessment.enrollment.course.title,
            'teacher_name': assessment.teacher.get_full_name(),
            'created_at': assessment.created_at.isoformat()
        } for assessment in assessments]
    
    def get_quiz_overview(self, enrollments):
        """Get quiz overview data for the student"""
        from courses.models import QuizAttempt
        attempts = QuizAttempt.objects.filter(
            enrollment__in=enrollments
        ).select_related('quiz', 'quiz__lesson').order_by('-completed_at')
        
        return [{
            'id': attempt.id,
            'quiz_title': attempt.quiz.title,
            'lesson_title': attempt.quiz.lesson.title,
            'course_title': attempt.enrollment.course.title,
            'score': attempt.score,
            'passed': attempt.passed,
            'completed_at': attempt.completed_at.isoformat(),
            'attempt_number': attempt.attempt_number
        } for attempt in attempts]
    
    def get_course_progress(self, enrollment):
        """Get course progress for the student"""
        if not enrollment:
            return {}
        
        return {
            'course_id': str(enrollment.course.id),
            'course_title': enrollment.course.title,
            'current_lesson_id': str(enrollment.current_lesson.id) if enrollment.current_lesson else None,
            'current_lesson_title': enrollment.current_lesson.title if enrollment.current_lesson else None,
            'progress_percentage': float(enrollment.progress_percentage),
            'completed_lessons_count': enrollment.completed_lessons_count,
            'total_lessons_count': enrollment.total_lessons_count
        }


class StudentScheduleView(APIView):
    """
    Get student's complete schedule with all enrolled courses, classes, and events
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        GET: Retrieve student's complete schedule
        """
        try:
            # Step 1: Validate user is a student
            if request.user.role != 'student':
                return Response(
                    {'error': 'Only students can access their schedule'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Step 2: Get student's enrolled courses
            try:
                enrollments = EnrolledCourse.objects.filter(
                    student_profile__user=request.user,
                    status='active'
                ).select_related('course', 'student_profile')
                
                if not enrollments.exists():
                    return Response({
                        'classes': [],
                        'total_events': 0,
                        'date_range': {'start': None, 'end': None},
                        'summary': {'total_courses': 0, 'total_classes': 0}
                    }, status=status.HTTP_200_OK)
                    
            except Exception as e:
                print(f"❌ Error fetching enrolled courses: {str(e)}")
                return Response(
                    {'error': 'Failed to fetch enrolled courses', 'details': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Step 3: Get classes for each enrolled course
            try:
                
                classes_with_events = []
                color_palette = [
                    {'bg': '#3B82F6', 'border': '#2563EB', 'text': '#FFFFFF'},  # Blue
                    {'bg': '#10B981', 'border': '#059669', 'text': '#FFFFFF'},  # Green
                    {'bg': '#F59E0B', 'border': '#D97706', 'text': '#FFFFFF'},  # Amber
                    {'bg': '#EF4444', 'border': '#DC2626', 'text': '#FFFFFF'},  # Red
                    {'bg': '#8B5CF6', 'border': '#7C3AED', 'text': '#FFFFFF'},  # Purple
                    {'bg': '#06B6D4', 'border': '#0891B2', 'text': '#FFFFFF'},  # Cyan
                    {'bg': '#F97316', 'border': '#EA580C', 'text': '#FFFFFF'},  # Orange
                    {'bg': '#EC4899', 'border': '#DB2777', 'text': '#FFFFFF'},  # Pink
                ]
                
                total_events = 0
                all_event_dates = []
                
                for index, enrollment in enumerate(enrollments):
                    try:
                        # Get classes for this course
                        classes = Class.objects.filter(
                            course=enrollment.course,
                            is_active=True
                        ).select_related('course')
                        
                        for class_instance in classes:
                            try:
                                # Get events for this class
                                events = ClassEvent.objects.filter(
                                    class_instance=class_instance,
                                    start_time__gte=timezone.now() - timezone.timedelta(days=7)  # Show events from 7 days ago
                                ).select_related('lesson').order_by('start_time')
                                
                                if events.exists():
                                    # Assign color to this class
                                    color_index = (index + len(classes_with_events)) % len(color_palette)
                                    colors = color_palette[color_index]
                                    
                                    # Convert events to schedule format
                                    schedule_events = []
                                    for event in events:
                                        try:
                                            schedule_event = {
                                                'id': str(event.id),
                                                'title': event.title,
                                                'start': event.start_time.isoformat(),
                                                'end': event.end_time.isoformat(),
                                                'description': event.description or '',
                                                'event_type': event.event_type,
                                                'meeting_platform': event.meeting_platform,
                                                'meeting_link': event.meeting_link,
                                                'meeting_id': event.meeting_id,
                                                'meeting_password': event.meeting_password,
                                                'backgroundColor': colors['bg'],
                                                'borderColor': colors['border'],
                                                'textColor': colors['text'],
                                            }
                                            schedule_events.append(schedule_event)
                                            total_events += 1
                                            all_event_dates.extend([event.start_time, event.end_time])
                                            
                                        except Exception as e:
                                            continue
                                    
                                    # Add class with events
                                    class_with_events = {
                                        'id': str(class_instance.id),
                                        'name': class_instance.name,
                                        'course_name': class_instance.course.title,
                                        'color': colors['bg'],
                                        'events': schedule_events
                                    }
                                    classes_with_events.append(class_with_events)
                                    
                            except Exception as e:
                                continue
                                
                    except Exception as e:
                        continue
                
            except Exception as e:
                return Response(
                    {'error': 'Failed to fetch classes and events', 'details': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Step 4: Calculate date range and summary
            try:
                date_range = {'start': None, 'end': None}
                if all_event_dates:
                    date_range = {
                        'start': min(all_event_dates).isoformat(),
                        'end': max(all_event_dates).isoformat()
                    }
                
                summary = {
                    'total_courses': enrollments.count(),
                    'total_classes': len(classes_with_events),
                    'total_events': total_events
                }
                
            except Exception as e:
                date_range = {'start': None, 'end': None}
                summary = {'total_courses': 0, 'total_classes': 0, 'total_events': 0}
            
            # Step 5: Prepare response
            try:
                response_data = {
                    'classes': classes_with_events,
                    'total_events': total_events,
                    'date_range': date_range,
                    'summary': summary
                }
                
                # Validate response with serializer
                serializer = StudentScheduleSerializer(data=response_data)
                if serializer.is_valid():
                    return Response(serializer.data, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {'error': 'Invalid response data format', 'details': serializer.errors},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                    
            except Exception as e:
                return Response(
                    {'error': 'Failed to prepare response', 'details': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
                            return Response(
                    {'error': 'An unexpected error occurred', 'details': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


class DashboardOverview(APIView):
    """
    Class-Based View for Dashboard Overview
    Provides comprehensive data for the student dashboard overview page
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_user_settings(self, user):
        """
        Get user's dashboard settings from database
        Returns default settings if none exist
        """
        try:
            settings = UserDashboardSettings.get_or_create_settings(user)
            return settings.get_dashboard_config()
        except Exception as e:
            print(f"🔍 DEBUG: Error getting user settings: {str(e)}")
            # Return default settings if there's an error
            return {
                'live_lessons_limit': 3,
                'continue_learning_limit': 25,
                'show_today_only': False,
                'theme_preference': 'auto',
                'notifications_enabled': True,
            }
    
    def get(self, request):
        """
        GET: Retrieve all dashboard overview data
        Returns consolidated data for statistics, lessons, and achievements
        """
        try:
            # Verify user is a student
            if request.user.role != 'student':
                return Response(
                    {'error': 'Only students can access dashboard overview'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student profile
            student_profile = getattr(request.user, 'student_profile', None)
            if not student_profile:
                return Response(
                    {'error': 'Student profile not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get user's dashboard settings
            user_settings = self.get_user_settings(request.user)
            
            # OPTIMIZED: Fetch all data once and reuse
            dashboard_data = self._get_dashboard_data(student_profile)
            
            # Collect all data using the cached data and user settings
            overview_data = {
                'statistics': self._get_statistics_from_data(dashboard_data),
                'continue_learning_lessons': self._get_continue_learning_lessons_from_data(dashboard_data, user_settings),
                'live_lessons': self._get_live_lessons_from_data(dashboard_data, user_settings),
                'recent_achievements': self._get_recent_achievements_from_data(dashboard_data)
            }
            
            return Response(overview_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch dashboard overview', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_dashboard_data(self, student_profile):
        """
        OPTIMIZED: Fetch all dashboard data in a single query set
        Returns a dictionary with all the data needed for dashboard
        """
        try:
            current_time = timezone.now()
            
            # Get all enrollments with related data in one query
            enrollments = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course').prefetch_related(
                'course__lessons'
            )
            
            # Get all class events for enrolled courses in one query
            course_ids = [enrollment.course.id for enrollment in enrollments]
            class_events = ClassEvent.objects.filter(
                class_instance__course_id__in=course_ids
            ).select_related('class_instance', 'lesson')
            
            return {
                'enrollments': enrollments,
                'class_events': class_events,
                'current_time': current_time,
                'student_profile': student_profile
            }
        except Exception as e:
            print(f"🔍 DEBUG: Error in _get_dashboard_data: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
    
    def _get_statistics_from_data(self, dashboard_data):
        """Get statistics from cached dashboard data"""
        enrollments = dashboard_data['enrollments']
        student_profile = dashboard_data['student_profile']
        
        courses_enrolled = enrollments.count()
        
        # Use the new class methods to calculate real statistics
        print(f"🔍 DEBUG: Getting lessons completed for student: {student_profile}")
        lessons_completed = EnrolledCourse.get_total_lessons_completed_for_student(student_profile)
        print(f"🔍 DEBUG: Lessons completed: {lessons_completed}")
        
        print(f"🔍 DEBUG: Getting average quiz score for student: {student_profile}")
        print(f"🔍 DEBUG: Student profile type: {type(student_profile)}")
        print(f"🔍 DEBUG: Student profile: {student_profile}")
        
        # Check if the method exists
        if hasattr(EnrolledCourse, 'get_average_quiz_score_for_student'):
            print(f"🔍 DEBUG: Method exists, calling it...")
            try:
                average_quiz_score = EnrolledCourse.get_average_quiz_score_for_student(student_profile)
                print(f"🔍 DEBUG: Average quiz score calculated: {average_quiz_score}")
            except Exception as e:
                print(f"🔍 DEBUG: Error calculating average quiz score: {str(e)}")
                import traceback
                traceback.print_exc()
                average_quiz_score = 0.0
        else:
            print(f"🔍 DEBUG: Method does not exist!")
            average_quiz_score = 0.0
        
        return {
            'courses_enrolled': courses_enrolled,
            'lessons_completed': lessons_completed,
            'average_quiz_score': average_quiz_score,
            'total_courses': courses_enrolled
        }
    
    def _get_continue_learning_lessons_from_data(self, dashboard_data, user_settings):
        """Get all non-live lessons (text, audio, video, interactive) from cached dashboard data - ONLY from ClassEvent model"""
        enrollments = dashboard_data['enrollments']
        class_events = dashboard_data['class_events']
        current_time = dashboard_data['current_time']
        
        print(f"🔍 DEBUG: Getting continue learning lessons from ClassEvent model only")
        print(f"🔍 DEBUG: Found {enrollments.count()} active enrollments")
        print(f"🔍 DEBUG: Found {class_events.count()} total class events")
        print(f"🔍 DEBUG: Current time: {current_time}")
        
        continue_learning_lessons = []
        
        for enrollment in enrollments:
            print(f"🔍 DEBUG: Processing course: {enrollment.course.title} (ID: {enrollment.course.id})")
            
            # First, let's see ALL class events for this course
            all_course_events = class_events.filter(
                class_instance__course=enrollment.course
            )
            print(f"🔍 DEBUG: Total class events for course {enrollment.course.title}: {all_course_events.count()}")
            
            for event in all_course_events:
                print(f"🔍 DEBUG: - Event: {event.title}, Event Type: {event.event_type}, Lesson Type: {event.lesson_type}, Start: {event.start_time}")
            
            # Configure time filter based on user's SHOW_TODAY_ONLY setting
            if user_settings['show_today_only']:
                # Show only today's events
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                time_filter = {
                    'start_time__gte': today_start,
                    'start_time__lte': today_end
                }
                print(f"🔍 DEBUG: Continue learning - Filtering for TODAY ONLY: {today_start} to {today_end}")
            else:
                # Show all upcoming events
                time_filter = {
                    'start_time__gte': current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                }
                print(f"🔍 DEBUG: Continue learning - Filtering for ALL UPCOMING events from today onwards")
            
            # Get ALL non-live lessons from ClassEvents (scheduled lessons)
            course_events = class_events.filter(
                class_instance__course=enrollment.course,
                event_type='lesson',
                lesson_type__in=['video', 'audio', 'text', 'interactive'],  # All non-live lesson types
                **time_filter
            ).order_by('start_time')[:10]
            
            print(f"🔍 DEBUG: Found {course_events.count()} non-live class events for course {enrollment.course.title}")
            
            for event in course_events:
                print(f"🔍 DEBUG: Processing class event: {event.title} (Type: {event.lesson_type}, Start: {event.start_time})")
                
                # Get actual course lesson count (more reliable than enrollment.total_lessons_count)
                actual_course_lessons = enrollment.course.lessons.count()
                
                # Create lesson data based on event type
                lesson_data = {
                    'id': event.id,
                    'title': event.title,
                    'type': event.lesson_type,
                    'course_title': enrollment.course.title,
                    'course_id': enrollment.course.id,
                    'duration': event.duration_minutes,
                    'media_url': f"/lessons/{event.id}",
                    'description': event.description[:100] + '...' if event.description and len(event.description) > 100 else event.description,
                    'start_time': event.start_time,  # Use actual event start time
                    'progress_percentage': float(enrollment.progress_percentage),  # Get real progress from enrollment
                    # Add course-level enrollment information for progress bar
                    'total_lessons': actual_course_lessons,  # Use actual course lesson count
                    'completed_lessons_count': enrollment.completed_lessons_count
                }
                
                print(f"🔍 DEBUG: Continue Learning Lesson Data: {lesson_data}")
                print(f"🔍 DEBUG: Enrollment data - total_lessons_count: {enrollment.total_lessons_count}, completed_lessons_count: {enrollment.completed_lessons_count}, progress_percentage: {enrollment.progress_percentage}")
                
                # Add interactive_type for interactive lessons
                if event.lesson_type == 'interactive':
                    lesson_data['interactive_type'] = getattr(event, 'interactive_type', 'general')
                
                # Use appropriate serializer based on lesson type
                if event.lesson_type in ['video', 'audio']:
                    serializer = AudioVideoLessonSerializer(data=lesson_data)
                elif event.lesson_type == 'text':
                    serializer = TextLessonSerializer(data=lesson_data)
                elif event.lesson_type == 'interactive':
                    serializer = InteractiveLessonSerializer(data=lesson_data)
                else:
                    print(f"🔍 DEBUG: Unknown lesson type: {event.lesson_type}")
                    continue
                
                if serializer.is_valid():
                    print(f"🔍 DEBUG: {event.lesson_type} lesson added: {event.title}")
                    continue_learning_lessons.append(serializer.data)
                else:
                    print(f"🔍 DEBUG: {event.lesson_type} lesson serializer invalid: {serializer.errors}")
        
        # Sort all lessons by start_time (earliest first)
        continue_learning_lessons.sort(key=lambda x: x.get('start_time', current_time))
        
        print(f"🔍 DEBUG: Final continue learning lessons count: {len(continue_learning_lessons)}")
        print(f"🔍 DEBUG: Lessons sorted by start_time, returning top {min(user_settings['continue_learning_limit'], len(continue_learning_lessons))} lessons")
        
        return continue_learning_lessons[:user_settings['continue_learning_limit']]  # Return user's configured limit
    
    def _get_live_lessons_from_data(self, dashboard_data, user_settings):
        """Get live lessons from cached dashboard data - sorted by time"""
        enrollments = dashboard_data['enrollments']
        class_events = dashboard_data['class_events']
        current_time = dashboard_data['current_time']
        
        print(f"🔍 DEBUG: Getting live lessons from ClassEvent model")
        print(f"🔍 DEBUG: Current time: {current_time}")
        
        live_lessons = []
        
        for enrollment in enrollments:
            print(f"🔍 DEBUG: Processing course for live lessons: {enrollment.course.title}")
            
            # Configure time filter based on user's SHOW_TODAY_ONLY setting
            if user_settings['show_today_only']:
                # Show only today's events
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                time_filter = {
                    'start_time__gte': today_start,
                    'start_time__lte': today_end
                }
                print(f"🔍 DEBUG: Filtering for TODAY ONLY: {today_start} to {today_end}")
            else:
                # Show all upcoming events
                time_filter = {
                    'start_time__gte': current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                }
                print(f"🔍 DEBUG: Filtering for ALL UPCOMING events from today onwards")
            
            # Filter class events for this course
            course_events = class_events.filter(
                class_instance__course=enrollment.course,
                event_type='lesson',
                lesson_type='live',
                **time_filter
            ).order_by('start_time')[:5]  # Get more events per course for better selection
            
            print(f"🔍 DEBUG: Found {course_events.count()} live events for course {enrollment.course.title}")
            
            for event in course_events:
                print(f"🔍 DEBUG: Processing live event: {event.title} (Start: {event.start_time})")
                lesson_data = {
                    'id': event.id,
                    'title': event.title,
                    'course_title': enrollment.course.title,
                    'class_name': event.class_instance.name,
                    'start_time': event.start_time.isoformat(),
                    'end_time': event.end_time.isoformat(),
                    'meeting_platform': event.meeting_platform,
                    'meeting_link': event.meeting_link,
                    'meeting_id': event.meeting_id,
                    'meeting_password': event.meeting_password,
                    'description': event.description
                }
                
                serializer = LiveLessonSerializer(data=lesson_data)
                if serializer.is_valid():
                    print(f"🔍 DEBUG: Live lesson added: {event.title}")
                    live_lessons.append(serializer.data)
                else:
                    print(f"🔍 DEBUG: Live lesson serializer invalid: {serializer.errors}")
        
        # Sort all live lessons by start_time (earliest first)
        live_lessons.sort(key=lambda x: x['start_time'])
        
        print(f"🔍 DEBUG: Final live lessons count: {len(live_lessons)}")
        print(f"🔍 DEBUG: Live lessons sorted by start_time, returning top {min(user_settings['live_lessons_limit'], len(live_lessons))} lessons")
        
        return live_lessons[:user_settings['live_lessons_limit']]  # Return user's configured limit
    

    
    def _get_recent_achievements_from_data(self, dashboard_data):
        """Get recent achievements from cached dashboard data"""
        # Placeholder - would implement achievement logic
        return []
    
    def _get_statistics(self, student_profile):
        """
        Get student statistics (courses enrolled, hours learned, learning streak)
        """
        try:
            # Get enrolled courses
            enrollments = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course')
            
            # Calculate statistics
            courses_enrolled = enrollments.count()
            
            # Calculate hours learned (estimate based on progress)
            total_hours = 0
            for enrollment in enrollments:
                # Estimate 20 hours per course, adjust based on progress
                course_hours = 20
                progress = enrollment.progress_percentage or 0
                completed_hours = (progress / 100) * course_hours
                total_hours += completed_hours
            
            # Calculate learning streak (placeholder for now)
            learning_streak = 0  # TODO: Implement streak calculation
            
            raw_data = {
                'courses_enrolled': courses_enrolled,
                'hours_learned': round(total_hours, 1),
                'learning_streak': learning_streak,
                'total_courses': courses_enrolled
            }
            
            # Validate with DashboardStatisticsSerializer
            serializer = DashboardStatisticsSerializer(data=raw_data)
            if serializer.is_valid():
                return serializer.data
            else:
                # Return fallback data if validation fails
                return self._get_fallback_statistics()
            
        except Exception as e:
            return self._get_fallback_statistics()
    
    def _get_fallback_statistics(self):
        """Fallback statistics when main method fails"""
        return {
            'courses_enrolled': 0,
            'hours_learned': 0,
            'learning_streak': 0,
            'total_courses': 0
        }
    
    def _get_audio_video_lessons(self, student_profile):
        """
        Get audio and video lessons from enrolled courses
        """
        try:
            print(f"🔍 DEBUG: Getting audio/video lessons for student: {student_profile}")
            
            enrollments = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course')
            
            print(f"🔍 DEBUG: Found {enrollments.count()} active enrollments")
            for enrollment in enrollments:
                print(f"🔍 DEBUG: - Course: {enrollment.course.title} (ID: {enrollment.course.id})")
            
            audio_video_lessons = []
            current_time = timezone.now()
            for enrollment in enrollments:
                print(f"🔍 DEBUG: Checking course: {enrollment.course.title}")
                
                # Get ClassEvent objects with only video or audio lesson types (exclude live lessons and past events)
                class_events = ClassEvent.objects.filter(
                    class_instance__course=enrollment.course,
                    event_type='lesson',
                    lesson_type__in=['video', 'audio'],  # Only actual audio/video lessons
                    start_time__gte=current_time  # Only future or current events
                ).select_related('class_instance', 'lesson').order_by('start_time')[:5]  # Limit to 5 per course
                
                print(f"🔍 DEBUG: Found {class_events.count()} audio/video class events for course {enrollment.course.title}")
                
                # Let's also check all class events for this course
                all_events = ClassEvent.objects.filter(
                    class_instance__course=enrollment.course
                )
                print(f"🔍 DEBUG: Total class events for course {enrollment.course.title}: {all_events.count()}")
                
                for event in all_events:
                    print(f"🔍 DEBUG: - Event: {event.title}, Event Type: {event.event_type}, Lesson Type: {event.lesson_type}")
                    print(f"🔍 DEBUG:   Event ID: {event.id}, Start Time: {event.start_time}")
                
                for event in class_events:
                    print(f"🔍 DEBUG: Processing audio/video class event: {event.title}")
                    lesson_data = {
                        'id': event.id,  # UUID field
                        'title': event.title,
                        'type': event.lesson_type,
                        'course_title': enrollment.course.title,
                        'course_id': enrollment.course.id,
                        'duration': event.duration_minutes,
                        'media_url': f"/lessons/{event.id}",  # Route to class event ID for in-app playback
                        'description': event.description[:100] + '...' if event.description and len(event.description) > 100 else event.description
                    }
                    
                    print(f"🔍 DEBUG: Lesson data: {lesson_data}")
                    
                    # Validate with AudioVideoLessonSerializer
                    serializer = AudioVideoLessonSerializer(data=lesson_data)
                    if serializer.is_valid():
                        print(f"🔍 DEBUG: Serializer valid, adding lesson")
                        audio_video_lessons.append(serializer.data)
                    else:
                        print(f"🔍 DEBUG: Serializer invalid: {serializer.errors}")
                        continue
            
            print(f"🔍 DEBUG: Final audio_video_lessons count: {len(audio_video_lessons)}")
            return audio_video_lessons[:10]  # Return top 10
            
        except Exception as e:
            print(f"🔍 DEBUG: Exception in _get_audio_video_lessons: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_live_lessons(self, student_profile):
        """
        Get upcoming live lessons from enrolled courses
        """
        try:
            enrollments = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course')
            
            live_lessons = []
            current_time = timezone.now()
            
            for enrollment in enrollments:
                # Get live lessons from class events (only future events)
                live_events = ClassEvent.objects.filter(
                    class_instance__course=enrollment.course,
                    event_type='lesson',
                    lesson_type='live',
                    start_time__gte=current_time
                ).select_related('class_instance', 'lesson').order_by('start_time')[:3]  # Next 3 upcoming events
                
                for event in live_events:
                    lesson_data = {
                        'id': event.id,
                        'title': event.title,
                        'course_title': enrollment.course.title,
                        'class_name': event.class_instance.name,
                        'start_time': event.start_time.isoformat(),
                        'end_time': event.end_time.isoformat(),
                        'meeting_platform': event.meeting_platform,
                        'meeting_link': event.meeting_link,
                        'meeting_id': event.meeting_id,
                        'meeting_password': event.meeting_password,
                        'description': event.description
                    }
                    
                    # Validate with LiveLessonSerializer
                    serializer = LiveLessonSerializer(data=lesson_data)
                    if serializer.is_valid():
                        live_lessons.append(serializer.data)
                    else:
                        # Skip invalid lessons or log errors
                        continue
            
            return live_lessons[:3]  # Return top 3 upcoming events
            
        except Exception as e:
            return []
    
    def _get_text_lessons(self, student_profile):
        """
        Get text-based lessons from enrolled courses
        """
        try:
            enrollments = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course')
            
            text_lessons = []
            for enrollment in enrollments:
                # Get text lessons
                lessons = enrollment.course.lessons.filter(
                    type='text'
                ).order_by('order')[:5]  # Limit to 5 per course
                
                for lesson in lessons:
                    lesson_data = {
                        'id': lesson.id,
                        'title': lesson.title,
                        'course_title': enrollment.course.title,
                        'course_id': enrollment.course.id,
                        'description': lesson.description[:150] + '...' if lesson.description and len(lesson.description) > 150 else lesson.description
                    }
                    
                    # Validate with TextLessonSerializer
                    serializer = TextLessonSerializer(data=lesson_data)
                    if serializer.is_valid():
                        text_lessons.append(serializer.data)
                    else:
                        # Skip invalid lessons or log errors
                        continue
            
            return text_lessons[:10]  # Return top 10
            
        except Exception as e:
            return []
    
    def _get_interactive_lessons(self, student_profile):
        """
        Get interactive lessons from enrolled courses
        """
        try:
            enrollments = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course')
            
            interactive_lessons = []
            for enrollment in enrollments:
                # Get interactive lessons
                lessons = enrollment.course.lessons.filter(
                    type='interactive'
                ).order_by('order')[:5]  # Limit to 5 per course
                
                for lesson in lessons:
                    lesson_data = {
                        'id': lesson.id,
                        'title': lesson.title,
                        'course_title': enrollment.course.title,
                        'course_id': enrollment.course.id,
                        'description': lesson.description[:150] + '...' if lesson.description and len(lesson.description) > 150 else lesson.description,
                        'interactive_type': getattr(lesson, 'interactive_type', 'general')
                    }
                    
                    # Validate with InteractiveLessonSerializer
                    serializer = InteractiveLessonSerializer(data=lesson_data)
                    if serializer.is_valid():
                        interactive_lessons.append(serializer.data)
                    else:
                        # Skip invalid lessons or log errors
                        continue
            
            return interactive_lessons[:10]  # Return top 10
            
        except Exception as e:
            return []
    
    def _get_recent_achievements(self, student_profile):
        """
        Get recent achievements and milestones
        """
        try:
            enrollments = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course')
            
            achievements = []
            current_time = timezone.now()
            
            for enrollment in enrollments:
                # Course completion achievements
                if enrollment.progress_percentage and enrollment.progress_percentage >= 100:
                    achievement_data = {
                        'type': 'course_completion',
                        'title': f'Completed {enrollment.course.title}',
                        'description': 'Congratulations! You have successfully completed this course.',
                        'achieved_at': enrollment.updated_at.isoformat(),
                        'course_title': enrollment.course.title,
                        'icon': '🎓'
                    }
                    
                    # Validate with AchievementSerializer
                    serializer = AchievementSerializer(data=achievement_data)
                    if serializer.is_valid():
                        achievements.append(serializer.data)
                
                # Progress milestones
                progress = enrollment.progress_percentage or 0
                if progress >= 25 and progress < 50:
                    achievement_data = {
                        'type': 'progress_milestone',
                        'title': 'Quarter Way There!',
                        'description': f'You\'ve completed 25% of {enrollment.course.title}',
                        'achieved_at': enrollment.updated_at.isoformat(),
                        'course_title': enrollment.course.title,
                        'icon': '🚀'
                    }
                    
                    # Validate with AchievementSerializer
                    serializer = AchievementSerializer(data=achievement_data)
                    if serializer.is_valid():
                        achievements.append(serializer.data)
                        
                elif progress >= 50 and progress < 75:
                    achievement_data = {
                        'type': 'progress_milestone',
                        'title': 'Halfway Point!',
                        'description': f'You\'ve completed 50% of {enrollment.course.title}',
                        'achieved_at': enrollment.updated_at.isoformat(),
                        'course_title': enrollment.course.title,
                        'icon': '🎯'
                    }
                    
                    # Validate with AchievementSerializer
                    serializer = AchievementSerializer(data=achievement_data)
                    if serializer.is_valid():
                        achievements.append(serializer.data)
                        
                elif progress >= 75 and progress < 100:
                    achievement_data = {
                        'type': 'progress_milestone',
                        'title': 'Almost There!',
                        'description': f'You\'ve completed 75% of {enrollment.course.title}',
                        'achieved_at': enrollment.updated_at.isoformat(),
                        'course_title': enrollment.course.title,
                        'icon': '🏆'
                    }
                    
                    # Validate with AchievementSerializer
                    serializer = AchievementSerializer(data=achievement_data)
                    if serializer.is_valid():
                        achievements.append(serializer.data)
            
            # Sort by achieved_at (most recent first) and return top 5
            achievements.sort(key=lambda x: x['achieved_at'], reverse=True)
            return achievements[:5]
            
        except Exception as e:
            return []
    

    
    