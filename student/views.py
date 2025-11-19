from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from django.utils import timezone
from django.db import models
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta
import uuid

from .models import EnrolledCourse, LessonAssessment, TeacherAssessment, QuizQuestionFeedback, QuizAttemptFeedback, Conversation, Message
from courses.models import Class, ClassEvent, Course, Lesson, Quiz, QuizAttempt, Question, Assignment, AssignmentSubmission
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
    DashboardOverviewSerializer,
    # Assignment Submission Serializers
    AssignmentSubmissionSerializer,
    AssignmentSubmissionResponseSerializer,
    # Messaging Serializers
    ConversationListSerializer, ConversationSerializer,
    MessageSerializer, CreateMessageSerializer
)
from users.models import StudentProfile


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
            QuizAttempt.objects.select_related('quiz').prefetch_related('quiz__lessons__course'),
            id=quiz_attempt_id
        )
        # Check if user teaches any lesson associated with this quiz
        if not quiz_attempt.quiz.lessons.filter(course__teacher=request.user).exists():
            return Response(
                {'error': 'Quiz attempt not found or you do not have permission'},
                status=status.HTTP_403_FORBIDDEN
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
            QuizAttempt.objects.select_related('quiz').prefetch_related('quiz__lessons__course'),
            id=quiz_attempt_id
        )
        # Check if user teaches any lesson associated with this quiz
        if not quiz_attempt.quiz.lessons.filter(course__teacher=request.user).exists():
            return Response(
                {'error': 'Quiz attempt not found or you do not have permission'},
                status=status.HTTP_403_FORBIDDEN
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
        ).select_related('quiz_attempt__quiz', 'teacher').prefetch_related('quiz_attempt__quiz__lessons').order_by('-created_at')
        
        attempt_feedbacks = QuizAttemptFeedback.objects.filter(
            quiz_attempt__enrollment__in=enrollments
        ).select_related('quiz_attempt__quiz', 'teacher').prefetch_related('quiz_attempt__quiz__lessons').order_by('-created_at')
        
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
                'assignment_overview': self.get_assignment_overview(enrollments),
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
            'progress_percentage': round(float(enrollment.progress_percentage), 2),
            'overall_grade': enrollment.overall_grade,
            'average_quiz_score': round(float(enrollment.average_quiz_score), 2) if enrollment.average_quiz_score else None,
            'average_assignment_score': round(float(enrollment.average_assignment_score), 2) if enrollment.average_assignment_score else None,
            'quiz_completion_rate': round(float(enrollment.quiz_completion_rate), 2) if enrollment.quiz_completion_rate else None,
            'assignment_completion_rate': round(float(enrollment.assignment_completion_rate), 2) if enrollment.assignment_completion_rate else None,
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
        ).select_related('quiz').prefetch_related('quiz__lessons').order_by('-completed_at')
        
        return [{
            'id': attempt.id,
            'quiz_title': attempt.quiz.title,
            'lesson_title': attempt.quiz.lessons.first().title if attempt.quiz.lessons.exists() else 'N/A',
            'course_title': attempt.enrollment.course.title,
            'score': attempt.score,
            'passed': attempt.passed,
            'completed_at': attempt.completed_at.isoformat(),
            'attempt_number': attempt.attempt_number
        } for attempt in attempts]
    
    def get_assignment_overview(self, enrollments):
        """Get assignment overview data for the student"""
        from courses.models import AssignmentSubmission
        submissions = AssignmentSubmission.objects.filter(
            enrollment__in=enrollments
        ).exclude(status='draft').select_related('assignment').prefetch_related(
            'assignment__lessons', 'assignment__questions'
        ).order_by('-submitted_at')
        
        assignment_data = []
        for submission in submissions:
            # Get assignment questions
            questions = []
            for question in submission.assignment.questions.all().order_by('order'):
                questions.append({
                    'id': str(question.id),
                    'question_text': question.question_text,
                    'question_type': question.type,
                    'points_possible': float(question.points),
                    'order': question.order,
                    'content': question.content,
                    'explanation': question.explanation,
                    'correct_answer': question.content.get('correct_answer') if question.content else None
                })
            
            # Get student answers for this submission
            student_answers = submission.answers or {}
            
            assignment_data.append({
                'id': submission.id,  # submission ID
                'assignment_id': str(submission.assignment.id),  # assignment ID
                'assignment_title': submission.assignment.title,
                'lesson_title': submission.assignment.lessons.first().title if submission.assignment.lessons.exists() else 'N/A',
                'course_title': submission.enrollment.course.title,
                'assignment_type': submission.assignment.assignment_type,
                'due_date': submission.assignment.due_date.isoformat() if submission.assignment.due_date else None,
                'status': submission.status,  # draft, submitted, graded
                'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
                'points_earned': float(submission.points_earned) if submission.points_earned else None,
                'points_possible': float(submission.points_possible) if submission.points_possible else None,
                'percentage': float(submission.percentage) if submission.percentage else None,
                'passed': submission.passed,
                'is_graded': submission.is_graded,
                'is_teacher_draft': submission.is_teacher_draft,  # Add the missing field
                'attempt_number': submission.attempt_number,
                'graded_at': submission.graded_at.isoformat() if submission.graded_at else None,
                'graded_by': submission.grader_name if submission.graded_by else None,
                'instructor_feedback': submission.instructor_feedback,
                'feedback_checked': submission.feedback_checked,
                # Add detailed grading data
                'questions': questions,
                'student_answers': student_answers,
                'total_points_possible': sum(q['points_possible'] for q in questions),
                'graded_questions': submission.graded_questions or []
            })
        
        return assignment_data
    
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
            
            # Filter continue learning lessons by date only (not time)
            # Since these are not live classes, students can access them anytime during the day
            # Use date-only comparison to avoid timezone issues
            # IMPORTANT: We need to compare dates correctly - exclude past dates (yesterday and earlier)
            # Django's __date lookup extracts date in database timezone (UTC), so we compare UTC dates
            base_filter = {
                'class_instance__course': enrollment.course,
                'event_type': 'lesson',
                'lesson_type__in': ['video', 'audio', 'text', 'interactive']
            }
            
            # Get today's date in UTC (since Django stores datetimes in UTC)
            # This ensures we're comparing dates correctly
            today_date = current_time.date()
            
            if user_settings['show_today_only']:
                # Show all lessons scheduled for today (date match only, regardless of time)
                # Use date comparison: extract date from start_time and compare
                time_filter = {
                    'start_time__date': today_date
                }
                print(f"🔍 DEBUG: Continue learning - Filtering for TODAY ONLY (date={today_date}, current_time={current_time}, time-independent)")
            else:
                # Show all lessons from today onwards (date comparison only)
                # CRITICAL: Exclude past dates - only show today and future dates
                # Use date comparison: start_time date >= today's date
                # This ensures lessons from yesterday (Nov 19) don't show if today is Nov 20
                time_filter = {
                    'start_time__date__gte': today_date
                }
                print(f"🔍 DEBUG: Continue learning - Filtering for ALL UPCOMING lessons (date>={today_date}, current_time={current_time}, excludes past dates)")
            
            # Get ALL non-live lessons from ClassEvents (scheduled lessons)
            course_events = class_events.filter(
                **base_filter,
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
            
            # Filter to only show upcoming/ongoing events (not past events)
            # Use end_time__gt to include events that haven't ended yet
            # This matches the parent dashboard filtering approach (line 3286)
            base_filter = {
                'class_instance__course': enrollment.course,
                'event_type': 'lesson',
                'lesson_type': 'live'
            }
            
            # Always filter by end_time > current_time to exclude past events
            # This ensures only ongoing or future events are shown
            time_filter = {
                'end_time__gt': current_time  # Only include events that haven't ended yet
            }
            
            if user_settings['show_today_only']:
                # Additionally filter to show only today's events
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                time_filter['start_time__gte'] = today_start
                time_filter['start_time__lte'] = today_end
                print(f"🔍 DEBUG: Live lessons - Filtering for TODAY ONLY (end_time > now): {today_start} to {today_end}")
            else:
                print(f"🔍 DEBUG: Live lessons - Filtering for ALL UPCOMING events (end_time > now)")
            
            # Filter class events for this course
            course_events = class_events.filter(
                **base_filter,
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
    

class AssessmentView(APIView):
    """
    Class-based view for handling comprehensive assessment data:
    - Single GET endpoint that fetches all assessment types
    - Each responsibility defined as a separate method
    - Similar structure to DashboardOverview
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """
        GET: Retrieve comprehensive assessment data
        Single endpoint that returns all assessment data
        """
        try:
            # Get all enrollments
            enrollments = EnrolledCourse.objects.all().select_related('course', 'student_profile')
            
            # Build comprehensive assessment data using separate methods
            assessment_data = {
                'dashboard': self._get_assessment_dashboard_data(enrollments),
                'quiz_assessments': self._get_quiz_assessments_data(enrollments),
                'assignment_assessments': self._get_assignment_assessments_data(enrollments),
                'instructor_assessments': self._get_instructor_assessments_data(enrollments),
                'summary': self._get_assessment_summary_data(enrollments)
            }
            print(f"Assessment data is: {assessment_data}")
            
            return Response(assessment_data)
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving assessments: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_assessment_dashboard_data(self, enrollments):
        """Get dashboard counts and statistics"""
        from courses.models import QuizAttempt
        
        # Quiz assessment counts
        quiz_attempts = QuizAttempt.objects.filter(enrollment__in=enrollments)
        quiz_count = quiz_attempts.count()
        quiz_passed = quiz_attempts.filter(passed=True).count()
        quiz_avg_score = quiz_attempts.aggregate(
            avg_score=models.Avg('score')
        )['avg_score'] or 0
        
        # Assignment assessment counts
        from courses.models import AssignmentSubmission
        assignment_count = AssignmentSubmission.objects.filter(
            enrollment__in=enrollments,
            status__in=['submitted', 'graded']  # Only count submitted and graded assignments
        ).count()
        
        # Instructor assessment counts
        instructor_count = TeacherAssessment.objects.filter(
            enrollment__in=enrollments
        ).count()
        
        # Recent activity (last 7 days)
        from django.utils import timezone
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        
        recent_quiz = quiz_attempts.filter(completed_at__gte=week_ago).count()
        
        # Calculate recent assignments using AssignmentSubmission model
        from courses.models import AssignmentSubmission
        recent_assignment = AssignmentSubmission.objects.filter(
            enrollment__in=enrollments,
            status__in=['submitted', 'graded'],  # Only count submitted and graded assignments
            submitted_at__gte=week_ago
        ).count()
        
        recent_instructor = TeacherAssessment.objects.filter(
            enrollment__in=enrollments,
            created_at__gte=week_ago
        ).count()
        
        return {
            'quiz_assessments': {
                'total': quiz_count,
                'passed': quiz_passed,
                'failed': quiz_count - quiz_passed,
                'average_score': round(float(quiz_avg_score), 2),
                'recent_week': recent_quiz
            },
            'assignment_assessments': {
                'total': assignment_count,
                'recent_week': recent_assignment
            },
            'instructor_assessments': {
                'total': instructor_count,
                'recent_week': recent_instructor
            },
            'overview': {
                'total_assessments': quiz_count + assignment_count + instructor_count,
                'total_courses': enrollments.count(),
                'recent_activity': recent_quiz + recent_assignment + recent_instructor
            }
        }
    
    def _get_quiz_assessments_data(self, enrollments):
        """Get quiz assessments data"""
        from courses.models import QuizAttempt
        
        quiz_attempts = QuizAttempt.objects.filter(
            enrollment__in=enrollments
        ).select_related('quiz', 'student').prefetch_related('quiz__lessons').order_by('-started_at')
        
        return [self._build_quiz_summary(attempt) for attempt in quiz_attempts]
    
    def _get_assignment_assessments_data(self, enrollments):
        """Get assignment assessments data"""
        assessments = LessonAssessment.objects.filter(
            enrollment__in=enrollments,
            quiz_attempt__isnull=True
        ).select_related('enrollment', 'lesson', 'teacher').order_by('-created_at')
        
        return [{
            'id': str(assessment.id),
            'title': assessment.title,
            'content': assessment.content[:100] + '...' if len(assessment.content) > 100 else assessment.content,
            'assessment_type': assessment.assessment_type,
            'lesson_title': assessment.lesson.title,
            'course_title': assessment.enrollment.course.title,
            'teacher_name': assessment.teacher.get_full_name(),
            'created_at': assessment.created_at.isoformat()
        } for assessment in assessments]
    
    def _get_instructor_assessments_data(self, enrollments):
        """Get instructor assessments data"""
        assessments = TeacherAssessment.objects.filter(
            enrollment__in=enrollments
        ).select_related('enrollment', 'teacher').order_by('-created_at')
        
        return [{
            'id': str(assessment.id),
            'academic_performance': assessment.academic_performance,
            'participation_level': assessment.participation_level,
            'strengths': assessment.strengths[:100] + '...' if len(assessment.strengths) > 100 else assessment.strengths,
            'weaknesses': assessment.weaknesses[:100] + '...' if len(assessment.weaknesses) > 100 else assessment.weaknesses,
            'course_title': assessment.enrollment.course.title,
            'teacher_name': assessment.teacher.get_full_name(),
            'created_at': assessment.created_at.isoformat()
        } for assessment in assessments]
    
    def _get_assessment_summary_data(self, enrollments):
        """Get assessment summary data"""
        from courses.models import QuizAttempt
        
        quiz_count = QuizAttempt.objects.filter(enrollment__in=enrollments).count()
        assignment_count = LessonAssessment.objects.filter(
            enrollment__in=enrollments,
            quiz_attempt__isnull=True
        ).count()
        instructor_count = TeacherAssessment.objects.filter(
            enrollment__in=enrollments
        ).count()
        
        return {
            'total_assessments': quiz_count + assignment_count + instructor_count,
            'quiz_count': quiz_count,
            'assignment_count': assignment_count,
            'instructor_count': instructor_count
        }
    

    # Quiz Assessment Methods
    def _get_quiz_assessment(self, request, assessment_id=None):
        """Get comprehensive quiz assessment data for UI display"""
        if assessment_id:
            # Get specific quiz attempt with all related data
            try:
                from courses.models import QuizAttempt, Quiz, Question
                
                # Get quiz attempt with all related data
                quiz_attempt = get_object_or_404(
                    QuizAttempt.objects.select_related(
                        'quiz', 'student'
                    ).prefetch_related(
                        'quiz__questions',
                        'quiz__lessons',
                        'question_feedbacks__teacher',
                        'attempt_feedbacks__teacher'
                    ),
                    id=assessment_id
                )
                
                # Check permissions
                if request.user.role == 'student' and quiz_attempt.student != request.user:
                    return Response(
                        {'error': 'Permission denied'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Build comprehensive quiz assessment response
                quiz_data = self._build_quiz_assessment_response(quiz_attempt)
                return Response(quiz_data)
                
            except Exception as e:
                return Response(
                    {'error': f'Quiz assessment not found: {str(e)}'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Get all quiz attempts for user with basic info
            if request.user.role == 'student':
                enrollments = EnrolledCourse.objects.filter(
                    student_profile__user=request.user
                )
                quiz_attempts = QuizAttempt.objects.filter(
                    enrollment__in=enrollments
                ).select_related('quiz').prefetch_related('quiz__lessons').order_by('-started_at')
            else:
                # Teacher/Admin can see all quiz attempts they have access to
                quiz_attempts = QuizAttempt.objects.filter(
                    quiz__lessons__course__teacher=request.user
                ).select_related('quiz', 'student').prefetch_related('quiz__lessons').order_by('-started_at')
            
            # Pagination
            paginator = StudentPagination()
            page = paginator.paginate_queryset(quiz_attempts, request)
            
            if page is not None:
                quiz_list = [self._build_quiz_summary(attempt) for attempt in page]
                return paginator.get_paginated_response(quiz_list)
            
            quiz_list = [self._build_quiz_summary(attempt) for attempt in quiz_attempts]
            return Response(quiz_list)
    
    def _build_quiz_assessment_response(self, quiz_attempt):
        """Build comprehensive quiz assessment response for detailed view"""
        from courses.models import Question
        
        # Get overall quiz attempt feedback
        overall_feedback = quiz_attempt.attempt_feedbacks.first()
        
        # Get all questions with their feedback
        questions_data = []
        for question in quiz_attempt.quiz.questions.all().order_by('order'):
            # Get feedback for this specific question
            question_feedback = quiz_attempt.question_feedbacks.filter(
                question=question
            ).first()
            
            # Get student's answer for this question
            student_answer = quiz_attempt.answers.get(str(question.id), '')
            
            # Determine if answer is correct
            is_correct = self._check_answer_correctness(question, student_answer)
            
            question_data = {
                'question_id': str(question.id),
                'question_number': question.order,
                'question_text': question.question_text,
                'question_type': question.type,
                'points_possible': question.points,
                'student_answer': student_answer,
                'correct_answer': self._get_correct_answer(question),
                'is_correct': is_correct,
                'points_earned': question.points if is_correct else 0,
                'explanation': question.explanation or '',
                'teacher_feedback': {
                    'feedback_text': question_feedback.feedback_text if question_feedback else '',
                    'points_earned': float(question_feedback.points_earned) if question_feedback and question_feedback.points_earned else (question.points if is_correct else 0),
                    'points_possible': float(question_feedback.points_possible) if question_feedback and question_feedback.points_possible else question.points,
                    'is_correct': question_feedback.is_correct if question_feedback else is_correct,
                    'teacher_name': question_feedback.teacher.get_full_name() if question_feedback else '',
                    'created_at': question_feedback.created_at.isoformat() if question_feedback else None
                } if question_feedback else None
            }
            questions_data.append(question_data)
        
        # Calculate totals
        total_points_earned = sum(q['points_earned'] for q in questions_data)
        total_points_possible = sum(q['points_possible'] for q in questions_data)
        percentage = (total_points_earned / total_points_possible * 100) if total_points_possible > 0 else 0
        
        # Calculate time taken
        time_taken = None
        if quiz_attempt.completed_at and quiz_attempt.started_at:
            time_taken = (quiz_attempt.completed_at - quiz_attempt.started_at).total_seconds() / 60  # minutes
        
        # Build response
        response_data = {
            'quiz_info': {
                'quiz_id': str(quiz_attempt.quiz.id),
                'quiz_title': quiz_attempt.quiz.title,
                'lesson_title': quiz_attempt.quiz.lessons.first().title if quiz_attempt.quiz.lessons.exists() else 'N/A',
                'course_title': quiz_attempt.quiz.lessons.first().course.title if quiz_attempt.quiz.lessons.exists() else 'N/A',
                'attempt_number': quiz_attempt.attempt_number,
                'time_limit': quiz_attempt.quiz.time_limit,
                'time_taken': time_taken,
                'started_at': quiz_attempt.started_at.isoformat(),
                'completed_at': quiz_attempt.completed_at.isoformat() if quiz_attempt.completed_at else None
            },
            'overall_feedback': {
                'score_percentage': float(quiz_attempt.final_score) if quiz_attempt.final_score else percentage,
                'points_earned': int(quiz_attempt.final_points_earned) if quiz_attempt.final_points_earned else int(total_points_earned),
                'points_possible': int(quiz_attempt.final_points_possible) if quiz_attempt.final_points_possible else int(total_points_possible),
                'passed': quiz_attempt.passed,
                'rating': overall_feedback.overall_rating if overall_feedback else self._get_performance_rating(percentage),
                'feedback_text': overall_feedback.feedback_text if overall_feedback else '',
                'strengths_highlighted': overall_feedback.strengths_highlighted if overall_feedback else '',
                'areas_for_improvement': overall_feedback.areas_for_improvement if overall_feedback else '',
                'study_recommendations': overall_feedback.study_recommendations if overall_feedback else '',
                'teacher_name': overall_feedback.teacher.get_full_name() if overall_feedback else '',
                'created_at': overall_feedback.created_at.isoformat() if overall_feedback else None
            },
            'questions': questions_data,
            'summary': {
                'total_questions': len(questions_data),
                'correct_answers': sum(1 for q in questions_data if q['is_correct']),
                'incorrect_answers': sum(1 for q in questions_data if not q['is_correct']),
                'completion_percentage': percentage
            }
        }
        
        return response_data
    
    def _build_quiz_summary(self, quiz_attempt):
        """Build summary data for quiz attempt list view"""
        return {
            'quiz_attempt_id': str(quiz_attempt.id),
            'quiz_title': quiz_attempt.quiz.title,
            'lesson_title': quiz_attempt.quiz.lessons.first().title if quiz_attempt.quiz.lessons.exists() else 'N/A',
            'course_title': quiz_attempt.quiz.lessons.first().course.title if quiz_attempt.quiz.lessons.exists() else 'N/A',
            'student_name': quiz_attempt.student.get_full_name(),
            'score_percentage': float(quiz_attempt.final_score) if quiz_attempt.final_score else 0,
            'passed': quiz_attempt.passed,
            'attempt_number': quiz_attempt.attempt_number,
            'started_at': quiz_attempt.started_at.isoformat(),
            'completed_at': quiz_attempt.completed_at.isoformat() if quiz_attempt.completed_at else None,
            'has_teacher_feedback': quiz_attempt.attempt_feedbacks.exists()
        }
    
    def _check_answer_correctness(self, question, student_answer):
        """Check if student's answer is correct for a given question"""
        if question.type == 'true_false':
            correct_answer = question.content.get('correct_answer', '').lower()
            return str(student_answer).lower() == correct_answer
        elif question.type == 'multiple_choice':
            correct_answer = question.content.get('correct_answer', '')
            return str(student_answer) == str(correct_answer)
        elif question.type == 'fill_blank':
            correct_answers = question.content.get('correct_answers', [])
            return str(student_answer).lower().strip() in [ans.lower().strip() for ans in correct_answers]
        # Add more question types as needed
        return False
    
    def _get_correct_answer(self, question):
        """Get the correct answer for display"""
        if question.type == 'true_false':
            return question.content.get('correct_answer', '')
        elif question.type == 'multiple_choice':
            return question.content.get('correct_answer', '')
        elif question.type == 'fill_blank':
            correct_answers = question.content.get('correct_answers', [])
            return ', '.join(correct_answers) if correct_answers else ''
        return ''
    
    def _get_performance_rating(self, percentage):
        """Get performance rating based on percentage"""
        if percentage >= 90:
            return 'excellent'
        elif percentage >= 80:
            return 'good'
        elif percentage >= 70:
            return 'satisfactory'
        elif percentage >= 60:
            return 'needs_improvement'
        else:
            return 'poor'
    
    
    # Assignment Assessment Methods
    def _get_assignment_assessment(self, request, assessment_id=None):
        """Get assignment assessment(s)"""
        if assessment_id:
            # Get specific assignment assessment
            assessment = get_object_or_404(LessonAssessment, id=assessment_id)
            
            # Check permissions
            if request.user.role == 'student' and assessment.enrollment.student_profile.user != request.user:
                return Response(
                    {'error': 'Permission denied'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = QuizQuestionFeedbackDetailSerializer(assessment)
            return Response(serializer.data)
        else:
            # Get all assignment assessments for user
            if request.user.role == 'student':
                enrollments = EnrolledCourse.objects.filter(
                    student_profile__user=request.user
                )
                assessments = LessonAssessment.objects.filter(
                    enrollment__in=enrollments,
                    assessment_type__in=['strength', 'weakness', 'improvement', 'general', 'achievement', 'challenge'],
                    quiz_attempt__isnull=True  # Assignment assessments don't have quiz attempts
                ).order_by('-created_at')
            else:
                # Teacher/Admin can see all assessments they created
                assessments = LessonAssessment.objects.filter(
                    teacher=request.user,
                    quiz_attempt__isnull=True
                ).order_by('-created_at')
            
            # Pagination
            paginator = StudentPagination()
            page = paginator.paginate_queryset(assessments, request)
            if page is not None:
                serializer = QuizQuestionFeedbackDetailSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = QuizQuestionFeedbackDetailSerializer(assessments, many=True)
            return Response(serializer.data)
    
   
        """Delete assignment assessment"""
        assessment = get_object_or_404(LessonAssessment, id=assessment_id)
        
        # Check permissions
        if assessment.teacher != request.user and request.user.role not in ['admin', 'superuser']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        assessment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    
class DashboardAssessmentView(APIView):
    """
    Returns assessment summary data for dashboard
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Get current user's student profile
            student_profile = request.user.student_profile
            
            # Quiz assessments stats - filter by user, not student_profile
            quiz_attempts = QuizAttempt.objects.filter(
                student=request.user,
                completed_at__isnull=False
            )
            
            total_quizzes = quiz_attempts.count()
            passed_quizzes = quiz_attempts.filter(passed=True).count()
            failed_quizzes = total_quizzes - passed_quizzes
            avg_score = quiz_attempts.aggregate(avg=Avg('score'))['avg'] or 0
            
            # Recent week quizzes (last 7 days)
            from django.utils import timezone
            week_ago = timezone.now() - timedelta(days=7)
            recent_quizzes = quiz_attempts.filter(completed_at__gte=week_ago).count()
            
            # Quiz assessments list (last attempts only)
            quiz_assessments = []
            for attempt in quiz_attempts.order_by('-completed_at')[:10]:  # Limit to 10 most recent
                quiz_assessments.append({
                    'quiz_attempt_id': str(attempt.id),
                    'quiz_title': attempt.quiz.title,
                    'lesson_title': attempt.quiz.lessons.first().title if attempt.quiz.lessons.exists() else 'N/A',
                    'course_title': attempt.quiz.lessons.first().course.title if attempt.quiz.lessons.exists() else 'N/A',
                    'student_name': f"{student_profile.child_first_name} {student_profile.child_last_name}",
                    'score_percentage': float(attempt.final_score) if attempt.final_score else 0.0,
                    'passed': attempt.passed,
                    'attempt_number': attempt.attempt_number,
                    'started_at': attempt.started_at.isoformat(),
                    'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
                    'has_teacher_feedback': attempt.is_teacher_graded
                })
            
            # Assignment assessments (top-level summary similar to quizzes)
            assignment_submissions_qs = AssignmentSubmission.objects.filter(
                student=request.user,
                status__in=['submitted', 'graded']  # Only show submitted and graded assignments
            ).select_related(
                'assignment',
                'graded_by'
            ).prefetch_related(
                'assignment__lessons__course'
            )

            total_assignments = assignment_submissions_qs.count()
            # Use passed flag; if not graded yet, passed defaults False per model
            passed_assignments = assignment_submissions_qs.filter(passed=True).count()
            avg_assignment_score = assignment_submissions_qs.aggregate(avg=Avg('percentage'))['avg'] or 0
            recent_assignments = assignment_submissions_qs.filter(submitted_at__gte=week_ago).count()

            assignment_assessments = []
            for sub in assignment_submissions_qs.order_by('-submitted_at')[:10]:
                # Determine if assignment is graded
                is_graded = sub.status == 'graded' and sub.is_graded
                
                assignment_assessments.append({
                    'assignment_attempt_id': str(sub.id),
                    'assignment_title': sub.assignment.title,
                    'lesson_title': sub.assignment.lessons.first().title if sub.assignment and sub.assignment.lessons.exists() else 'N/A',
                    'course_title': sub.assignment.lessons.first().course.title if sub.assignment and sub.assignment.lessons.exists() else 'N/A',
                    'student_name': f"{student_profile.child_first_name} {student_profile.child_last_name}",
                    'score_percentage': float(sub.percentage) if sub.percentage is not None and is_graded else None,
                    'passed': bool(sub.passed) if is_graded else None,  # Only show pass/fail if graded
                    'is_graded': is_graded,
                    'attempt_number': sub.attempt_number,
                    'submitted_at': sub.submitted_at.isoformat() if sub.submitted_at else None,
                    'graded_at': sub.graded_at.isoformat() if sub.graded_at else None,
                    'has_teacher_feedback': bool(sub.instructor_feedback)
                })
            
            # Teacher assessments - get all assessments for this student
            teacher_assessments = TeacherAssessment.objects.filter(
                enrollment__student_profile=student_profile
            ).select_related('enrollment__course', 'teacher')
            
            total_teacher_assessments = teacher_assessments.count()
            new_teacher_assessments = teacher_assessments.filter(viewed_at__isnull=True).count()
            recent_teacher_assessments = teacher_assessments.filter(created_at__gte=week_ago).count()
            
            # Group teacher assessments by course and teacher
            teacher_assessment_groups = []
            grouped_assessments = {}
            
            for assessment in teacher_assessments.order_by('-created_at'):
                key = (assessment.enrollment.course.id, assessment.teacher.id)
                if key not in grouped_assessments:
                    grouped_assessments[key] = {
                        'course_id': str(assessment.enrollment.course.id),
                        'course_title': assessment.enrollment.course.title,
                        'teacher_id': str(assessment.teacher.id),
                        'teacher_name': assessment.teacher.get_full_name(),
                        'assessments': [],
                        'total_assessments': 0,
                        'new_assessments': 0,
                        'latest_assessment': None
                    }
                
                assessment_data = {
                    'id': str(assessment.id),
                    'created_at': assessment.created_at.isoformat(),
                    'academic_performance': assessment.academic_performance,
                    'participation_level': assessment.participation_level,
                    'general_comments_preview': assessment.general_comments[:100] + '...' if len(assessment.general_comments) > 100 else assessment.general_comments,
                    'viewed_at': assessment.viewed_at.isoformat() if assessment.viewed_at else None,
                    'is_new': assessment.viewed_at is None
                }
                
                grouped_assessments[key]['assessments'].append(assessment_data)
                grouped_assessments[key]['total_assessments'] += 1
                if assessment.viewed_at is None:
                    grouped_assessments[key]['new_assessments'] += 1
                
                # Set latest assessment (first one since we're ordering by -created_at)
                if grouped_assessments[key]['latest_assessment'] is None:
                    grouped_assessments[key]['latest_assessment'] = assessment_data
            
            teacher_assessment_groups = list(grouped_assessments.values())
            
            # Instructor assessments (using teacher assessments data)
            instructor_assessments = []
            
            response_data = {
                'dashboard': {
                    'quiz_assessments': {
                        'total': total_quizzes,
                        'passed': passed_quizzes,
                        'failed': failed_quizzes,
                        'average_score': round(avg_score, 1),
                        'recent_week': recent_quizzes
                    },
                    'assignment_assessments': {
                        'total': total_assignments,
                        'passed': passed_assignments,
                        'average_score': round(avg_assignment_score, 1),
                        'recent_week': recent_assignments
                    },
                    'instructor_assessments': {
                        'total': total_teacher_assessments,
                        'new': new_teacher_assessments,
                        'recent_week': recent_teacher_assessments
                    },
                    'overview': {
                        'total_assessments': total_quizzes + total_assignments,
                        'total_courses': 0,
                        'recent_activity': recent_quizzes + recent_assignments
                    }
                },
                'quiz_assessments': quiz_assessments,
                'assignment_assessments': assignment_assessments,
                'instructor_assessments': instructor_assessments,
                'teacher_assessment_groups': teacher_assessment_groups,
                'summary': {
                    'total_assessments': total_quizzes + total_assignments,
                    'quiz_count': total_quizzes,
                    'assignment_count': total_assignments,
                    'instructor_count': 0
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch assessment data: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class QuizDetailView(APIView):
    """
    Returns detailed quiz attempt data including questions and answers
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, quiz_attempt_id):
        try:
            # Get current user's student profile
            student_profile = request.user.student_profile
            
            # Get the quiz attempt - filter by user, not student_profile
            quiz_attempt = get_object_or_404(
                QuizAttempt, 
                id=quiz_attempt_id, 
                student=request.user
            )
            
            # Get quiz questions
            quiz_questions = Question.objects.filter(quiz=quiz_attempt.quiz)
            
            # Get quiz attempt feedback (overall feedback)
            quiz_attempt_feedback = QuizAttemptFeedback.objects.filter(
                quiz_attempt=quiz_attempt
            ).first()
            
            # Build questions list from answers JSONField and questions
            questions = []
            answers_data = quiz_attempt.answers or {}
            
            for question in quiz_questions:
                question_id = str(question.id)
                student_answer = answers_data.get(question_id, '')
                
                # Get question-specific feedback
                question_feedback = QuizQuestionFeedback.objects.filter(
                    quiz_attempt=quiz_attempt,
                    question=question
                ).first()
                
                # Extract correct answer and options from content JSONField
                content = question.content or {}
                correct_answer = content.get('correct_answer', '')
                options = content.get('options', [])
                full_options = content.get('full_options', None)
                
                # Calculate if answer is correct
                is_correct = student_answer.lower().strip() == correct_answer.lower().strip() if correct_answer else False
                
                question_data = {
                    'question_id': question_id,
                    'question_text': question.question_text,
                    'question_type': question.type,
                    'student_answer': student_answer,
                    'correct_answer': correct_answer,
                    'options': options,  # Add options for multiple choice questions
                    'full_options': full_options,  # Add full_options with explanations
                    'points_earned': float(question_feedback.points_earned) if question_feedback and question_feedback.points_earned else (question.points if is_correct else 0),
                    'points_possible': float(question_feedback.points_possible) if question_feedback and question_feedback.points_possible else question.points,
                    'explanation': question.explanation or '',
                    'teacher_feedback': question_feedback.feedback_text if question_feedback else '',
                    'is_correct': is_correct
                }
                questions.append(question_data)
            
            # Calculate summary statistics
            correct_answers = sum(1 for q in questions if q['is_correct'])
            incorrect_answers = len(questions) - correct_answers
            completion_percentage = 100.0 if quiz_attempt.completed_at else 0.0
            
            # Calculate total points earned and possible
            total_points_earned = sum(q['points_earned'] for q in questions)
            total_points_possible = sum(q['points_possible'] for q in questions)
            
            response_data = {
                'quiz_info': {
                    'quiz_attempt_id': str(quiz_attempt.id),
                    'quiz_title': quiz_attempt.quiz.title,
                    'lesson_title': quiz_attempt.quiz.lessons.first().title if quiz_attempt.quiz.lessons.exists() else 'N/A',
                    'course_title': quiz_attempt.quiz.lessons.first().course.title if quiz_attempt.quiz.lessons.exists() else 'N/A',
                    'student_name': f"{student_profile.child_first_name} {student_profile.child_last_name}",
                    'attempt_number': quiz_attempt.attempt_number,
                    'started_at': quiz_attempt.started_at.isoformat(),
                    'completed_at': quiz_attempt.completed_at.isoformat() if quiz_attempt.completed_at else None,
                },
                'overall_feedback': {
                    'score_percentage': float(quiz_attempt.final_score) if quiz_attempt.final_score else (total_points_earned / total_points_possible * 100) if total_points_possible > 0 else 0.0,
                    'points_earned': quiz_attempt.final_points_earned if quiz_attempt.final_points_earned else total_points_earned,
                    'points_possible': quiz_attempt.final_points_possible if quiz_attempt.final_points_possible else total_points_possible,
                    'passed': quiz_attempt.passed,
                    'rating': quiz_attempt_feedback.overall_rating if quiz_attempt_feedback and quiz_attempt_feedback.overall_rating else ('excellent' if quiz_attempt.final_score and quiz_attempt.final_score >= 90 else 'good' if quiz_attempt.final_score and quiz_attempt.final_score >= 70 else 'needs_improvement'),
                    'feedback_text': quiz_attempt_feedback.feedback_text if quiz_attempt_feedback else quiz_attempt.teacher_comments or '',
                    'strengths_highlighted': quiz_attempt_feedback.strengths_highlighted if quiz_attempt_feedback else '',
                    'areas_for_improvement': quiz_attempt_feedback.areas_for_improvement if quiz_attempt_feedback else '',
                    'study_recommendations': quiz_attempt_feedback.study_recommendations if quiz_attempt_feedback else '',
                    'teacher_name': quiz_attempt_feedback.teacher.get_full_name() if quiz_attempt_feedback and quiz_attempt_feedback.teacher else '',
                    'created_at': quiz_attempt_feedback.created_at.isoformat() if quiz_attempt_feedback and quiz_attempt_feedback.created_at else quiz_attempt.completed_at.isoformat() if quiz_attempt.completed_at else None,
                },
                'questions': questions,
                'summary': {
                    'total_questions': len(questions),
                    'correct_answers': correct_answers,
                    'incorrect_answers': incorrect_answers,
                    'completion_percentage': completion_percentage
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch quiz detail: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TeacherAssessmentListView(APIView):
    """
    Returns list of teacher assessments for a specific course and teacher
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, course_id, teacher_id):
        try:
            student_profile = request.user.student_profile
            
            # Get teacher assessments for this course and teacher
            teacher_assessments = TeacherAssessment.objects.filter(
                enrollment__student_profile=student_profile,
                enrollment__course_id=course_id,
                teacher_id=teacher_id
            ).select_related('enrollment__course', 'teacher').order_by('-created_at')
            
            if not teacher_assessments.exists():
                return Response(
                    {'error': 'No teacher assessments found for this course and teacher'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get course and teacher info from first assessment
            first_assessment = teacher_assessments.first()
            course_title = first_assessment.enrollment.course.title
            teacher_name = first_assessment.teacher.get_full_name()
            
            # Build assessments list
            assessments = []
            for assessment in teacher_assessments:
                assessments.append({
                    'id': str(assessment.id),
                    'created_at': assessment.created_at.isoformat(),
                    'academic_performance': assessment.academic_performance,
                    'participation_level': assessment.participation_level,
                    'general_comments_preview': assessment.general_comments[:100] + '...' if len(assessment.general_comments) > 100 else assessment.general_comments,
                    'viewed_at': assessment.viewed_at.isoformat() if assessment.viewed_at else None,
                    'is_new': assessment.viewed_at is None
                })
            
            response_data = {
                'course_id': str(course_id),
                'course_title': course_title,
                'teacher_id': str(teacher_id),
                'teacher_name': teacher_name,
                'total_assessments': len(assessments),
                'new_assessments': len([a for a in assessments if a['is_new']]),
                'assessments': assessments
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch teacher assessments: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TeacherAssessmentDetailView(APIView):
    """
    Returns detailed teacher assessment and marks it as viewed
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, assessment_id):
        try:
            student_profile = request.user.student_profile
            
            # Get the specific assessment
            assessment = get_object_or_404(
                TeacherAssessment,
                id=assessment_id,
                enrollment__student_profile=student_profile
            )
            
            # Mark as viewed if not already viewed
            if assessment.viewed_at is None:
                assessment.viewed_at = timezone.now()
                assessment.save()
            
            response_data = {
                'id': str(assessment.id),
                'teacher_name': assessment.teacher.get_full_name(),
                'course_title': assessment.enrollment.course.title,
                'created_at': assessment.created_at.isoformat(),
                'viewed_at': assessment.viewed_at.isoformat() if assessment.viewed_at else None,
                'academic_performance': assessment.academic_performance,
                'participation_level': assessment.participation_level,
                'strengths': assessment.strengths,
                'weaknesses': assessment.weaknesses,
                'recommendations': assessment.recommendations,
                'general_comments': assessment.general_comments
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch teacher assessment detail: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssignmentSubmissionView(APIView):
    """
    Handle assignment submissions (both draft and final)
    POST /api/assignments/{assignment_id}/submit/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, assignment_id):
        try:
            # Get assignment and validate
            assignment = get_object_or_404(Assignment, id=assignment_id)
            
            # Validate request data
            serializer = AssignmentSubmissionSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            is_draft = validated_data.get('is_draft', False)
            
            # Get student's enrollment in the course (allow both active and completed like quizzes)
            first_lesson = assignment.lessons.first() if assignment.lessons.exists() else None
            if not first_lesson:
                return Response(
                    {'error': 'Assignment has no associated lesson'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                enrollment = EnrolledCourse.objects.get(
                    student_profile__user=request.user,
                    course=first_lesson.course,
                    status__in=['active', 'completed']
                )
            except EnrolledCourse.DoesNotExist:
                return Response(
                    {'error': 'You are not enrolled in this course'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get or create submission
            submission, created = AssignmentSubmission.objects.get_or_create(
                student=request.user,
                assignment=assignment,
                defaults={
                    'attempt_number': 1,
                    'status': 'draft' if is_draft else 'submitted',
                    'answers': validated_data.get('answers', {}),
                    'enrollment': enrollment,
                    'submitted_at': timezone.now()
                }
            )
            
            # Update existing submission if not created
            if not created:
                print(f"🔄 Updating existing submission. Current answers: {submission.answers}")
                print(f"🔄 New answers received: {validated_data.get('answers', {})}")
                
                # Merge answers instead of replacing them completely
                existing_answers = submission.answers or {}
                new_answers = validated_data.get('answers', {})
                
                # Merge the answers (new answers override existing ones for same questions)
                merged_answers = {**existing_answers, **new_answers}
                
                print(f"🔄 Merged answers: {merged_answers}")
                
                submission.answers = merged_answers
                submission.status = 'draft' if is_draft else 'submitted'
                submission.submitted_at = timezone.now()
                submission.save()
            
            # Assignment submission completed successfully
            # Note: Assignment completion tracking has been removed from UI
            # The fields remain in the model for potential future use
            
            # Return response
            response_serializer = AssignmentSubmissionResponseSerializer(submission)
            response_data = {
                'submission': response_serializer.data,
                'message': 'Draft saved successfully' if is_draft else 'Assignment submitted successfully'
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Assignment.DoesNotExist:
            return Response(
                {'error': 'Assignment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to submit assignment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssignmentSubmissionDetailView(APIView):
    """
    GET: Retrieve full assignment submission details for student view
    POST: Submit student feedback response and mark feedback as checked
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, submission_id):
        try:
            # Get the assignment submission
            submission = AssignmentSubmission.objects.select_related(
                'assignment',
                'graded_by'
            ).prefetch_related(
                'assignment__questions',
                'assignment__lessons__course'
            ).get(
                id=submission_id,
                student=request.user
            )
            
            # Get assignment with questions
            assignment = submission.assignment
            questions = assignment.questions.all().order_by('order')
            
            # Build questions data
            questions_data = []
            for question in questions:
                questions_data.append({
                    'id': str(question.id),
                    'question_text': question.question_text,
                    'order': question.order,
                    'points': question.points,
                    'type': question.type,
                    'content': question.content,
                    'explanation': question.explanation,
                })
            
            # Build graded questions data
            graded_questions_data = []
            for graded_q in submission.graded_questions:
                # Check both 'teacher_feedback' and 'feedback' for backward compatibility
                feedback = graded_q.get('teacher_feedback') or graded_q.get('feedback', '')
                graded_questions_data.append({
                    'question_id': graded_q.get('question_id'),
                    'points_earned': graded_q.get('points_earned', 0),
                    'points_possible': graded_q.get('points_possible'),
                    'feedback': feedback,
                    'correct_answer': graded_q.get('correct_answer', ''),
                    'is_correct': graded_q.get('is_correct'),
                })
            
            # Build submission data
            submission_data = {
                'id': str(submission.id),
                'status': submission.status,
                'is_graded': submission.is_graded,
                'answers': submission.answers,
                'graded_questions': graded_questions_data,
                'instructor_feedback': submission.instructor_feedback,
                'feedback_response': submission.feedback_response,
                'feedback_checked': submission.feedback_checked,
                'feedback_checked_at': submission.feedback_checked_at.isoformat() if submission.feedback_checked_at else None,
                'points_earned': float(submission.points_earned) if submission.points_earned else None,
                'points_possible': float(submission.points_possible) if submission.points_possible else None,
                'percentage': float(submission.percentage) if submission.percentage else None,
                'passed': submission.passed,
                'submitted_at': submission.submitted_at.isoformat(),
                'graded_at': submission.graded_at.isoformat() if submission.graded_at else None,
                'graded_by': submission.graded_by.get_full_name() if submission.graded_by else None,
            }
            
            # Build assignment data
            assignment_data = {
                'id': str(assignment.id),
                'title': assignment.title,
                'description': assignment.description,
                'assignment_type': assignment.assignment_type,
                'passing_score': assignment.passing_score,
                'questions': questions_data,
            }
            
            return Response({
                'assignment': assignment_data,
                'submission': submission_data,
            })
            
        except AssignmentSubmission.DoesNotExist:
            return Response(
                {'error': 'Assignment submission not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to retrieve assignment submission: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, submission_id):
        try:
            # Get the assignment submission
            submission = AssignmentSubmission.objects.get(
                id=submission_id,
                student=request.user
            )
            
            # Get feedback response from request
            feedback_response = request.data.get('feedback_response', '')
            
            # Update submission
            submission.feedback_response = feedback_response
            submission.feedback_checked = True
            submission.feedback_checked_at = timezone.now()
            submission.save()
            
            return Response({
                'message': 'Feedback response submitted successfully',
                'feedback_response': submission.feedback_response,
                'feedback_checked': submission.feedback_checked,
                'feedback_checked_at': submission.feedback_checked_at.isoformat(),
            })
            
        except AssignmentSubmission.DoesNotExist:
            return Response(
                {'error': 'Assignment submission not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to submit feedback response: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===== PARENT DASHBOARD =====

class ParentDashboardView(APIView):
    """
    Parent dashboard view - returns comprehensive data for parent dashboard
    Organized into separate methods for each dashboard section
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Get parent dashboard data
        Aggregates data from all dashboard sections
        """
        try:
            # Get student profile (parents use student credentials)
            student_profile = getattr(request.user, 'student_profile', None)
            
            if not student_profile:
                return Response(
                    {'error': 'Student profile not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get enrolled courses for data aggregation
            # Use select_related to get course data for performance calculations
            enrolled_courses_queryset = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course').only(
                'id', 'completed_lessons_count', 'total_lessons_count', 
                'course_id', 'student_profile_id', 'average_quiz_score', 
                'average_assignment_score', 'course__title'
            )
            
            # Convert to list immediately to force evaluation and avoid prefetch issues
            # This ensures the queryset is fully evaluated before any methods try to use it
            enrolled_courses_objects = list(enrolled_courses_queryset)
            
            # Build response data using separate methods
            response_data = {
                'children': self.get_children_data(student_profile, enrolled_courses_objects),
                'recent_activities': self.get_recent_activities(student_profile, enrolled_courses_objects),
                'upcoming_tasks': self.get_upcoming_tasks(student_profile, enrolled_courses_objects),
                'performance_data': self.get_performance_data(student_profile, enrolled_courses_objects),
                'single_course_data': self.get_single_course_data(student_profile, enrolled_courses_objects),
                'notifications': self.get_notifications(student_profile, enrolled_courses_objects),
                'weekly_stats': self.get_weekly_stats(student_profile, enrolled_courses_objects),
                'messages_unread_count': self.get_messages_unread_count(student_profile),
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to fetch parent dashboard data', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_children_data(self, student_profile, enrolled_courses):
        """
        Get children list data
        For now, returns the current student as a single child
        Future: Can be extended to support multiple children per parent
        """
        # Get name from student profile
        child_first_name = student_profile.child_first_name or student_profile.user.first_name or ''
        child_last_name = student_profile.child_last_name or student_profile.user.last_name or ''
        full_name = f"{child_first_name} {child_last_name}".strip() or student_profile.user.email
        
        # Generate avatar initials
        if child_first_name and child_last_name:
            avatar = f"{child_first_name[0]}{child_last_name[0]}".upper()
        elif child_first_name:
            avatar = child_first_name[0].upper()
        elif student_profile.user.first_name:
            avatar = student_profile.user.first_name[0].upper()
        else:
            avatar = student_profile.user.email[0].upper()
        
        # Get grade level
        grade = student_profile.grade_level or 'Not specified'
        
        # Calculate metrics from enrolled courses
        #weekly_progress = self._calculate_weekly_progress(enrolled_courses)
        lessons_completed, total_lessons = self._calculate_lessons_progress(enrolled_courses)
        
        # Get average scores from StudentProfile
        avg_score = float(student_profile.overall_average_score) if student_profile.overall_average_score is not None else 0
        average_quiz = float(student_profile.overall_quiz_average_score) if student_profile.overall_quiz_average_score is not None else 0
        average_assignment = float(student_profile.overall_assignment_average_score) if student_profile.overall_assignment_average_score is not None else 0
        
        return [{
            'id': str(student_profile.user.id),
            'name': full_name,
            'grade': grade,
            'avatar': avatar,
            #'weekly_progress': weekly_progress,
            'lessons_completed': lessons_completed,
            'total_lessons': total_lessons,
            'avg_score': avg_score,
            'average_quiz': average_quiz,
            'average_assignment': average_assignment,
        }]
    
    def _calculate_weekly_progress(self, enrolled_courses):
        """
        Calculate weekly progress percentage
        Helper method for get_children_data
        """
        # TODO: Calculate progress from lessons completed this week
        # For now, return placeholder
        return 0
    
    def _calculate_lessons_progress(self, enrolled_courses):
        """
        Calculate total lessons completed vs total lessons
        Helper method for get_children_data
        """
        # enrolled_courses is already a list, so we can safely iterate
        total_completed = sum(enrollment.completed_lessons_count for enrollment in enrolled_courses)
        total_lessons = sum(enrollment.total_lessons_count for enrollment in enrolled_courses)
        return (total_completed, total_lessons)
    
    def _calculate_average_score(self, enrolled_courses):
        """
        Calculate average score from quizzes and assignments
        Helper method for get_children_data
        """
        # TODO: Calculate average from QuizAttempt and AssignmentSubmission scores
        # For now, return placeholder
        
    
    
    
    def get_weekly_progress(self, student_profile, enrolled_courses):
        """
        Get weekly progress data for a child
        Calculates progress from enrolled courses and lesson completions
        """
        # TODO: Calculate weekly progress from enrolled courses
        # - Get lessons completed this week
        # - Calculate progress percentage
        # - Get average scores
        # - Calculate streak
        # For now, return placeholder
        return {}
    
    def get_recent_activities(self, student_profile, enrolled_courses):
        """
        Get recent activities (quizzes, assignments, lessons)
        From enrolled courses, get recent quiz attempts and assignment submissions
        """
        # TODO: Query recent activities from enrolled courses
        # - Get recent QuizAttempt records from enrolled courses
        # - Get recent AssignmentSubmission records from enrolled courses
        # - Format with subject (course title), activity name, status, score, time
        # For now, return placeholder
        return [
            {
                'id': 'placeholder-1',
                'subject': 'Mathematics',
                'activity': 'Quiz: Fractions',
                'status': 'completed',
                'score': 95,
                'time': '2 hours ago',
                'color': 'bg-blue-500',
            },
            {
                'id': 'placeholder-2',
                'subject': 'English',
                'activity': 'Reading Assignment',
                'status': 'completed',
                'score': 88,
                'time': '5 hours ago',
                'color': 'bg-purple-500',
            },
            {
                'id': 'placeholder-3',
                'subject': 'Science',
                'activity': 'Lab Report',
                'status': 'in-progress',
                'score': None,
                'time': '1 day ago',
                'color': 'bg-green-500',
            },
        ]
    
    def get_upcoming_tasks(self, student_profile, enrolled_courses):
        """
        Get upcoming tasks from ClassEvents and Assignments
        Returns only upcoming tasks (filtered by date on backend for performance)
        """
        from courses.models import ClassEvent, Assignment, AssignmentSubmission
        from student.models import StudentLessonProgress
        from django.utils import timezone
        from django.db.models import Q, Exists, OuterRef
        
        tasks = []
        enrolled_course_ids = [enrollment.course.id for enrollment in enrolled_courses]
        now_utc = timezone.now()
        
        # 1. Get ClassEvents from enrolled courses
        # Query all event types (lesson, meeting, project, break) from classes in enrolled courses
        # Only include events where student is enrolled in the class
        # Filter to only upcoming/ongoing events:
        #   - For projects: due_date >= now (not yet due)
        #   - For other events: end_time > now (includes upcoming and ongoing events)
        class_events = ClassEvent.objects.filter(
            class_instance__course_id__in=enrolled_course_ids,
            class_instance__students=student_profile.user
        ).filter(
            Q(event_type='project', due_date__gte=now_utc) |
            Q(event_type__in=['lesson', 'meeting', 'break'], end_time__gt=now_utc)
        ).select_related('class_instance', 'class_instance__course', 'lesson', 'project')
        
        for event in class_events:
            course_title = event.class_instance.course.title if event.class_instance and event.class_instance.course else 'Unknown Course'
            task_title = event.title
            
            # For project events, use project title if available
            if event.event_type == 'project' and event.project_title:
                task_title = event.project_title
            elif event.event_type == 'project' and event.project:
                task_title = event.project.title
            
            # For project events, use due_date
            # For other events (lesson, meeting, break), use start_time and end_time
            if event.event_type == 'project':
                due_date = event.due_date
                if due_date:
                    # Ensure datetime is timezone-aware and in UTC before serializing
                    if timezone.is_naive(due_date):
                        due_date_utc = timezone.make_aware(due_date, timezone.utc)
                    else:
                        due_date_utc = due_date.astimezone(timezone.utc)
                    
                    # Format as ISO string with 'Z' suffix to indicate UTC
                    due_date_iso = due_date_utc.isoformat().replace('+00:00', 'Z')
                    
                    tasks.append({
                        'id': str(event.id),
                        'type': 'class_event',
                        'event_type': event.event_type,
                        'title': task_title,
                        'course_name': course_title,
                        'course_id': str(event.class_instance.course.id) if event.class_instance and event.class_instance.course else None,
                        'due_date': due_date_iso,
                        'start_time': None,
                        'end_time': None,
                    })
            elif event.start_time and event.end_time:
                # For non-project events, use start_time as the reference date for sorting
                # but include both start_time and end_time for display
                start_time = event.start_time
                end_time = event.end_time
                
                # Ensure datetimes are timezone-aware and in UTC before serializing
                if timezone.is_naive(start_time):
                    start_time_utc = timezone.make_aware(start_time, timezone.utc)
                else:
                    start_time_utc = start_time.astimezone(timezone.utc)
                
                if timezone.is_naive(end_time):
                    end_time_utc = timezone.make_aware(end_time, timezone.utc)
                else:
                    end_time_utc = end_time.astimezone(timezone.utc)
                
                # Format as ISO strings with 'Z' suffix
                start_time_iso = start_time_utc.isoformat().replace('+00:00', 'Z')
                end_time_iso = end_time_utc.isoformat().replace('+00:00', 'Z')
                
                # Use start_time as due_date for sorting/filtering purposes
                tasks.append({
                    'id': str(event.id),
                    'type': 'class_event',
                    'event_type': event.event_type,
                    'title': task_title,
                    'course_name': course_title,
                    'course_id': str(event.class_instance.course.id) if event.class_instance and event.class_instance.course else None,
                    'due_date': start_time_iso,  # Use start_time for sorting
                    'start_time': start_time_iso,
                    'end_time': end_time_iso,
                })
        
        # 2. Get Assignments from completed lessons
        # Get all completed lessons for this student across enrolled courses
        completed_lessons = StudentLessonProgress.objects.filter(
            enrollment__in=enrolled_courses,
            status='completed'
        ).values_list('lesson_id', flat=True)
        
        if completed_lessons:
            # Get assignments linked to completed lessons that haven't been submitted
            # Only include upcoming assignments (due_date >= now)
            assignments = Assignment.objects.filter(
                lessons__id__in=completed_lessons,
                due_date__isnull=False,
                due_date__gte=now_utc
            ).distinct()
            
            # Exclude assignments that have been submitted
            submitted_assignments = AssignmentSubmission.objects.filter(
                student=student_profile.user,
                enrollment__in=enrolled_courses
            ).values_list('assignment_id', flat=True)
            
            assignments = assignments.exclude(id__in=submitted_assignments)
            
            for assignment in assignments:
                # Get course from assignment's lessons (assignments can be linked to multiple lessons)
                # Get the first enrolled course that contains this assignment's lessons
                assignment_course = None
                assignment_course_id = None
                for enrollment in enrolled_courses:
                    if assignment.lessons.filter(course=enrollment.course).exists():
                        assignment_course = enrollment.course.title
                        assignment_course_id = str(enrollment.course.id)
                        break
                
                if assignment_course and assignment.due_date:  # Only add if we found a matching enrolled course
                    # Ensure datetime is timezone-aware and in UTC before serializing
                    due_date = assignment.due_date
                    if timezone.is_naive(due_date):
                        # If naive, assume it's in UTC and make it timezone-aware
                        due_date_utc = timezone.make_aware(due_date, timezone.utc)
                    else:
                        # Convert to UTC if it's timezone-aware (but in a different timezone)
                        due_date_utc = due_date.astimezone(timezone.utc)
                    
                    # Format as ISO string with 'Z' suffix to indicate UTC
                    # Django's isoformat() returns '+00:00' for UTC, replace with 'Z' for JavaScript compatibility
                    due_date_iso = due_date_utc.isoformat().replace('+00:00', 'Z')
                    
                    tasks.append({
                        'id': str(assignment.id),
                        'type': 'assignment',
                        'event_type': 'assignment',
                        'title': assignment.title,
                        'course_name': assignment_course,
                        'course_id': assignment_course_id,
                        'due_date': due_date_iso,
                    })
        
        return tasks
    
    def get_performance_data(self, student_profile, enrolled_courses):
        """
        Get performance data by subject/course
        Aggregates quiz and assignment scores by course/subject
        """
        from courses.models import QuizAttempt, AssignmentSubmission
        from django.db.models import Avg, Q
        
        performance_data = []
        
        for enrollment in enrolled_courses:
            # Get course title
            course_title = enrollment.course.title if hasattr(enrollment, 'course') and enrollment.course else 'Unknown Course'
            
            # Calculate quiz average for this enrollment
            quiz_attempts = QuizAttempt.objects.filter(
                enrollment=enrollment,
                completed_at__isnull=False,
                score__isnull=False
            )
            
            quiz_avg = None
            if quiz_attempts.exists():
                # Use final_score property if available (handles teacher-graded quizzes)
                quiz_scores = []
                for attempt in quiz_attempts:
                    score = attempt.final_score if hasattr(attempt, 'final_score') else attempt.score
                    if score is not None:
                        quiz_scores.append(float(score))
                
                if quiz_scores:
                    quiz_avg = sum(quiz_scores) / len(quiz_scores)
            
            # Calculate assignment average for this enrollment
            assignment_submissions = AssignmentSubmission.objects.filter(
                enrollment=enrollment,
                is_graded=True,
                percentage__isnull=False
            )
            
            assignment_avg = None
            if assignment_submissions.exists():
                assignment_scores = [float(sub.percentage) for sub in assignment_submissions if sub.percentage is not None]
                if assignment_scores:
                    assignment_avg = sum(assignment_scores) / len(assignment_scores)
            
            # Calculate overall average (weighted by count)
            overall_score = None
            if quiz_avg is not None and assignment_avg is not None:
                # Weighted average
                quiz_count = quiz_attempts.count()
                assignment_count = assignment_submissions.count()
                total_count = quiz_count + assignment_count
                if total_count > 0:
                    overall_score = ((quiz_avg * quiz_count) + (assignment_avg * assignment_count)) / total_count
            elif quiz_avg is not None:
                overall_score = quiz_avg
            elif assignment_avg is not None:
                overall_score = assignment_avg
            
            # Only include courses with at least some performance data
            if overall_score is not None:
                performance_data.append({
                    'subject': course_title,
                    'score': round(overall_score),
                    'trend': 'stable',  # Can be enhanced later to compare with previous periods
                })
        
        # If no performance data, return empty list
        return performance_data
    
    def get_single_course_data(self, student_profile, enrolled_courses):
        """
        Get detailed single course performance data
        Includes weekly progress trend, grade breakdown, recent grades
        """
        from courses.models import QuizAttempt, AssignmentSubmission
        from django.utils import timezone
        from datetime import timedelta
        
        # Select most active course (first one with data, or first enrolled course)
        if not enrolled_courses:
            return {
                'course_name': 'No Course',
                'current_score': 0,
                'trend': 'stable',
                'weekly_progress': [],
                'breakdown': [],
                'recent_grades': [],
            }
        
        # Get the first enrolled course (or most active one)
        enrollment = enrolled_courses[0]
        course_title = enrollment.course.title if hasattr(enrollment, 'course') and enrollment.course else 'Unknown Course'
        
        # Calculate current averages from enrollment or calculate them
        quiz_avg = None
        assignment_avg = None
        
        # Try to use enrollment's stored averages first
        if enrollment.average_quiz_score is not None:
            quiz_avg = float(enrollment.average_quiz_score)
        else:
            # Calculate from QuizAttempt
            quiz_attempts = QuizAttempt.objects.filter(
                enrollment=enrollment,
                completed_at__isnull=False,
                score__isnull=False
            )
            if quiz_attempts.exists():
                quiz_scores = []
                for attempt in quiz_attempts:
                    score = attempt.final_score if hasattr(attempt, 'final_score') else attempt.score
                    if score is not None:
                        quiz_scores.append(float(score))
                if quiz_scores:
                    quiz_avg = sum(quiz_scores) / len(quiz_scores)
        
        if enrollment.average_assignment_score is not None:
            assignment_avg = float(enrollment.average_assignment_score)
        else:
            # Calculate from AssignmentSubmission
            assignment_submissions = AssignmentSubmission.objects.filter(
                enrollment=enrollment,
                is_graded=True,
                percentage__isnull=False
            )
            if assignment_submissions.exists():
                assignment_scores = [float(sub.percentage) for sub in assignment_submissions if sub.percentage is not None]
                if assignment_scores:
                    assignment_avg = sum(assignment_scores) / len(assignment_scores)
        
        # Calculate current score (overall average)
        current_score = 0
        if quiz_avg is not None and assignment_avg is not None:
            quiz_count = QuizAttempt.objects.filter(enrollment=enrollment, completed_at__isnull=False, score__isnull=False).count()
            assignment_count = AssignmentSubmission.objects.filter(enrollment=enrollment, is_graded=True, percentage__isnull=False).count()
            total_count = quiz_count + assignment_count
            if total_count > 0:
                current_score = ((quiz_avg * quiz_count) + (assignment_avg * assignment_count)) / total_count
        elif quiz_avg is not None:
            current_score = quiz_avg
        elif assignment_avg is not None:
            current_score = assignment_avg
        
        # Build breakdown (weekly stats will be used for the chart, but we need breakdown here)
        breakdown = [
            {
                'category': 'Homework',
                'score': round(assignment_avg) if assignment_avg is not None else None,
                'color': 'bg-blue-500',
            },
            {
                'category': 'Quizzes',
                'score': round(quiz_avg) if quiz_avg is not None else None,
                'color': 'bg-purple-500',
            },
            {
                'category': 'Tests',
                'score': None,  # No grade for now
                'color': 'bg-green-500',
            },
            {
                'category': 'Participation',
                'score': None,  # No grade for now
                'color': 'bg-orange-500',
            },
        ]
        
        # Get recent grades (last 5 quiz attempts and assignments)
        recent_grades = []
        
        # Recent quiz attempts
        recent_quizzes = QuizAttempt.objects.filter(
            enrollment=enrollment,
            completed_at__isnull=False,
            score__isnull=False
        ).order_by('-completed_at')[:3]
        
        for quiz_attempt in recent_quizzes:
            score = quiz_attempt.final_score if hasattr(quiz_attempt, 'final_score') else quiz_attempt.score
            if score is not None:
                recent_grades.append({
                    'assignment': quiz_attempt.quiz.title if hasattr(quiz_attempt, 'quiz') and quiz_attempt.quiz else 'Quiz',
                    'date': quiz_attempt.completed_at.strftime('%b %d') if quiz_attempt.completed_at else '',
                    'score': round(float(score)),
                    'type': 'quiz',
                })
        
        # Recent assignments
        recent_assignments = AssignmentSubmission.objects.filter(
            enrollment=enrollment,
            is_graded=True,
            percentage__isnull=False
        ).order_by('-graded_at', '-submitted_at')[:3]
        
        for assignment_sub in recent_assignments:
            if assignment_sub.percentage is not None:
                recent_grades.append({
                    'assignment': assignment_sub.assignment.title if hasattr(assignment_sub, 'assignment') and assignment_sub.assignment else 'Assignment',
                    'date': (assignment_sub.graded_at or assignment_sub.submitted_at).strftime('%b %d') if (assignment_sub.graded_at or assignment_sub.submitted_at) else '',
                    'score': round(float(assignment_sub.percentage)),
                    'type': 'homework',
                })
        
        # Sort by date (most recent first) and limit to 5
        recent_grades.sort(key=lambda x: x.get('date', ''), reverse=True)
        recent_grades = recent_grades[:5]
        
        return {
            'course_name': course_title,
            'current_score': round(current_score) if current_score > 0 else 0,
            'trend': 'stable',  # Can be enhanced later
            'weekly_progress': [],  # This will be populated from weekly_stats in frontend
            'breakdown': breakdown,
            'recent_grades': recent_grades,
        }
    
    def get_notifications(self, student_profile, enrolled_courses):
        """
        Get notifications/messages for the parent
        Returns assessments/reports from teachers and messages from admin
        For now, returns empty array - will be implemented later
        """
        # TODO: Implement notifications/messages functionality
        # - Get teacher assessments/reports for enrolled students
        # - Get admin messages
        # - Format with type, text, time, unread status
        return []
    
    def get_messages_unread_count(self, student_profile):
        """
        Get unread message count for parent
        Returns count of unread messages in parent-type conversations
        """
        try:
            # Get parent-type conversations for this student
            conversations = Conversation.objects.filter(
                student_profile=student_profile,
                recipient_type='parent'
            )
            
            # Count unread messages (messages not sent by parent and not read)
            parent_user = student_profile.user
            unread_count = Message.objects.filter(
                conversation__in=conversations
            ).exclude(sender=parent_user).filter(read_at__isnull=True).count()
            
            return unread_count
        except Exception as e:
            # If there's an error, return 0 to avoid breaking the dashboard
            import traceback
            traceback.print_exc()
            return 0
    
    def get_weekly_stats(self, student_profile, enrolled_courses):
        """
        Get weekly performance statistics (quiz and assignment averages over time)
        Returns the last 6 weeks of performance data for trend visualization
        """
        try:
            from users.models import StudentWeeklyPerformance
        except Exception:
            # Table doesn't exist yet (migration not run)
            return {
                'weekly_trend': [],
                'total_weeks': 0,
            }
        
        try:
            # Get last 6 weeks of performance data
            weekly_performance = StudentWeeklyPerformance.objects.filter(
                student_profile=student_profile
            ).order_by('-year', '-week_number')[:6]
            
            # Format data for frontend
            weekly_trend = []
            for wp in weekly_performance:
                weekly_trend.append({
                    'week': f"W{wp.week_number}",
                    'year': wp.year,
                    'week_number': wp.week_number,
                    'overall_avg': float(wp.overall_average) if wp.overall_average is not None else None,
                    'quiz_avg': float(wp.quiz_average) if wp.quiz_average is not None else None,
                    'assignment_avg': float(wp.assignment_average) if wp.assignment_average is not None else None,
                    'quiz_count': wp.quiz_count,
                    'assignment_count': wp.assignment_count,
                })
            
            # Reverse to show oldest to newest (W1, W2, ..., W6)
            weekly_trend.reverse()
            
            return {
                'weekly_trend': weekly_trend,
                'total_weeks': len(weekly_trend),
            }
        except Exception as e:
            print(f"Error fetching weekly stats: {e}")
            import traceback
            traceback.print_exc()
            return {
                'weekly_trend': [],
                'total_weeks': 0,
            }
    
    def get_all_courses_detailed_data(self, student_profile, enrolled_courses):
        """
        Get detailed breakdown data for all enrolled courses
        Returns array of course details including breakdown and recent grades
        This is called asynchronously after initial dashboard load
        """
        from courses.models import QuizAttempt, AssignmentSubmission
        
        courses_detailed = []
        
        for enrollment in enrolled_courses:
            course_title = enrollment.course.title if hasattr(enrollment, 'course') and enrollment.course else 'Unknown Course'
            
            # Calculate quiz average
            quiz_avg = None
            if enrollment.average_quiz_score is not None:
                quiz_avg = float(enrollment.average_quiz_score)
            else:
                quiz_attempts = QuizAttempt.objects.filter(
                    enrollment=enrollment,
                    completed_at__isnull=False,
                    score__isnull=False
                )
                if quiz_attempts.exists():
                    quiz_scores = []
                    for attempt in quiz_attempts:
                        score = attempt.final_score if hasattr(attempt, 'final_score') else attempt.score
                        if score is not None:
                            quiz_scores.append(float(score))
                    if quiz_scores:
                        quiz_avg = sum(quiz_scores) / len(quiz_scores)
            
            # Calculate assignment average
            assignment_avg = None
            if enrollment.average_assignment_score is not None:
                assignment_avg = float(enrollment.average_assignment_score)
            else:
                assignment_submissions = AssignmentSubmission.objects.filter(
                    enrollment=enrollment,
                    is_graded=True,
                    percentage__isnull=False
                )
                if assignment_submissions.exists():
                    assignment_scores = [float(sub.percentage) for sub in assignment_submissions if sub.percentage is not None]
                    if assignment_scores:
                        assignment_avg = sum(assignment_scores) / len(assignment_scores)
            
            # Calculate current score
            current_score = 0
            if quiz_avg is not None and assignment_avg is not None:
                quiz_count = QuizAttempt.objects.filter(enrollment=enrollment, completed_at__isnull=False, score__isnull=False).count()
                assignment_count = AssignmentSubmission.objects.filter(enrollment=enrollment, is_graded=True, percentage__isnull=False).count()
                total_count = quiz_count + assignment_count
                if total_count > 0:
                    current_score = ((quiz_avg * quiz_count) + (assignment_avg * assignment_count)) / total_count
            elif quiz_avg is not None:
                current_score = quiz_avg
            elif assignment_avg is not None:
                current_score = assignment_avg
            
            # Build breakdown
            breakdown = [
                {
                    'category': 'Homework',
                    'score': round(assignment_avg) if assignment_avg is not None else None,
                    'color': 'bg-blue-500',
                },
                {
                    'category': 'Quizzes',
                    'score': round(quiz_avg) if quiz_avg is not None else None,
                    'color': 'bg-purple-500',
                },
                {
                    'category': 'Tests',
                    'score': None,
                    'color': 'bg-green-500',
                },
                {
                    'category': 'Participation',
                    'score': None,
                    'color': 'bg-orange-500',
                },
            ]
            
            # Get recent grades
            recent_grades = []
            
            # Recent quiz attempts
            recent_quizzes = QuizAttempt.objects.filter(
                enrollment=enrollment,
                completed_at__isnull=False,
                score__isnull=False
            ).order_by('-completed_at')[:3]
            
            for quiz_attempt in recent_quizzes:
                score = quiz_attempt.final_score if hasattr(quiz_attempt, 'final_score') else quiz_attempt.score
                if score is not None:
                    recent_grades.append({
                        'assignment': quiz_attempt.quiz.title if hasattr(quiz_attempt, 'quiz') and quiz_attempt.quiz else 'Quiz',
                        'date': quiz_attempt.completed_at.strftime('%b %d') if quiz_attempt.completed_at else '',
                        'score': round(float(score)),
                        'type': 'quiz',
                    })
            
            # Recent assignments
            recent_assignments = AssignmentSubmission.objects.filter(
                enrollment=enrollment,
                is_graded=True,
                percentage__isnull=False
            ).order_by('-graded_at', '-submitted_at')[:3]
            
            for assignment_sub in recent_assignments:
                if assignment_sub.percentage is not None:
                    recent_grades.append({
                        'assignment': assignment_sub.assignment.title if hasattr(assignment_sub, 'assignment') and assignment_sub.assignment else 'Assignment',
                        'date': (assignment_sub.graded_at or assignment_sub.submitted_at).strftime('%b %d') if (assignment_sub.graded_at or assignment_sub.submitted_at) else '',
                        'score': round(float(assignment_sub.percentage)),
                        'type': 'homework',
                    })
            
            # Sort by date and limit
            recent_grades.sort(key=lambda x: x.get('date', ''), reverse=True)
            recent_grades = recent_grades[:5]
            
            courses_detailed.append({
                'course_name': course_title,
                'course_id': str(enrollment.course.id) if hasattr(enrollment, 'course') and enrollment.course else None,
                'current_score': round(current_score) if current_score > 0 else 0,
                'trend': 'stable',
                'breakdown': breakdown,
                'recent_grades': recent_grades,
            })
        
        return courses_detailed


class AllCoursesDetailedView(APIView):
    """
    Get detailed breakdown data for all enrolled courses
    Called asynchronously after initial dashboard load
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Get detailed data for all enrolled courses
        """
        try:
            student_profile = getattr(request.user, 'student_profile', None)
            
            if not student_profile:
                return Response(
                    {'error': 'Student profile not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get enrolled courses
            enrolled_courses_queryset = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                status='active'
            ).select_related('course').only(
                'id', 'course_id', 'student_profile_id', 
                'average_quiz_score', 'average_assignment_score', 
                'course__title', 'course__id'
            )
            
            enrolled_courses_objects = list(enrolled_courses_queryset)
            
            # Get detailed data for all courses
            view_instance = ParentDashboardView()
            courses_detailed = view_instance.get_all_courses_detailed_data(
                student_profile, 
                enrolled_courses_objects
            )
            
            return Response({
                'courses': courses_detailed
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to fetch courses detailed data', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===== PARENT MESSAGING VIEWS =====

class ParentMessagePagination(PageNumberPagination):
    """Pagination for parent message lists"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class ParentConversationsListView(APIView):
    """
    List conversations for parent's student.
    Parents can only see recipient_type='parent' conversations.
    """
    permission_classes = [IsAuthenticated]
    
    def get_parent_student_profile(self, parent_user):
        """Get student profile for parent's child"""
        try:
            return StudentProfile.objects.get(user=parent_user)
        except StudentProfile.DoesNotExist:
            return None
    
    def get(self, request):
        """List conversations for parent's student"""
        try:
            parent_user = request.user
            if parent_user.role != 'student':
                return Response(
                    {'error': 'Only parents can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student profile (parent's child)
            student_profile = self.get_parent_student_profile(parent_user)
            if not student_profile:
                return Response(
                    {'error': 'Student profile not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get conversations - only parent type
            conversations = Conversation.objects.filter(
                student_profile=student_profile,
                recipient_type='parent'
            ).select_related('student_profile', 'student_profile__user', 'teacher', 'course')
            
            # Order by last message time
            conversations = conversations.order_by('-last_message_at', '-created_at')
            
            # Serialize with context for unread count
            serializer = ConversationListSerializer(
                conversations,
                many=True,
                context={'request': request}
            )
            
            return Response({
                'conversations': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to fetch conversations', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ParentConversationMessagesView(APIView):
    """
    Get messages in a conversation or send a new message.
    Parents can only access recipient_type='parent' conversations for their student.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = ParentMessagePagination
    
    def verify_parent_access(self, parent_user, conversation):
        """Verify parent has access to this conversation"""
        # Check if conversation is for parent's student
        student_profile = self.get_parent_student_profile(parent_user)
        if not student_profile:
            return False
        
        return (
            conversation.student_profile == student_profile and
            conversation.recipient_type == 'parent'
        )
    
    def get_parent_student_profile(self, parent_user):
        """Get student profile for parent's child"""
        try:
            return StudentProfile.objects.get(user=parent_user)
        except StudentProfile.DoesNotExist:
            return None
    
    def get(self, request, conversation_id):
        """Get messages in conversation"""
        try:
            parent_user = request.user
            if parent_user.role != 'student':
                return Response(
                    {'error': 'Only parents can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get conversation
            try:
                conversation = Conversation.objects.select_related(
                    'student_profile', 'student_profile__user', 'teacher'
                ).get(id=conversation_id)
            except Conversation.DoesNotExist:
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify access
            if not self.verify_parent_access(parent_user, conversation):
                return Response(
                    {'error': 'You do not have access to this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get messages with pagination
            messages = conversation.messages.select_related('sender').order_by('created_at')
            
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(messages, request)
            
            if page is not None:
                serializer = MessageSerializer(page, many=True, context={'request': request})
                # Return in the format expected by frontend
                return Response({
                    'conversation': ConversationSerializer(conversation).data,
                    'messages': serializer.data,
                    'pagination': {
                        'page': paginator.page.number,
                        'page_size': paginator.page_size,
                        'total_pages': paginator.page.paginator.num_pages,
                        'total_count': paginator.page.paginator.count,
                    }
                }, status=status.HTTP_200_OK)
            
            # No pagination
            serializer = MessageSerializer(messages, many=True, context={'request': request})
            return Response({
                'conversation': ConversationSerializer(conversation).data,
                'messages': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to fetch messages', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, conversation_id):
        """Send a new message"""
        try:
            parent_user = request.user
            if parent_user.role != 'student':
                return Response(
                    {'error': 'Only parents can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get conversation
            try:
                conversation = Conversation.objects.select_related(
                    'student_profile', 'teacher'
                ).get(id=conversation_id)
            except Conversation.DoesNotExist:
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify access
            if not self.verify_parent_access(parent_user, conversation):
                return Response(
                    {'error': 'You do not have access to this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Validate message data
            serializer = CreateMessageSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Create message
            message = Message.objects.create(
                conversation=conversation,
                sender=parent_user,
                content=serializer.validated_data['content']
            )
            
            # Update conversation's last_message_at
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=['last_message_at'])
            
            # Serialize response
            response_serializer = MessageSerializer(message, context={'request': request})
            
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to send message', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ParentMarkMessageReadView(APIView):
    """Mark a message as read (parent)"""
    permission_classes = [IsAuthenticated]
    
    def get_parent_student_profile(self, parent_user):
        """Get student profile for parent's child"""
        try:
            return StudentProfile.objects.get(user=parent_user)
        except StudentProfile.DoesNotExist:
            return None
    
    def verify_parent_access(self, parent_user, conversation):
        """Verify parent has access to this conversation"""
        student_profile = self.get_parent_student_profile(parent_user)
        if not student_profile:
            return False
        
        return (
            conversation.student_profile == student_profile and
            conversation.recipient_type == 'parent'
        )
    
    def patch(self, request, message_id):
        """Mark message as read"""
        try:
            parent_user = request.user
            if parent_user.role != 'student':
                return Response(
                    {'error': 'Only parents can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get message
            try:
                message = Message.objects.select_related(
                    'conversation', 'conversation__student_profile'
                ).get(id=message_id)
            except Message.DoesNotExist:
                return Response(
                    {'error': 'Message not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify parent has access to conversation
            if not self.verify_parent_access(parent_user, message.conversation):
                return Response(
                    {'error': 'You do not have access to this message'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Mark as read
            message.mark_as_read(parent_user)
            
            # Serialize response
            serializer = MessageSerializer(message, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to mark message as read', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ParentUnreadCountView(APIView):
    """Get unread message count for parent"""
    permission_classes = [IsAuthenticated]
    
    def get_parent_student_profile(self, parent_user):
        """Get student profile for parent's child"""
        try:
            return StudentProfile.objects.get(user=parent_user)
        except StudentProfile.DoesNotExist:
            return None
    
    def get(self, request):
        """Get unread count for parent"""
        try:
            parent_user = request.user
            if parent_user.role != 'student':
                return Response(
                    {'error': 'Only parents can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student profile
            student_profile = self.get_parent_student_profile(parent_user)
            if not student_profile:
                return Response({
                    'unread_count': 0
                }, status=status.HTTP_200_OK)
            
            # Get parent-type conversations for this student
            conversations = Conversation.objects.filter(
                student_profile=student_profile,
                recipient_type='parent'
            )
            
            # Count unread messages (messages not sent by parent and not read)
            unread_count = Message.objects.filter(
                conversation__in=conversations
            ).exclude(sender=parent_user).filter(read_at__isnull=True).count()
            
            return Response({
                'unread_count': unread_count
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to get unread count', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )