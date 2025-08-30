from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import EnrolledCourse, LessonAssessment, TeacherAssessment, QuizQuestionFeedback, QuizAttemptFeedback
from .serializers import (
    EnrolledCourseListSerializer, 
    EnrolledCourseDetailSerializer, 
    EnrolledCourseCreateUpdateSerializer,
    QuizQuestionFeedbackDetailSerializer,
    QuizQuestionFeedbackCreateUpdateSerializer,
    QuizAttemptFeedbackDetailSerializer,
    QuizAttemptFeedbackCreateUpdateSerializer,
    StudentFeedbackOverviewSerializer
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
