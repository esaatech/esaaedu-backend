import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from users.models import User, TeacherProfile

logger = logging.getLogger(__name__)
from .serializers import (
    TeacherProfileSerializer, TeacherProfileUpdateSerializer,
    ProjectSerializer, ProjectCreateUpdateSerializer,
    ProjectSubmissionSerializer, ProjectSubmissionGradingSerializer,
    ProjectSubmissionFeedbackSerializer,
    AssignmentListSerializer, AssignmentDetailSerializer, AssignmentCreateUpdateSerializer,
    AssignmentQuestionSerializer, AssignmentSubmissionSerializer, AssignmentGradingSerializer,
    AssignmentFeedbackSerializer
)
from courses.models import Course, ClassEvent, CourseReview, Project, ProjectSubmission, Assignment, AssignmentQuestion, AssignmentSubmission, LessonMaterial, VideoMaterial, BookPage, Lesson, DocumentMaterial, AudioVideoMaterial
from student.models import EnrolledCourse, Conversation, Message
from student.serializers import (
    ConversationListSerializer, ConversationSerializer,
    MessageSerializer, CreateConversationSerializer, CreateMessageSerializer
)
from users.models import StudentProfile
from rest_framework.pagination import PageNumberPagination
from datetime import datetime, timedelta
# Import AI grading service
from ai.gemini_grader import GeminiGrader
# Import AI generation services
from ai.gemini_course_introduction_service import GeminiCourseIntroductionService
from ai.gemini_course_lessons_service import GeminiCourseLessonsService
from ai.video_transcription_service import VideoTranscriptionService
from ai.gemini_quiz_service import GeminiQuizService
from ai.gemini_assignment_service import GeminiAssignmentService
from courses.serializers import VideoMaterialSerializer, VideoMaterialCreateSerializer, VideoMaterialTranscribeSerializer


class TeacherProfileAPIView(APIView):
    """
    API view for teacher profile management
    Handles different sections of the teacher profile UI
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get complete teacher profile data
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get or create teacher profile
            teacher_profile, created = TeacherProfile.objects.get_or_create(
                user=teacher,
                defaults={
                    'bio': '',
                    'qualifications': '',
                    'department': '',
                    'phone_number': '',
                    'specializations': [],
                    'years_of_experience': 0,
                    'linkedin_url': '',
                    'twitter_url': '',
                }
            )
            
            # Get profile data
            profile_data = self.get_personal_information(teacher_profile)
            professional_data = self.get_professional_information(teacher_profile)
            contact_data = self.get_contact_information(teacher_profile)
            account_status = self.get_account_status(teacher_profile)
            teaching_stats = self.get_teaching_statistics(teacher_profile)
            
            return Response({
                'profile': profile_data,
                'professional': professional_data,
                'contact': contact_data,
                'account_status': account_status,
                'teaching_stats': teaching_stats,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch teacher profile', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        """
        Update teacher profile data
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            teacher_profile = get_object_or_404(TeacherProfile, user=teacher)
            
            # Determine which section to update based on request data
            section = request.data.get('section', 'all')
            
            if section == 'personal' or section == 'all':
                self.update_personal_information(teacher_profile, request.data)
            
            if section == 'professional' or section == 'all':
                self.update_professional_information(teacher_profile, request.data)
            
            if section == 'contact' or section == 'all':
                self.update_contact_information(teacher_profile, request.data)
            
            # Return updated profile data
            profile_data = self.get_personal_information(teacher_profile)
            professional_data = self.get_professional_information(teacher_profile)
            contact_data = self.get_contact_information(teacher_profile)
            account_status = self.get_account_status(teacher_profile)
            teaching_stats = self.get_teaching_statistics(teacher_profile)
            
            return Response({
                'profile': profile_data,
                'professional': professional_data,
                'contact': contact_data,
                'account_status': account_status,
                'teaching_stats': teaching_stats,
                'message': 'Profile updated successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to update teacher profile', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_personal_information(self, teacher_profile):
        """
        Get personal information section data
        """
        return {
            'id': teacher_profile.id,
            'email': teacher_profile.user.email,
            'first_name': teacher_profile.user.first_name,
            'last_name': teacher_profile.user.last_name,
            'full_name': teacher_profile.user.get_full_name() or f"{teacher_profile.user.first_name} {teacher_profile.user.last_name}".strip(),
            'role': teacher_profile.user.role,
            'profile_image': teacher_profile.profile_image,
        }
    
    def get_professional_information(self, teacher_profile):
        """
        Get professional information section data
        """
        return {
            'bio': teacher_profile.bio,
            'qualifications': teacher_profile.qualifications,
            'department': teacher_profile.department,
            'specializations': teacher_profile.specializations,
            'years_of_experience': teacher_profile.years_of_experience,
        }
    
    def get_contact_information(self, teacher_profile):
        """
        Get contact information section data
        """
        return {
            'phone_number': teacher_profile.phone_number,
            'linkedin_url': teacher_profile.linkedin_url,
            'twitter_url': teacher_profile.twitter_url,
        }
    
    def get_account_status(self, teacher_profile):
        """
        Get account status section data
        """
        return {
            'email_verified': teacher_profile.user.is_active,  # Assuming active means verified
            'account_type': teacher_profile.user.role,
            'member_since': teacher_profile.user.created_at,
            'last_login_at': teacher_profile.user.last_login_at,
        }
    
    def get_teaching_statistics(self, teacher_profile):
        """
        Get teaching statistics section data
        """
        try:
            # Get teacher's courses
            teacher_courses = Course.objects.filter(teacher=teacher_profile.user)
            
            # Calculate statistics
            total_students = EnrolledCourse.objects.filter(
                course__teacher=teacher_profile.user
            ).values('student_profile__user').distinct().count()
            
            active_courses = teacher_courses.filter(status='published').count()
            
            # Get completed lessons (assuming this is tracked in LessonProgress)
            completed_lessons = LessonProgress.objects.filter(
                lesson__course__teacher=teacher_profile.user,
                status='completed'
            ).count()
            
            # Get average rating from course reviews
            avg_rating = CourseReview.objects.filter(
                course__teacher=teacher_profile.user
            ).aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
            
            return {
                'total_students': total_students,
                'active_courses': active_courses,
                'completed_lessons': completed_lessons,
                'average_rating': round(avg_rating, 1),
            }
        except Exception as e:
            # Return default values if calculation fails
            return {
                'total_students': 0,
                'active_courses': 0,
                'completed_lessons': 0,
                'average_rating': 0.0,
            }
    
    def update_personal_information(self, teacher_profile, data):
        """
        Update personal information section
        """
        user = teacher_profile.user
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'profile_image' in data:
            teacher_profile.profile_image = data['profile_image']
        
        user.save()
        teacher_profile.save()
    
    def update_professional_information(self, teacher_profile, data):
        """
        Update professional information section
        """
        if 'bio' in data:
            teacher_profile.bio = data['bio']
        if 'qualifications' in data:
            teacher_profile.qualifications = data['qualifications']
        if 'department' in data:
            teacher_profile.department = data['department']
        if 'specializations' in data:
            teacher_profile.specializations = data['specializations']
        if 'years_of_experience' in data:
            teacher_profile.years_of_experience = data['years_of_experience']
        
        teacher_profile.save()
    
    def update_contact_information(self, teacher_profile, data):
        """
        Update contact information section
        """
        if 'phone_number' in data:
            teacher_profile.phone_number = data['phone_number']
        if 'linkedin_url' in data:
            teacher_profile.linkedin_url = data['linkedin_url']
        if 'twitter_url' in data:
            teacher_profile.twitter_url = data['twitter_url']
        
        teacher_profile.save()


class TeacherScheduleAPIView(APIView):
    """
    API view for teacher schedule management
    Handles different types of schedule data for the teacher calendar
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get teacher's schedule data for calendar display
        """
        try:
            teacher = request.user
            
            # Get all events for teacher's courses
            events = self.get_teacher_events(teacher)
            
            # Get upcoming events
            upcoming_events = self.get_upcoming_events(teacher)
            
            # Get events by type
            events_by_type = self.get_events_by_type(teacher)
            
            # Get events by course
            events_by_course = self.get_events_by_course(teacher)
            
            return Response({
                'events': events,
                'upcoming_events': upcoming_events,
                'events_by_type': events_by_type,
                'events_by_course': events_by_course,
                'summary': self.get_schedule_summary(teacher)
            })
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch schedule data', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_teacher_events(self, teacher):
        """
        Get all events for teacher's courses
        """
        events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).select_related(
            'class_instance__course',
            'lesson',
            'project',
            'project_platform',
            'assessment'
        ).order_by('start_time')
        
        return [
            {
                'id': str(event.id),
                'title': event.title,
                'description': event.description,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'end_time': event.end_time.isoformat() if event.end_time else None,
                'event_type': event.event_type,
                'lesson_type': event.lesson_type,
                'meeting_platform': event.meeting_platform,
                'meeting_link': event.meeting_link,
                'meeting_id': event.meeting_id,
                'meeting_password': event.meeting_password,
                'course_id': str(event.class_instance.course.id),
                'course_title': event.class_instance.course.title,
                'class_name': event.class_instance.name,
                'lesson_title': event.lesson.title if event.lesson else None,
                'project_id': str(event.project.id) if event.project else None,
                'project_title': event.project_title or (event.project.title if event.project else None),
                'project_platform_id': str(event.project_platform.id) if event.project_platform else None,
                'project_platform_name': event.project_platform.display_name if event.project_platform else None,
                'assessment_id': str(event.assessment.id) if event.assessment else None,
                'assessment_title': event.assessment.title if event.assessment else None,
                'assessment_type': event.assessment.assessment_type if event.assessment else None,
                'due_date': event.due_date.isoformat() if event.due_date else None,
                'submission_type': event.submission_type,
                'duration_minutes': event.duration_minutes,
                'created_at': event.created_at.isoformat(),
            }
            for event in events
        ]
    
    def get_upcoming_events(self, teacher):
        """
        Get upcoming events (next 30 days)
        """
        from datetime import datetime, timedelta
        from django.db.models import Q
        
        now = datetime.now()
        future_date = now + timedelta(days=30)
        
        # For non-project events, filter by start_time
        # For project events, filter by due_date
        events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).filter(
            Q(start_time__gte=now, start_time__lte=future_date) |  # Non-project events
            Q(due_date__gte=now, due_date__lte=future_date)       # Project events
        ).select_related(
            'class_instance__course',
            'lesson',
            'project',
            'project_platform',
            'assessment'
        ).order_by('start_time', 'due_date')
        
        return [
            {
                'id': str(event.id),
                'title': event.title,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'end_time': event.end_time.isoformat() if event.end_time else None,
                'event_type': event.event_type,
                'course_title': event.class_instance.course.title,
                'class_name': event.class_instance.name,
                'meeting_link': event.meeting_link,
                'meeting_platform': event.meeting_platform,
                'project_id': str(event.project.id) if event.project else None,
                'project_title': event.project_title or (event.project.title if event.project else None),
                'project_platform_name': event.project_platform.display_name if event.project_platform else None,
                'assessment_id': str(event.assessment.id) if event.assessment else None,
                'assessment_title': event.assessment.title if event.assessment else None,
                'assessment_type': event.assessment.assessment_type if event.assessment else None,
                'due_date': event.due_date.isoformat() if event.due_date else None,
                'submission_type': event.submission_type,
            }
            for event in events
        ]
    
    def get_events_by_type(self, teacher):
        """
        Get events grouped by type
        """
        events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).select_related(
            'class_instance__course',
            'lesson',
            'project',
            'project_platform',
            'assessment'
        )
        
        events_by_type = {
            'lesson': [],
            'meeting': [],
            'break': [],
            'project': [],
            'test': [],
            'exam': []
        }
        
        for event in events:
            event_data = {
                'id': str(event.id),
                'title': event.title,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'end_time': event.end_time.isoformat() if event.end_time else None,
                'course_title': event.class_instance.course.title,
                'class_name': event.class_instance.name,
                'project_id': str(event.project.id) if event.project else None,
                'project_title': event.project_title or (event.project.title if event.project else None),
                'project_platform_name': event.project_platform.display_name if event.project_platform else None,
                'assessment_id': str(event.assessment.id) if event.assessment else None,
                'assessment_title': event.assessment.title if event.assessment else None,
                'assessment_type': event.assessment.assessment_type if event.assessment else None,
                'due_date': event.due_date.isoformat() if event.due_date else None,
                'submission_type': event.submission_type,
            }
            # Safely append to events_by_type, creating key if it doesn't exist
            event_type = event.event_type
            if event_type not in events_by_type:
                events_by_type[event_type] = []
            events_by_type[event_type].append(event_data)
        
        return events_by_type
    
    def get_events_by_course(self, teacher):
        """
        Get events grouped by course
        """
        events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).select_related(
            'class_instance__course',
            'lesson',
            'project',
            'project_platform',
            'assessment'
        )
        
        events_by_course = {}
        
        for event in events:
            course_id = str(event.class_instance.course.id)
            course_title = event.class_instance.course.title
            
            if course_id not in events_by_course:
                events_by_course[course_id] = {
                    'course_id': course_id,
                    'course_title': course_title,
                    'events': []
                }
            
            event_data = {
                'id': str(event.id),
                'title': event.title,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'end_time': event.end_time.isoformat() if event.end_time else None,
                'event_type': event.event_type,
                'lesson_type': event.lesson_type,
                'class_name': event.class_instance.name,
                'project_id': str(event.project.id) if event.project else None,
                'project_title': event.project_title or (event.project.title if event.project else None),
                'project_platform_name': event.project_platform.display_name if event.project_platform else None,
                'assessment_id': str(event.assessment.id) if event.assessment else None,
                'assessment_title': event.assessment.title if event.assessment else None,
                'assessment_type': event.assessment.assessment_type if event.assessment else None,
                'due_date': event.due_date.isoformat() if event.due_date else None,
                'submission_type': event.submission_type,
            }
            events_by_course[course_id]['events'].append(event_data)
        
        return list(events_by_course.values())
    
    def get_schedule_summary(self, teacher):
        """
        Get schedule summary statistics
        """
        from datetime import datetime, timedelta
        from django.db.models import Q
        
        now = datetime.now()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Total events
        total_events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).count()
        
        # This week's events (non-project events by start_time, project events by due_date)
        this_week_events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).filter(
            Q(start_time__date__gte=week_start, start_time__date__lte=week_end) |  # Non-project events
            Q(due_date__date__gte=week_start, due_date__date__lte=week_end)       # Project events
        ).count()
        
        # Today's events (non-project events by start_time, project events by due_date)
        today_events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).filter(
            Q(start_time__date=today) |  # Non-project events
            Q(due_date__date=today)     # Project events
        ).count()
        
        # Upcoming live classes
        upcoming_live_classes = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher,
            event_type='lesson',
            lesson_type='live',
            start_time__gte=now
        ).count()
        
        # Upcoming project deadlines
        upcoming_project_deadlines = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher,
            event_type='project',
            due_date__gte=now
        ).count()
        
        return {
            'total_events': total_events,
            'this_week_events': this_week_events,
            'today_events': today_events,
            'upcoming_live_classes': upcoming_live_classes,
            'upcoming_project_deadlines': upcoming_project_deadlines,
        }


class ProjectManagementView(APIView):
    """
    Teacher project management - CRUD operations for projects
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET: List all projects for the teacher's courses
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get query parameters for filtering
            course_id = request.query_params.get('course_id')
            status_filter = request.query_params.get('status')
            search = request.query_params.get('search')
            
            # Base queryset - projects from teacher's courses
            projects = Project.objects.filter(course__teacher=teacher).select_related('course')
            
            # Apply filters
            if course_id:
                projects = projects.filter(course_id=course_id)
            
            if search:
                projects = projects.filter(
                    Q(title__icontains=search) | 
                    Q(instructions__icontains=search) |
                    Q(course__title__icontains=search)
                )
            
            # Order by order field first, then by creation date
            projects = projects.order_by('order', '-created_at')
            
            # Serialize projects
            serializer = ProjectSerializer(projects, many=True, context={'request': request})
            
            # Get summary statistics
            summary = self._get_projects_summary(teacher)
            
            return Response({
                'projects': serializer.data,
                'summary': summary
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch projects', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """
        POST: Create a new project
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can create projects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = ProjectCreateUpdateSerializer(
                data=request.data, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                project = serializer.save()
                
                # Create submissions for all enrolled students
                # self._create_student_submissions(project)  # Disabled to prevent immediate submission creation
                
                response_serializer = ProjectSerializer(project, context={'request': request})
                return Response({
                    'project': response_serializer.data,
                    'message': 'Project created successfully'
                }, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to create project', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, project_id):
        """
        PUT: Update an existing project
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can update projects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            project = get_object_or_404(Project, id=project_id, course__teacher=teacher)
            
            serializer = ProjectCreateUpdateSerializer(
                project, 
                data=request.data, 
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                updated_project = serializer.save()
                
                response_serializer = ProjectSerializer(updated_project, context={'request': request})
                return Response({
                    'project': response_serializer.data,
                    'message': 'Project updated successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to update project', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, project_id):
        """
        DELETE: Delete a project
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can delete projects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            project = get_object_or_404(Project, id=project_id, course__teacher=teacher)
            
            # Check if there are any submissions
            submission_count = project.submissions.count()
            if submission_count > 0:
                return Response(
                    {'error': f'Cannot delete project with {submission_count} submissions. Please delete submissions first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            project_title = project.title
            project.delete()
            
            return Response({
                'message': f'Project "{project_title}" deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to delete project', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_projects_summary(self, teacher):
        """Get summary statistics for teacher's projects"""
        projects = Project.objects.filter(course__teacher=teacher)
        
        total_projects = projects.count()
        total_submissions = ProjectSubmission.objects.filter(project__course__teacher=teacher).count()
        graded_submissions = ProjectSubmission.objects.filter(
            project__course__teacher=teacher, 
            status='GRADED'
        ).count()
        pending_submissions = ProjectSubmission.objects.filter(
            project__course__teacher=teacher,
            status__in=['ASSIGNED', 'SUBMITTED', 'RETURNED']
        ).count()
        
        return {
            'total_projects': total_projects,
            'total_submissions': total_submissions,
            'graded_submissions': graded_submissions,
            'pending_submissions': pending_submissions,
            'grading_completion_rate': round((graded_submissions / total_submissions * 100), 1) if total_submissions > 0 else 0
        }
    
    def _create_student_submissions(self, project):
        """Create project submissions for all enrolled students"""
        try:
            # Get all enrolled students for this course
            enrolled_students = EnrolledCourse.objects.filter(
                course=project.course,
                status='active'
            ).select_related('student_profile__user')
            
            # Create submissions for each student
            submissions_to_create = []
            for enrollment in enrolled_students:
                submission = ProjectSubmission(
                    project=project,
                    student=enrollment.student_profile.user,
                    status='ASSIGNED'
                )
                submissions_to_create.append(submission)
            
            # Bulk create submissions
            if submissions_to_create:
                ProjectSubmission.objects.bulk_create(submissions_to_create)
                
        except Exception as e:
            print(f"Error creating student submissions: {str(e)}")


class ProjectGradingView(APIView):
    """
    Teacher project grading - Manage and grade project submissions
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        """
        GET: Get all submissions for a specific project
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify project belongs to teacher
            project = get_object_or_404(Project, id=project_id, course__teacher=teacher)
            
            # Get query parameters for filtering
            status_filter = request.query_params.get('status')
            search = request.query_params.get('search')
            
            # Get submissions for this project
            submissions = ProjectSubmission.objects.filter(project=project).select_related('student')
            
            # Apply filters
            if status_filter:
                submissions = submissions.filter(status=status_filter)
            
            if search:
                submissions = submissions.filter(
                    Q(student__first_name__icontains=search) |
                    Q(student__last_name__icontains=search) |
                    Q(student__email__icontains=search)
                )
            
            # Order by submission date
            submissions = submissions.order_by('-submitted_at', '-created_at')
            
            # Serialize submissions
            serializer = ProjectSubmissionSerializer(submissions, many=True)
            
            # Get project details
            project_serializer = ProjectSerializer(project, context={'request': request})
            
            # Get grading statistics
            stats = self._get_grading_stats(project)
            
            return Response({
                'project': project_serializer.data,
                'submissions': serializer.data,
                'grading_stats': stats
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch project submissions', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, submission_id):
        """
        PUT: Grade a project submission
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can grade submissions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get submission and verify it belongs to teacher's project
            submission = get_object_or_404(
                ProjectSubmission, 
                id=submission_id,
                project__course__teacher=teacher
            )
            
            serializer = ProjectSubmissionGradingSerializer(data=request.data)
            
            if serializer.is_valid():
                # Update submission with grading data
                submission.status = serializer.validated_data['status']
                submission.points_earned = serializer.validated_data.get('points_earned')
                submission.feedback = serializer.validated_data.get('feedback', '')
                submission.grader = teacher
                submission.graded_at = timezone.now()
                submission.save()
                
                response_serializer = ProjectSubmissionSerializer(submission)
                return Response({
                    'submission': response_serializer.data,
                    'message': 'Submission graded successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to grade submission', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_grading_stats(self, project):
        """Get grading statistics for a project"""
        submissions = ProjectSubmission.objects.filter(project=project)
        
        total_submissions = submissions.count()
        graded_count = submissions.filter(status='GRADED').count()
        pending_count = submissions.filter(status__in=['ASSIGNED', 'SUBMITTED', 'RETURNED']).count()
        
        # Calculate average score
        avg_score = submissions.filter(
            status='GRADED',
            points_earned__isnull=False
        ).aggregate(avg_score=Avg('points_earned'))['avg_score'] or 0
        
        return {
            'total_submissions': total_submissions,
            'graded_count': graded_count,
            'pending_count': pending_count,
            'average_score': round(float(avg_score), 1),
            'grading_progress': round((graded_count / total_submissions * 100), 1) if total_submissions > 0 else 0
        }


class ProjectSubmissionDetailView(APIView):
    """
    Detailed view for individual project submissions
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, submission_id):
        """
        GET: Get detailed view of a specific submission
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get submission and verify it belongs to teacher's project
            submission = get_object_or_404(
                ProjectSubmission, 
                id=submission_id,
                project__course__teacher=teacher
            )
            
            serializer = ProjectSubmissionSerializer(submission)
            
            # Get related data
            project_serializer = ProjectSerializer(submission.project, context={'request': request})
            
            return Response({
                'submission': serializer.data,
                'project': project_serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch submission details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, submission_id):
        """
        POST: Provide feedback on a submission
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can provide feedback'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get submission and verify it belongs to teacher's project
            submission = get_object_or_404(
                ProjectSubmission, 
                id=submission_id,
                project__course__teacher=teacher
            )
            
            serializer = ProjectSubmissionFeedbackSerializer(data=request.data)
            
            if serializer.is_valid():
                # Update submission with feedback
                submission.status = serializer.validated_data['status']
                submission.feedback = serializer.validated_data['feedback']
                submission.grader = teacher
                submission.graded_at = timezone.now()
                submission.save()
                
                response_serializer = ProjectSubmissionSerializer(submission)
                return Response({
                    'submission': response_serializer.data,
                    'message': 'Feedback provided successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to provide feedback', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProjectDashboardView(APIView):
    """
    Teacher project dashboard - Overview of all project-related activities
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET: Get comprehensive project dashboard data
        """
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get dashboard data
            dashboard_data = {
                'overview': self._get_overview_stats(teacher),
                'recent_projects': self._get_recent_projects(teacher),
                'pending_grading': self._get_pending_grading(teacher),
                'recent_submissions': self._get_recent_submissions(teacher),
                'course_projects': self._get_course_projects_summary(teacher)
            }
            
            return Response(dashboard_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch dashboard data', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_overview_stats(self, teacher):
        """Get overview statistics"""
        projects = Project.objects.filter(course__teacher=teacher)
        submissions = ProjectSubmission.objects.filter(project__course__teacher=teacher)
        
        return {
            'total_projects': projects.count(),
            'total_submissions': submissions.count(),
            'graded_submissions': submissions.filter(status='GRADED').count(),
            'pending_submissions': submissions.filter(status__in=['ASSIGNED', 'SUBMITTED', 'RETURNED']).count(),
            'overdue_submissions': submissions.filter(
                project__due_at__lt=timezone.now(),
                status__in=['ASSIGNED', 'SUBMITTED']
            ).count()
        }
    
    def _get_recent_projects(self, teacher):
        """Get recent projects"""
        projects = Project.objects.filter(
            course__teacher=teacher
        ).select_related('course').order_by('-created_at')[:5]
        
        return ProjectSerializer(projects, many=True, context={'request': self.request}).data
    
    def _get_pending_grading(self, teacher):
        """Get submissions pending grading"""
        submissions = ProjectSubmission.objects.filter(
            project__course__teacher=teacher,
            status__in=['SUBMITTED', 'RETURNED']
        ).select_related('project', 'student').order_by('-submitted_at')[:10]
        
        return ProjectSubmissionSerializer(submissions, many=True).data
    
    def _get_recent_submissions(self, teacher):
        """Get recent submissions"""
        submissions = ProjectSubmission.objects.filter(
            project__course__teacher=teacher
        ).select_related('project', 'student').order_by('-submitted_at')[:10]
        
        return ProjectSubmissionSerializer(submissions, many=True).data
    
    def _get_course_projects_summary(self, teacher):
        """Get projects summary by course"""
        courses = Course.objects.filter(teacher=teacher)
        course_summaries = []
        
        for course in courses:
            projects = Project.objects.filter(course=course)
            submissions = ProjectSubmission.objects.filter(project__course=course)
            
            course_summaries.append({
                'course_id': str(course.id),
                'course_title': course.title,
                'project_count': projects.count(),
                'submission_count': submissions.count(),
                'graded_count': submissions.filter(status='GRADED').count(),
                'pending_count': submissions.filter(status__in=['ASSIGNED', 'SUBMITTED', 'RETURNED']).count()
            })
        
        return course_summaries


class ProjectManagementView(APIView):
    """
    Project Management CBV - Complete CRUD operations for projects
    GET: List all projects for teacher's courses
    POST: Create a new project
    PUT: Update an existing project
    DELETE: Delete a project
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET: List all projects for teacher's courses
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access projects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get teacher's courses
            teacher_courses = Course.objects.filter(teacher=request.user)
            
            # Get projects for teacher's courses
            projects = Project.objects.filter(course__in=teacher_courses).select_related('course')
            
            # Apply filters
            course_id = request.query_params.get('course_id')
            if course_id:
                projects = projects.filter(course_id=course_id)
            
            search = request.query_params.get('search')
            if search:
                projects = projects.filter(
                    Q(title__icontains=search) |
                    Q(instructions__icontains=search) |
                    Q(course__title__icontains=search)
                )
            
            # Serialize projects
            serializer = ProjectSerializer(projects, many=True, context={'request': request})
            
            # Calculate summary statistics
            total_projects = projects.count()
            total_submissions = ProjectSubmission.objects.filter(project__in=projects).count()
            graded_submissions = ProjectSubmission.objects.filter(
                project__in=projects, status='GRADED'
            ).count()
            pending_submissions = ProjectSubmission.objects.filter(
                project__in=projects, status__in=['ASSIGNED', 'SUBMITTED', 'RETURNED']
            ).count()
            
            summary = {
                'total_projects': total_projects,
                'total_submissions': total_submissions,
                'graded_submissions': graded_submissions,
                'pending_submissions': pending_submissions,
                'grading_completion_rate': (graded_submissions / total_submissions * 100) if total_submissions > 0 else 0
            }
            
            return Response({
                'projects': serializer.data,
                'summary': summary
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving projects: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """
        POST: Create a new project
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can create projects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = ProjectCreateUpdateSerializer(
                data=request.data, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                project = serializer.save()
                
                # Create submissions for all enrolled students
                # self._create_student_submissions(project)  # Disabled to prevent immediate submission creation
                
                response_serializer = ProjectSerializer(project, context={'request': request})
                return Response({
                    'project': response_serializer.data,
                    'message': 'Project created successfully'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': f'Error creating project: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, project_id):
        """
        PUT: Update an existing project
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can update projects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get project and check ownership
            project = get_object_or_404(Project, id=project_id, course__teacher=request.user)
            
            serializer = ProjectCreateUpdateSerializer(
                project, 
                data=request.data, 
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                updated_project = serializer.save()
                response_serializer = ProjectSerializer(updated_project, context={'request': request})
                return Response({
                    'project': response_serializer.data,
                    'message': 'Project updated successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': f'Error updating project: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, project_id):
        """
        DELETE: Delete a project
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can delete projects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get project and check ownership
            project = get_object_or_404(Project, id=project_id, course__teacher=request.user)
            
            # Check if project has submissions and warn about deletion
            submission_count = project.submissions.count()
            if submission_count > 0:
                # Delete all submissions along with the project
                project.submissions.all().delete()
            
            # Store project data for response
            project_data = {
                'id': project.id,
                'title': project.title,
                'course': project.course.title
            }
            
            # Delete the project
            project.delete()
            
            response_data = {
                'message': 'Project deleted successfully',
                'deleted_project': project_data
            }
            
            if submission_count > 0:
                response_data['warning'] = f'Also deleted {submission_count} associated submissions'
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error deleting project: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _create_student_submissions(self, project):
        """
        Create ProjectSubmission records for all students enrolled in the project's course
        """
        try:
            # Get all students enrolled in the course
            enrollments = EnrolledCourse.objects.filter(course=project.course)
            
            # Create submissions for each enrolled student
            submissions_to_create = []
            for enrollment in enrollments:
                submission = ProjectSubmission(
                    project=project,
                    student=enrollment.student_profile.user,
                    status='ASSIGNED'
                )
                submissions_to_create.append(submission)
            
            # Bulk create submissions
            if submissions_to_create:
                ProjectSubmission.objects.bulk_create(submissions_to_create)
                
        except Exception as e:
            print(f"Error creating student submissions: {str(e)}")
            # Don't raise the exception as project creation should still succeed


# ===== ASSIGNMENT MANAGEMENT CBV =====

class AssignmentManagementView(APIView):
    """
    Complete CRUD operations for assignment management
    GET: List all assignments for teacher's courses
    POST: Create new assignment
    PUT: Update assignment
    DELETE: Delete assignment
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, assignment_id=None):
        """
        GET: List all assignments for teacher's courses OR get specific assignment
        If assignment_id is provided, return single assignment detail
        Query parameters (for list view):
        - course_id: Filter by specific course
        - lesson_id: Filter by specific lesson
        - assignment_type: Filter by assignment type
        - search: Search by title or description
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access assignment management'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # If assignment_id is provided, return single assignment detail
            if assignment_id:
                try:
                    assignment = Assignment.objects.prefetch_related(
                        'lessons', 'lessons__course', 'questions', 'submissions', 'submissions__student'
                    ).get(id=assignment_id)
                    
                    # Check if user teaches any lesson associated with this assignment
                    if not assignment.lessons.filter(course__teacher=request.user).exists():
                        return Response(
                            {'error': 'Assignment not found or you do not have permission'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    
                    serializer = AssignmentDetailSerializer(assignment, context={'request': request})
                    return Response({
                        'assignment': serializer.data
                    }, status=status.HTTP_200_OK)
                    
                except Assignment.DoesNotExist:
                    return Response(
                        {'error': 'Assignment not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Get assignments for teacher's courses
            assignments = Assignment.objects.filter(
                lessons__course__teacher=request.user
            ).prefetch_related('lessons', 'lessons__course', 'questions', 'submissions')
            
            # Apply filters
            course_id = request.query_params.get('course_id')
            if course_id:
                assignments = assignments.filter(lessons__course_id=course_id)
            
            lesson_id = request.query_params.get('lesson_id')
            if lesson_id:
                assignments = assignments.filter(lessons__id=lesson_id)
            
            assignment_type = request.query_params.get('assignment_type')
            if assignment_type:
                assignments = assignments.filter(assignment_type=assignment_type)
            
            search = request.query_params.get('search')
            if search:
                assignments = assignments.filter(
                    Q(title__icontains=search) | Q(description__icontains=search)
                )
            
            # Serialize and return
            serializer = AssignmentListSerializer(assignments, many=True, context={'request': request})
            return Response({
                'assignments': serializer.data,
                'total_count': assignments.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving assignments: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """
        POST: Create a new assignment
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can create assignments'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Use serializer for validation and creation
            serializer = AssignmentCreateUpdateSerializer(
                data=request.data, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                assignment = serializer.save()
                
                # Return detailed assignment data
                response_serializer = AssignmentDetailSerializer(assignment, context={'request': request})
                return Response({
                    'assignment': response_serializer.data,
                    'message': 'Assignment created successfully'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': f'Error creating assignment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, assignment_id=None):
        """
        PUT: Update an existing assignment
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can update assignments'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment_id from URL parameter or request data
            if not assignment_id:
                assignment_id = request.data.get('assignment_id')
            
            if not assignment_id:
                return Response(
                    {'error': 'Assignment ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to update it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to update it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Use serializer for validation and updating
            serializer = AssignmentCreateUpdateSerializer(
                assignment, 
                data=request.data, 
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                updated_assignment = serializer.save()
                
                # Return detailed assignment data
                response_serializer = AssignmentDetailSerializer(updated_assignment, context={'request': request})
                return Response({
                    'assignment': response_serializer.data,
                    'message': 'Assignment updated successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': f'Error updating assignment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, assignment_id=None):
        """
        DELETE: Delete an assignment
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can delete assignments'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment_id from URL parameter or request data
            if not assignment_id:
                assignment_id = request.data.get('assignment_id')
            
            if not assignment_id:
                return Response(
                    {'error': 'Assignment ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to delete it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to delete it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if assignment has submissions
            submission_count = assignment.submissions.count()
            if submission_count > 0:
                return Response(
                    {'error': f'Cannot delete assignment with {submission_count} submissions. Please delete submissions first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Store assignment data for response
            first_lesson = assignment.lessons.first()
            assignment_data = {
                'id': str(assignment.id),
                'title': assignment.title,
                'lesson': first_lesson.title if first_lesson else 'N/A',
                'course': first_lesson.course.title if first_lesson else 'N/A'
            }
            
            # Delete the assignment
            assignment.delete()
            
            return Response({
                'message': 'Assignment deleted successfully',
                'deleted_assignment': assignment_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error deleting assignment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssignmentQuestionManagementView(APIView):
    """
    CRUD operations for assignment questions
    GET: List questions for specific assignment
    POST: Create new question
    PUT: Update question
    DELETE: Delete question
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, assignment_id):
        """
        GET: List questions for specific assignment
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access assignment questions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to access it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to access it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get questions ordered by order field
            questions = assignment.questions.all().order_by('order')
            serializer = AssignmentQuestionSerializer(questions, many=True)
            
            return Response({
                'assignment_id': str(assignment.id),
                'assignment_title': assignment.title,
                'questions': serializer.data,
                'total_questions': questions.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving assignment questions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, assignment_id):
        """
        POST: Create new question for assignment
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can create assignment questions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to modify it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to modify it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Add assignment to request data
            request.data['assignment'] = assignment.id
            
            # Use serializer for validation and creation
            serializer = AssignmentQuestionSerializer(data=request.data)
            
            if serializer.is_valid():
                question = serializer.save(assignment=assignment)
                
                response_serializer = AssignmentQuestionSerializer(question)
                return Response({
                    'question': response_serializer.data,
                    'message': 'Question created successfully'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': f'Error creating assignment question: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, assignment_id, question_id):
        """
        PUT: Update assignment question
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can update assignment questions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to modify it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to modify it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get question and check it belongs to assignment
            try:
                question = AssignmentQuestion.objects.get(
                    id=question_id, 
                    assignment=assignment
                )
            except AssignmentQuestion.DoesNotExist:
                return Response(
                    {'error': 'Question not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Use serializer for validation and updating
            serializer = AssignmentQuestionSerializer(
                question, 
                data=request.data, 
                partial=True
            )
            
            if serializer.is_valid():
                updated_question = serializer.save()
                
                response_serializer = AssignmentQuestionSerializer(updated_question)
                return Response({
                    'question': response_serializer.data,
                    'message': 'Question updated successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': f'Error updating assignment question: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, assignment_id, question_id):
        """
        DELETE: Delete assignment question
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can delete assignment questions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to modify it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to modify it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get question and check it belongs to assignment
            try:
                question = AssignmentQuestion.objects.get(
                    id=question_id, 
                    assignment=assignment
                )
            except AssignmentQuestion.DoesNotExist:
                return Response(
                    {'error': 'Question not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Store question data for response
            question_data = {
                'id': str(question.id),
                'question_text': question.question_text[:50] + '...',
                'order': question.order
            }
            
            # Delete the question
            question.delete()
            
            return Response({
                'message': 'Question deleted successfully',
                'deleted_question': question_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error deleting assignment question: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssignmentGradingView(APIView):
    """
    Assignment grading and submission management
    GET: List submissions for assignment
    PUT: Grade submission
    POST: Provide feedback
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, assignment_id, submission_id=None):
        """
        GET: List all submissions for a specific assignment OR get specific submission
        If submission_id is provided, return single submission detail
        Query parameters (for list view):
        - status: Filter by grading status (graded, pending)
        - search: Search by student name or email
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access assignment grading'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # If submission_id is provided, return single submission detail
            if submission_id:
                try:
                    assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                    # Check if user teaches any lesson associated with this assignment
                    if not assignment.lessons.filter(course__teacher=request.user).exists():
                        return Response(
                            {'error': 'Assignment not found or you do not have permission to access it'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    
                    submission = AssignmentSubmission.objects.select_related(
                        'student', 'graded_by'
                    ).get(
                        id=submission_id,
                        assignment=assignment
                    )
                    
                    serializer = AssignmentSubmissionSerializer(submission)
                    return Response({
                        'submission': serializer.data
                    }, status=status.HTTP_200_OK)
                    
                except Assignment.DoesNotExist:
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to access it'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                except AssignmentSubmission.DoesNotExist:
                    return Response(
                        {'error': 'Submission not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to access it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to access it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get submissions
            submissions = assignment.submissions.all().select_related(
                'student', 'graded_by'
            ).order_by('-submitted_at')
            
            # Apply filters
            status_filter = request.query_params.get('status')
            if status_filter == 'graded':
                submissions = submissions.filter(is_graded=True)
            elif status_filter == 'pending':
                submissions = submissions.filter(is_graded=False)
            
            search = request.query_params.get('search')
            if search:
                submissions = submissions.filter(
                    Q(student__first_name__icontains=search) |
                    Q(student__last_name__icontains=search) |
                    Q(student__email__icontains=search)
                )
            
            # Serialize and return
            serializer = AssignmentSubmissionSerializer(submissions, many=True)
            
            # Calculate grading stats
            total_submissions = assignment.submissions.count()
            graded_count = assignment.submissions.filter(is_graded=True).count()
            pending_count = total_submissions - graded_count
            
            return Response({
                'assignment_id': str(assignment.id),
                'assignment_title': assignment.title,
                'submissions': serializer.data,
                'grading_stats': {
                    'total_submissions': total_submissions,
                    'graded_count': graded_count,
                    'pending_count': pending_count,
                    'grading_progress': (graded_count / total_submissions * 100) if total_submissions > 0 else 0
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving assignment submissions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, assignment_id, submission_id):
        """
        PUT: Grade an assignment submission
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can grade assignments'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to grade it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to grade it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get submission and check it belongs to assignment
            try:
                submission = AssignmentSubmission.objects.get(
                    id=submission_id, 
                    assignment=assignment
                )
            except AssignmentSubmission.DoesNotExist:
                return Response(
                    {'error': 'Submission not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Use grading serializer for validation and updating
            serializer = AssignmentGradingSerializer(
                submission, 
                data=request.data, 
                partial=True
            )
            
            if serializer.is_valid():
                # Only set grader and grading timestamp if it's actually graded
                save_kwargs = {}
                is_graded = serializer.validated_data.get('is_graded', False)
                if is_graded:
                    save_kwargs['graded_by'] = request.user
                    save_kwargs['graded_at'] = timezone.now()
                
                updated_submission = serializer.save(**save_kwargs)
                
                # Update assignment performance metrics
                try:
                    # Get the student's enrollment for this course
                    from student.models import EnrolledCourse
                    first_lesson = assignment.lessons.first()
                    if not first_lesson:
                        return Response(
                            {'error': 'Assignment has no associated lesson'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    enrollment = EnrolledCourse.objects.get(
                        student_profile__user=submission.student,
                        course=first_lesson.course
                    )
                    
                    # Calculate assignment score percentage
                    if updated_submission.points_possible > 0:
                        assignment_score = (updated_submission.points_earned / updated_submission.points_possible) * 100
                    else:
                        assignment_score = 0
                    
                    # Update performance metrics
                    enrollment.update_assignment_performance(assignment_score, is_graded)
                    
                except Exception as e:
                    print(f"Error updating assignment performance metrics: {e}")
                    # Don't fail the request if metrics update fails
                
                response_serializer = AssignmentSubmissionSerializer(updated_submission)
                return Response({
                    'submission': response_serializer.data,
                    'message': 'Submission graded successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': f'Error grading assignment submission: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, assignment_id, submission_id):
        """
        POST: Provide feedback on an assignment submission
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can provide feedback on assignments'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(id=assignment_id)
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to provide feedback'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to provide feedback'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get submission and check it belongs to assignment
            try:
                submission = AssignmentSubmission.objects.get(
                    id=submission_id, 
                    assignment=assignment
                )
            except AssignmentSubmission.DoesNotExist:
                return Response(
                    {'error': 'Submission not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Use feedback serializer for validation and updating
            serializer = AssignmentFeedbackSerializer(
                submission, 
                data=request.data, 
                partial=True
            )
            
            if serializer.is_valid():
                updated_submission = serializer.save()
                
                response_serializer = AssignmentSubmissionSerializer(updated_submission)
                return Response({
                    'submission': response_serializer.data,
                    'message': 'Feedback provided successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': f'Error providing feedback: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssignmentAIGradingView(APIView):
    """
    AI-powered assignment grading endpoint.
    
    POST: Grade assignment submission using AI
    - Receives questions array from frontend
    - Returns grades (points_earned, feedback) for each question
    - NO database save - frontend handles state and saving
    
    Endpoint: POST /api/teacher/assignments/{assignment_id}/grading/{submission_id}/ai-grade
    
    Request Body:
    {
        "questions": [
            {
                "question_id": "uuid",
                "question_text": "...",
                "question_type": "essay" | "fill_blank" | "short_answer",
                "student_answer": "...",
                "points_possible": 5,
                "correct_answer": "...",  // Optional
                "explanation": "...",  // Optional
                "rubric": "..."  // Optional, for essays
            }
        ],
        "assignment_context": {  // Optional
            "passage_text": "...",
            "lesson_content": "...",
            "learning_objectives": [...]
        }
    }
    
    Response:
    {
        "grades": [
            {
                "question_id": "uuid",
                "points_earned": 3.0,
                "points_possible": 5,
                "feedback": "...",
                "confidence": 0.85
            }
        ],
        "total_score": 17.0,
        "total_possible": 25
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, assignment_id, submission_id):
        """
        POST: AI-grade assignment submission.
        
        Receives questions from frontend, returns grades.
        Does NOT save to database - frontend manages state.
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can use AI grading'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get assignment and check ownership
            try:
                assignment = Assignment.objects.prefetch_related('lessons', 'lessons__course').get(
                    id=assignment_id
                )
                # Check if user teaches any lesson associated with this assignment
                if not assignment.lessons.filter(course__teacher=request.user).exists():
                    return Response(
                        {'error': 'Assignment not found or you do not have permission to grade it'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {'error': 'Assignment not found or you do not have permission to grade it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get submission and check it belongs to assignment
            try:
                submission = AssignmentSubmission.objects.select_related('student').get(
                    id=submission_id, 
                    assignment=assignment
                )
            except AssignmentSubmission.DoesNotExist:
                return Response(
                    {'error': 'Submission not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Validate request data
            questions_data = request.data.get('questions', [])
            if not questions_data:
                return Response(
                    {'error': 'Questions array is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get assignment context (optional)
            assignment_context = request.data.get('assignment_context')
            
            # If no context provided, try to extract from assignment
            if not assignment_context:
                assignment_context = {}
                try:
                    first_lesson = assignment.lessons.first()
                    if first_lesson:
                        assignment_context['lesson_title'] = first_lesson.title
                        if hasattr(first_lesson, 'content'):
                            assignment_context['lesson_content'] = first_lesson.content
                        if hasattr(first_lesson, 'description'):
                            assignment_context['lesson_description'] = first_lesson.description
                        
                        course = first_lesson.course
                        assignment_context['course_title'] = course.title
                    assignment_context['assignment_title'] = assignment.title
                    assignment_context['assignment_description'] = assignment.description
                except Exception as e:
                    logger.warning(f"Failed to extract assignment context: {e}")
            
            # Initialize grader
            grader = GeminiGrader()
            
            # Grade questions batch
            result = grader.grade_questions_batch(
                questions=questions_data,
                assignment_context=assignment_context if assignment_context else None
            )
            
            return Response({
                'grades': result['grades'],
                'total_score': result['total_score'],
                'total_possible': result['total_possible']
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            logger.error(f"Error in AI grading: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during AI grading: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AIGenerateCourseIntroductionView(APIView):
    """
    REST API endpoint for generating course introduction using AI.
    
    POST: Generate course introduction
    - Receives system_instruction and course context from frontend
    - Returns generated course introduction data (not saved to DB)
    
    Endpoint: POST /api/teacher/courses/{course_id}/ai/generate-introduction/
    
    Request Body:
    {
        "system_instruction": "You are an expert course creator...",
        "temperature": 0.7  // Optional
    }
    
    Response:
    {
        "overview": "...",
        "learning_objectives": [...],
        "prerequisites_text": [...],
        "duration_weeks": 8,
        "sessions_per_week": 2,
        "total_projects": 5,
        "max_students": 12,
        "value_propositions": [...]
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, course_id):
        """
        POST: Generate course introduction using AI.
        
        Does NOT save to database - frontend handles saving.
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can use AI generation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get course and check ownership
            try:
                course = Course.objects.select_related('teacher').get(
                    id=course_id,
                    teacher=request.user
                )
            except Course.DoesNotExist:
                return Response(
                    {'error': 'Course not found or you do not have permission'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Validate request data
            system_instruction = request.data.get('system_instruction', '').strip()
            if not system_instruction:
                # Provide default system instruction if not provided
                system_instruction = """You are an expert course creator specializing in educational content.
Generate comprehensive course introductions that are engaging, clear, and informative.
Focus on creating value for students and highlighting what makes the course unique."""
            
            temperature = float(request.data.get('temperature', 0.7))
            
            # Initialize service
            service = GeminiCourseIntroductionService()
            
            # Generate course introduction
            result = service.generate(
                system_instruction=system_instruction,
                course_title=course.title,
                course_description=course.long_description or course.description or '',
                temperature=temperature
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Validation error in AI course introduction generation: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            logger.error(f"Error in AI course introduction generation: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during AI generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AIGenerateCourseDetailView(APIView):
    """
    REST API endpoint for generating course details using AI.
    
    POST: Generate course details
    - Receives system_instruction, user_request, and optional persona from frontend
    - Returns generated course detail data (not saved to DB)
    
    Endpoint: POST /api/teacher/courses/{course_id}/ai/generate-course-detail/
    
    Request Body:
    {
        "system_instruction": "You are an expert course creator...",
        "user_request": "Create a course on Python programming for beginners",
        "persona": "fun and engaging",  // Optional
        "temperature": 0.7  // Optional
    }
    
    Response:
    {
        "title": "...",
        "short_description": "...",
        "detailed_description": "...",
        "category": "...",
        "difficulty_level": "beginner"
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, course_id):
        """
        POST: Generate course details using AI.
        
        Does NOT save to database - frontend handles saving.
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can use AI generation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get course and check ownership (optional - course might not exist yet)
            # If course doesn't exist, we'll still allow generation for new courses
            course = None
            if course_id:
                try:
                    course = Course.objects.select_related('teacher').get(
                        id=course_id,
                        teacher=request.user
                    )
                except Course.DoesNotExist:
                    # Allow generation even if course doesn't exist (for new course creation)
                    pass
            
            # Validate request data
            system_instruction = request.data.get('system_instruction', '').strip()
            if not system_instruction:
                return Response(
                    {'error': 'system_instruction is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_request = request.data.get('user_request', '').strip()
            if not user_request:
                return Response(
                    {'error': 'user_request is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            persona = request.data.get('persona', '').strip() or None
            temperature = float(request.data.get('temperature', 0.7))
            
            # Initialize service
            from ai.gemini_course_detail_service import GeminiCourseDetailService
            service = GeminiCourseDetailService()
            
            # Generate course details
            result = service.generate(
                system_instruction=system_instruction,
                user_request=user_request,
                persona=persona,
                temperature=temperature
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Validation error in AI course detail generation: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            logger.error(f"Error in AI course detail generation: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during AI generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AIGenerateCourseLessonsView(APIView):
    """
    REST API endpoint for generating course lessons using AI.
    
    POST: Generate course lessons
    - Receives system_instruction and course context from frontend
    - Returns generated lessons data (not saved to DB)
    
    Endpoint: POST /api/teacher/courses/{course_id}/ai/generate-lessons/
    
    Request Body:
    {
        "system_instruction": "You are an expert curriculum designer...",
        "duration_weeks": 8,  // Optional
        "sessions_per_week": 2,  // Optional
        "temperature": 0.7  // Optional
    }
    
    Response:
    {
        "lessons": [
            {
                "title": "...",
                "description": "...",
                "order": 1,
                "type": "live_class",
                "duration": 45
            },
            ...
        ]
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, course_id):
        """
        POST: Generate course lessons using AI.
        
        Does NOT save to database - frontend handles saving.
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can use AI generation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get course and check ownership
            try:
                course = Course.objects.select_related('teacher').get(
                    id=course_id,
                    teacher=request.user
                )
            except Course.DoesNotExist:
                return Response(
                    {'error': 'Course not found or you do not have permission'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Validate request data
            system_instruction = request.data.get('system_instruction', '').strip()
            if not system_instruction:
                # Provide default system instruction if not provided
                system_instruction = """You are an expert curriculum designer specializing in creating structured, progressive learning experiences.
Generate comprehensive lesson outlines that build upon each other in a scaffolded manner.
Each lesson should be clear, focused, and contribute to the overall course learning objectives."""
            
            temperature = float(request.data.get('temperature', 0.7))
            duration_weeks = request.data.get('duration_weeks')
            sessions_per_week = request.data.get('sessions_per_week')
            
            # Initialize service
            service = GeminiCourseLessonsService()
            
            # Generate lessons
            result = service.generate(
                system_instruction=system_instruction,
                course_title=course.title,
                course_description=course.long_description or course.description or '',
                duration_weeks=duration_weeks,
                sessions_per_week=sessions_per_week,
                temperature=temperature
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Validation error in AI lessons generation: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            logger.error(f"Error in AI lessons generation: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during AI generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VideoMaterialView(APIView):
    """
    API view for managing video materials.
    Handles creating video materials and checking for existing transcriptions.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Create a new video material or get existing one by URL.
        Checks if transcript already exists for this video URL.
        """
        try:
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can create video materials'},
                    status=status.HTTP_403_FORBIDDEN
                )

            video_url = request.data.get('video_url', '').strip()
            lesson_material_id = request.data.get('lesson_material_id')  # Optional

            if not video_url:
                return Response(
                    {'error': 'video_url is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Always create a new video material instance
            # Each LessonMaterial gets its own VideoMaterial with independent transcript
            create_data = {'video_url': video_url}
            if lesson_material_id:
                create_data['lesson_material'] = lesson_material_id

            serializer = VideoMaterialCreateSerializer(data=create_data)
            if serializer.is_valid():
                video_material = serializer.save()

                # Extract video ID and detect if YouTube
                transcription_service = VideoTranscriptionService()
                if transcription_service._is_youtube_url(video_url):
                    video_material.is_youtube = True
                    video_material.video_id = transcription_service._extract_youtube_id(video_url)
                    video_material.save()

                result_serializer = VideoMaterialSerializer(video_material)
                return Response(result_serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            import traceback
            logger.error(f"Error creating video material: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error creating video material: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request, video_material_id=None):
        """
        Get video material by ID or by video_url query parameter
        """
        try:
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access video materials'},
                    status=status.HTTP_403_FORBIDDEN
                )

            video_material = None

            if video_material_id:
                try:
                    video_material = VideoMaterial.objects.get(id=video_material_id)
                except VideoMaterial.DoesNotExist:
                    return Response(
                        {'error': 'Video material not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            elif request.query_params.get('video_url'):
                video_url = request.query_params.get('video_url')
                lesson_material_id = request.query_params.get('lesson_material_id')
                
                # Since video_url is no longer unique, we need lesson_material_id to identify the specific VideoMaterial
                if not lesson_material_id:
                    return Response(
                        {'error': 'lesson_material_id query parameter is required when querying by video_url'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                try:
                    video_material = VideoMaterial.objects.get(
                        video_url=video_url,
                        lesson_material_id=lesson_material_id
                    )
                except VideoMaterial.DoesNotExist:
                    return Response(
                        {'error': 'Video material not found for this URL and lesson material'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                except VideoMaterial.MultipleObjectsReturned:
                    # This shouldn't happen, but handle it just in case
                    video_material = VideoMaterial.objects.filter(
                        video_url=video_url,
                        lesson_material_id=lesson_material_id
                    ).first()
                    if not video_material:
                        return Response(
                            {'error': 'Video material not found for this URL and lesson material'},
                            status=status.HTTP_404_NOT_FOUND
                        )
            else:
                return Response(
                    {'error': 'video_material_id or video_url query parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = VideoMaterialSerializer(video_material)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting video material: {e}", exc_info=True)
            return Response(
                {'error': f'Error getting video material: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, video_material_id):
        """
        PUT: Update video material (especially transcript and availability settings).
        Allows teachers to edit transcript and toggle student visibility.
        """
        try:
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can update video materials'},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                video_material = VideoMaterial.objects.get(id=video_material_id)
            except VideoMaterial.DoesNotExist:
                return Response(
                    {'error': 'Video material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if user owns the lesson this material belongs to
            if video_material.lesson_material:
                lesson = video_material.lesson_material.lessons.first()
                if lesson and lesson.course.teacher != request.user:
                    return Response(
                        {'error': 'You do not have permission to update this video material'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            # Convert lesson_material_id to lesson_material if provided
            update_data = request.data.copy()
            if 'lesson_material_id' in update_data:
                lesson_material_id = update_data.pop('lesson_material_id')
                try:
                    lesson_material = LessonMaterial.objects.get(id=lesson_material_id, material_type='video')
                    # Verify teacher owns the lesson
                    lesson = lesson_material.lessons.first()
                    if lesson and lesson.course.teacher != request.user:
                        return Response(
                            {'error': 'You do not have permission to link this video material to this lesson'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    update_data['lesson_material'] = lesson_material_id
                except LessonMaterial.DoesNotExist:
                    return Response(
                        {'error': 'Lesson material not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Update using serializer (partial update)
            serializer = VideoMaterialSerializer(video_material, data=update_data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            updated_material = serializer.save()
            
            logger.info(f"Updated video material {video_material_id} by teacher {request.user.id}")

            return Response({
                'video_material': VideoMaterialSerializer(updated_material).data,
                'message': 'Video material updated successfully'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error updating video material: {e}", exc_info=True)
            return Response(
                {'error': f'Error updating video material: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VideoMaterialTranscribeView(APIView):
    """
    API view for transcribing video materials.
    Uses VideoTranscriptionService and caches the result.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, video_material_id):
        """
        Transcribe a video material.
        Checks cache first, then transcribes if needed.
        """
        try:
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can transcribe videos'},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                video_material = VideoMaterial.objects.get(id=video_material_id)
            except VideoMaterial.DoesNotExist:
                return Response(
                    {'error': 'Video material not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if already transcribed
            if video_material.has_transcript:
                logger.info(f"Video material {video_material_id} already has transcript")
                serializer = VideoMaterialSerializer(video_material)
                return Response({
                    'video_material': serializer.data,
                    'message': 'Transcript already exists',
                    'from_cache': True
                }, status=status.HTTP_200_OK)

            # Validate request data
            transcribe_serializer = VideoMaterialTranscribeSerializer(data=request.data)
            if not transcribe_serializer.is_valid():
                return Response(transcribe_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            language_codes = transcribe_serializer.validated_data.get('language_codes')

            # Transcribe using VideoTranscriptionService
            transcription_service = VideoTranscriptionService()
            result = transcription_service.transcribe_video(
                video_material.video_url,
                language_codes=language_codes
            )

            if result['success']:
                # Update video material with transcript
                video_material.transcript = result['transcript']
                video_material.language = result.get('language')
                video_material.method_used = result['method']
                video_material.transcript_length = len(result['transcript'])
                video_material.word_count = len(result['transcript'].split())
                if result.get('language'):
                    # Try to get language name (simplified)
                    language_map = {
                        'en': 'English',
                        'es': 'Spanish',
                        'fr': 'French',
                        'de': 'German',
                        'it': 'Italian',
                        'pt': 'Portuguese'
                    }
                    video_material.language_name = language_map.get(result['language'], result['language'])
                video_material.save()

                logger.info(f"Successfully transcribed video material {video_material_id} using {result['method']}")

                serializer = VideoMaterialSerializer(video_material)
                return Response({
                    'video_material': serializer.data,
                    'message': 'Transcript generated successfully',
                    'from_cache': False
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': result.get('error', 'Failed to transcribe video')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            import traceback
            logger.error(f"Error transcribing video material: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error transcribing video: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentUploadView(APIView):
    """
    API view for uploading document files to Google Cloud Storage.
    Handles file upload, validation, and creates DocumentMaterial instance.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Upload a document file to GCS and create DocumentMaterial instance.
        
        Expected request:
        - file: File object (PDF, DOCX, DOC, TXT)
        - lesson_material_id: UUID (optional, for linking to existing LessonMaterial)
        
        Returns:
        - file_url: GCS URL
        - file_size: Size in bytes
        - file_size_mb: Size in MB
        - file_extension: File extension
        - file_name: Stored filename
        - original_filename: Original filename
        - mime_type: MIME type
        - document_material_id: UUID of created DocumentMaterial
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can upload documents'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get uploaded file
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                return Response(
                    {'error': 'No file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file size (max 50MB)
            max_size = 50 * 1024 * 1024  # 50MB in bytes
            if uploaded_file.size > max_size:
                return Response(
                    {'error': f'File size exceeds maximum allowed size of 50MB. File size: {round(uploaded_file.size / (1024 * 1024), 2)}MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file extension
            original_filename = uploaded_file.name
            file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
            allowed_extensions = ['pdf', 'docx', 'doc', 'txt']
            
            if file_extension not in allowed_extensions:
                return Response(
                    {'error': f'File extension "{file_extension}" not allowed. Allowed extensions: {", ".join(allowed_extensions)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine MIME type
            mime_type_map = {
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'doc': 'application/msword',
                'txt': 'text/plain'
            }
            mime_type = mime_type_map.get(file_extension, 'application/octet-stream')

            # Generate unique filename for storage
            import uuid
            unique_filename = f"{uuid.uuid4()}-{original_filename}"
            storage_path = f"documents/{unique_filename}"

            # Upload to GCS (REQUIRED - no local fallback for documents)
            from django.core.files.storage import default_storage
            from django.conf import settings
            
            # Check if GCS is configured
            if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
                return Response(
                    {'error': 'Google Cloud Storage is not configured. Please set GCS_BUCKET_NAME and GCS_PROJECT_ID environment variables.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            try:
                # Save file to GCS storage
                saved_path = default_storage.save(storage_path, uploaded_file)
                
                # Get file URL from GCS
                file_url = default_storage.url(saved_path)
                # Ensure full URL format for GCS
                if not file_url.startswith('http'):
                    file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
                
                logger.info(f"File uploaded successfully: {saved_path}")
                
            except Exception as e:
                logger.error(f"Error uploading file to storage: {e}")
                return Response(
                    {'error': f'Failed to upload file: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Get optional lesson_material_id
            lesson_material_id = request.data.get('lesson_material_id')
            lesson_material = None
            
            if lesson_material_id:
                try:
                    lesson_material = LessonMaterial.objects.get(
                        id=lesson_material_id,
                        material_type='document'
                    )
                except LessonMaterial.DoesNotExist:
                    return Response(
                        {'error': f'LessonMaterial with id {lesson_material_id} not found or not a document type'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Create DocumentMaterial instance
            try:
                document_material = DocumentMaterial.objects.create(
                    file_name=saved_path,
                    original_filename=original_filename,
                    file_url=file_url,
                    file_size=uploaded_file.size,
                    file_extension=file_extension,
                    mime_type=mime_type,
                    uploaded_by=request.user,
                    lesson_material=lesson_material
                )
                
                logger.info(f"DocumentMaterial created: {document_material.id}")
                
            except Exception as e:
                logger.error(f"Error creating DocumentMaterial: {e}")
                # Try to delete uploaded file if DocumentMaterial creation fails
                try:
                    default_storage.delete(saved_path)
                except:
                    pass
                return Response(
                    {'error': f'Failed to create document material: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Return success response
            return Response({
                'file_url': file_url,
                'file_size': uploaded_file.size,
                'file_size_mb': round(uploaded_file.size / (1024 * 1024), 2),
                'file_extension': file_extension,
                'file_name': saved_path,
                'original_filename': original_filename,
                'mime_type': mime_type,
                'document_material_id': str(document_material.id),
                'message': 'File uploaded successfully'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            logger.error(f"Error in document upload: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during file upload: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AudioVideoUploadView(APIView):
    """
    API view for uploading audio/video files to Google Cloud Storage.
    Handles file upload, validation, and creates AudioVideoMaterial instance.
    Supports file replacement - deletes old file when new one is uploaded.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Upload an audio/video file to GCS and create AudioVideoMaterial instance.
        
        Expected request:
        - file: File object (MP3, MP4, WAV, OGG, WebM, etc.)
        - lesson_material_id: UUID (optional, for linking to existing LessonMaterial)
        
        Returns:
        - file_url: GCS URL
        - file_size: Size in bytes
        - file_size_mb: Size in MB
        - file_extension: File extension
        - file_name: Stored filename
        - original_filename: Original filename
        - mime_type: MIME type
        - audio_video_material_id: UUID of created AudioVideoMaterial
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can upload audio/video files'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get uploaded file
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                return Response(
                    {'error': 'No file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file size (max 500MB for videos)
            max_size = 500 * 1024 * 1024  # 500MB in bytes
            if uploaded_file.size > max_size:
                return Response(
                    {'error': f'File size exceeds maximum allowed size of 500MB. File size: {round(uploaded_file.size / (1024 * 1024), 2)}MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file extension and MIME type
            import mimetypes
            original_filename = uploaded_file.name
            
            # CRITICAL: Database column is VARCHAR(200), so we MUST truncate to 200 chars max
            # Truncate original filename early to prevent database errors
            max_original_filename_length = 200
            if len(original_filename) > max_original_filename_length:
                # Keep extension and truncate the base name
                if '.' in original_filename:
                    name_part, ext_part = original_filename.rsplit('.', 1)
                    max_name_length = max_original_filename_length - len(ext_part) - 1  # -1 for the dot
                    if max_name_length < 1:
                        # If extension is too long, just use first 200 chars
                        original_filename = original_filename[:max_original_filename_length]
                    else:
                        truncated_name = name_part[:max_name_length] if len(name_part) > max_name_length else name_part
                        original_filename = f"{truncated_name}.{ext_part}"
                else:
                    original_filename = original_filename[:max_original_filename_length]
            
            file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
            
            # Allowed extensions
            allowed_audio_extensions = ['mp3', 'wav', 'ogg', 'aac', 'm4a']
            allowed_video_extensions = ['mp4', 'webm', 'ogg', 'mov', 'avi', 'wmv']
            allowed_extensions = allowed_audio_extensions + allowed_video_extensions
            
            if file_extension not in allowed_extensions:
                return Response(
                    {'error': f'File extension "{file_extension}" not allowed. Allowed extensions: {", ".join(allowed_extensions)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine MIME type
            mime_type = uploaded_file.content_type or mimetypes.guess_type(original_filename)[0]
            
            # MIME type mapping
            mime_type_map = {
                'mp3': 'audio/mpeg',
                'mp4': 'video/mp4',
                'wav': 'audio/wav',
                'ogg': 'audio/ogg',
                'webm': 'video/webm',
                'aac': 'audio/aac',
                'm4a': 'audio/m4a',
                'mov': 'video/quicktime',
                'avi': 'video/x-msvideo',
                'wmv': 'video/x-ms-wmv',
            }
            
            if not mime_type:
                mime_type = mime_type_map.get(file_extension, 'application/octet-stream')
            
            # Validate MIME type
            allowed_audio_mimes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 'audio/ogg', 'audio/aac', 'audio/m4a']
            allowed_video_mimes = ['video/mp4', 'video/webm', 'video/ogg', 'video/quicktime', 'video/x-msvideo', 'video/x-ms-wmv']
            allowed_mimes = allowed_audio_mimes + allowed_video_mimes
            
            if mime_type not in allowed_mimes:
                return Response(
                    {'error': f'MIME type "{mime_type}" not allowed. Allowed types: audio/video files'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate unique filename for storage
            import uuid
            # CRITICAL: Database file_name column is VARCHAR(200), not 255!
            # UUID is 36 chars + 1 dash = 37 chars
            # Storage path prefix "audio-video/" is 13 chars
            # Total prefix overhead: 13 + 37 = 50 chars
            # Available for filename: 200 - 50 = 150 chars
            # But original_filename is already truncated to 200, so we need to truncate it further
            # to fit in the storage path
            max_filename_for_path = 150  # 200 - 50 (prefix overhead)
            if len(original_filename) > max_filename_for_path:
                # Truncate further for the storage path
                if '.' in original_filename:
                    name_part, ext_part = original_filename.rsplit('.', 1)
                    max_name_length = max_filename_for_path - len(ext_part) - 1
                    if max_name_length < 1:
                        # Fallback: use UUID only with extension
                        unique_filename = f"{uuid.uuid4()}.{ext_part}"
                    else:
                        truncated_name = name_part[:max_name_length] if len(name_part) > max_name_length else name_part
                        unique_filename = f"{uuid.uuid4()}-{truncated_name}.{ext_part}"
                else:
                    unique_filename = f"{uuid.uuid4()}-{original_filename[:max_filename_for_path]}"
            else:
                unique_filename = f"{uuid.uuid4()}-{original_filename}"
            
            storage_path = f"audio-video/{unique_filename}"
            
            # Final safety check - ensure storage_path doesn't exceed 200 chars
            if len(storage_path) > 200:
                # Emergency fallback: use UUID only
                file_ext = original_filename.split('.')[-1] if '.' in original_filename else 'mp4'
                unique_filename = f"{uuid.uuid4()}.{file_ext}"
                storage_path = f"audio-video/{unique_filename}"

            # Upload to GCS
            from django.core.files.storage import default_storage
            from django.conf import settings
            
            # Check if GCS is configured
            if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
                return Response(
                    {'error': 'Google Cloud Storage is not configured. Please set GCS_BUCKET_NAME and GCS_PROJECT_ID environment variables.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            try:
                # Save file to GCS storage
                saved_path = default_storage.save(storage_path, uploaded_file)
                
                # Get file URL from GCS
                file_url = default_storage.url(saved_path)
                # Ensure full URL format for GCS
                if not file_url.startswith('http'):
                    file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
                
                logger.info(f"Audio/Video file uploaded successfully: {saved_path}")
                
            except Exception as e:
                logger.error(f"Error uploading audio/video file to storage: {e}")
                return Response(
                    {'error': f'Failed to upload file: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Get optional lesson_material_id
            lesson_material_id = request.data.get('lesson_material_id')
            lesson_material = None
            
            if lesson_material_id:
                try:
                    lesson_material = LessonMaterial.objects.get(
                        id=lesson_material_id,
                        material_type='audio'
                    )
                except LessonMaterial.DoesNotExist:
                    # Will link later when LessonMaterial is created
                    pass

            # Create AudioVideoMaterial instance
            # CRITICAL: Both file_name and original_filename database columns are VARCHAR(200)
            # Ensure both are truncated to exactly 200 characters max
            try:
                # Ensure original_filename is max 200 chars
                safe_original_filename = original_filename[:200] if len(original_filename) > 200 else original_filename
                
                # Ensure saved_path (file_name) is max 200 chars
                safe_file_name = saved_path[:200] if len(saved_path) > 200 else saved_path
                
                audio_video_material = AudioVideoMaterial.objects.create(
                    file_name=safe_file_name,
                    original_filename=safe_original_filename,
                    file_url=file_url,
                    file_size=uploaded_file.size,
                    file_extension=file_extension,
                    mime_type=mime_type,
                    uploaded_by=request.user,
                    lesson_material=lesson_material
                )
                
                logger.info(f"AudioVideoMaterial created: {audio_video_material.id}")
                
            except Exception as e:
                logger.error(f"Error creating AudioVideoMaterial: {e}")
                # Try to delete uploaded file if AudioVideoMaterial creation fails
                try:
                    default_storage.delete(saved_path)
                except:
                    pass
                return Response(
                    {'error': f'Failed to create audio/video material: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Return success response
            return Response({
                'file_url': file_url,
                'file_size': uploaded_file.size,
                'file_size_mb': round(uploaded_file.size / (1024 * 1024), 2),
                'file_extension': file_extension,
                'file_name': saved_path,
                'original_filename': original_filename,
                'mime_type': mime_type,
                'audio_video_material_id': str(audio_video_material.id),
                'message': 'Audio/Video uploaded successfully'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            logger.error(f"Error in audio/video upload: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during file upload: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CourseImageUploadView(APIView):
    """
    API view for uploading course images to Google Cloud Storage.
    Handles image upload, compression, thumbnail generation, and returns both URLs.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Upload a course image to GCS, compress it, generate thumbnail, and return both URLs.
        
        Expected request:
        - image: Image file (JPEG, PNG, WebP)
        
        Returns:
        - image_url: GCS URL for full-size compressed image
        - thumbnail_url: GCS URL for thumbnail
        - file_size: Size in bytes (after compression)
        - file_size_mb: Size in MB
        - file_extension: File extension
        - original_filename: Original filename
        - message: Success message
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can upload course images'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get uploaded image
            uploaded_image = request.FILES.get('image')
            if not uploaded_image:
                return Response(
                    {'error': 'No image provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB in bytes
            if uploaded_image.size > max_size:
                return Response(
                    {'error': f'Image size exceeds maximum allowed size of 10MB. File size: {round(uploaded_image.size / (1024 * 1024), 2)}MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file extension
            original_filename = uploaded_image.name
            file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
            allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
            
            if file_extension not in allowed_extensions:
                return Response(
                    {'error': f'Image extension "{file_extension}" not allowed. Allowed extensions: {", ".join(allowed_extensions)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if GCS is configured
            from django.core.files.storage import default_storage
            from django.conf import settings
            from django.core.files.base import ContentFile
            from PIL import Image
            from io import BytesIO
            import uuid
            
            if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
                return Response(
                    {'error': 'Google Cloud Storage is not configured. Please set GCS_BUCKET_NAME and GCS_PROJECT_ID environment variables.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            try:
                # Process image with Pillow
                img = Image.open(uploaded_image)
                
                # Convert RGBA/LA/P to RGB if needed
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize full image to max 1920x1920 (maintains aspect ratio)
                max_size_full = (1920, 1920)
                img.thumbnail(max_size_full, Image.Resampling.LANCZOS)
                
                # Compress and save full image
                full_output = BytesIO()
                img.save(
                    full_output,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )
                full_output.seek(0)
                
                # Generate thumbnail (400x400)
                img_thumb = img.copy()
                img_thumb.thumbnail((400, 400), Image.Resampling.LANCZOS)
                
                # Compress and save thumbnail
                thumb_output = BytesIO()
                img_thumb.save(
                    thumb_output,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )
                thumb_output.seek(0)
                
                # Generate unique filenames
                unique_id = uuid.uuid4()
                base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else 'image'
                # Sanitize base name
                base_name = ''.join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
                
                full_filename = f"{unique_id}-{base_name}.jpg"
                thumb_filename = f"{unique_id}-{base_name}-thumb.jpg"
                
                full_storage_path = f"course_images/{full_filename}"
                thumb_storage_path = f"course_images/thumbnails/{thumb_filename}"
                
                # Upload full image to GCS
                full_file = ContentFile(full_output.getvalue())
                saved_full_path = default_storage.save(full_storage_path, full_file)
                full_url = default_storage.url(saved_full_path)
                if not full_url.startswith('http'):
                    full_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_full_path}"
                
                # Upload thumbnail to GCS
                thumb_file = ContentFile(thumb_output.getvalue())
                saved_thumb_path = default_storage.save(thumb_storage_path, thumb_file)
                thumb_url = default_storage.url(saved_thumb_path)
                if not thumb_url.startswith('http'):
                    thumb_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_thumb_path}"
                
                # Get compressed file sizes
                full_size = len(full_output.getvalue())
                thumb_size = len(thumb_output.getvalue())
                
                logger.info(f"Course image uploaded successfully: {saved_full_path}, thumbnail: {saved_thumb_path}")
                
                # Return success response
                return Response({
                    'image_url': full_url,
                    'thumbnail_url': thumb_url,
                    'file_size': full_size,
                    'file_size_mb': round(full_size / (1024 * 1024), 2),
                    'file_extension': 'jpg',
                    'original_filename': original_filename,
                    'message': 'Course image uploaded and compressed successfully'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error processing/uploading course image: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return Response(
                    {'error': f'Failed to process/upload image: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            import traceback
            logger.error(f"Error in course image upload: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during image upload: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AIGenerateQuizView(APIView):
    """
    REST API endpoint for generating quizzes using AI from lesson materials.
    
    POST: Generate quiz from selected materials
    - Receives lesson_id, material_ids, system_instruction from frontend
    - Fetches content for each material
    - Handles transcription for video/audio materials
    - Combines all content and generates quiz
    
    Endpoint: POST /api/teacher/lessons/{lesson_id}/ai/generate-quiz/
    
    Request Body:
    {
        "material_ids": ["uuid1", "uuid2", ...],  // IDs of materials to include
        "system_instruction": "You are an expert quiz creator...",  // Optional
        "temperature": 0.7  // Optional
    }
    
    Response:
    {
        "title": "...",
        "description": "...",
        "questions": [...]
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, lesson_id):
        """
        POST: Generate quiz from selected materials using AI.
        
        Does NOT save to database - frontend handles saving.
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can use AI generation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get lesson and check ownership
            try:
                lesson = Lesson.objects.select_related('course__teacher').get(
                    id=lesson_id,
                    course__teacher=request.user
                )
            except Lesson.DoesNotExist:
                return Response(
                    {'error': 'Lesson not found or you do not have permission'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get material IDs from request
            material_ids = request.data.get('material_ids', [])
            if not material_ids or not isinstance(material_ids, list):
                return Response(
                    {'error': 'material_ids is required and must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Fetch all materials
            materials = LessonMaterial.objects.filter(
                id__in=material_ids,
                lessons=lesson
            ).prefetch_related('book_pages')
            
            if materials.count() != len(material_ids):
                return Response(
                    {'error': 'Some materials not found or not associated with this lesson'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Collect content from all materials
            # Support both text content and direct file uploads to Gemini
            text_content_parts = []
            file_parts = []
            transcription_service = VideoTranscriptionService()
            
            for material in materials:
                material_content = None
                document_part = None
                
                logger.info(f"Processing material {material.id}: type={material.material_type}, title={material.title}")
                
                if material.material_type == 'note':
                    # Notes: use content/description
                    material_content = material.description or ''
                    
                elif material.material_type == 'video' or material.material_type == 'audio':
                    # Video/Audio: use transcript if available, otherwise transcribe
                    try:
                        video_material = VideoMaterial.objects.filter(
                            lesson_material=material
                        ).first()
                        
                        if not video_material and material.file_url:
                            # Try to find by video URL
                            video_material = VideoMaterial.objects.filter(
                                video_url=material.file_url
                            ).first()
                        
                        if video_material and video_material.has_transcript and video_material.transcript:
                            # Use existing transcript
                            material_content = video_material.transcript
                            logger.info(f"Using existing transcript for video material {material.id}")
                        elif material.file_url:
                            # Need to transcribe
                            logger.info(f"Transcribing video/audio material {material.id}")
                            result = transcription_service.transcribe_video(material.file_url)
                            if result.get('success') and result.get('transcript'):
                                material_content = result['transcript']
                                logger.info(f"Successfully transcribed material {material.id}")
                            else:
                                logger.warning(f"Failed to transcribe material {material.id}: {result.get('error')}")
                                material_content = f"[Video/Audio URL: {material.file_url} - Transcription unavailable]"
                        else:
                            material_content = f"[Video/Audio material: {material.title} - No URL available]"
                    except Exception as e:
                        logger.error(f"Error processing video/audio material {material.id}: {e}")
                        material_content = f"[Video/Audio material: {material.title} - Error processing]"
                
                elif material.material_type == 'book':
                    # Books: get all page content
                    pages = material.book_pages.all().order_by('page_number')
                    if pages.exists():
                        page_contents = []
                        for page in pages:
                            page_text = f"Page {page.page_number}"
                            if page.title:
                                page_text += f": {page.title}"
                            page_text += f"\n{page.content}"
                            page_contents.append(page_text)
                        material_content = "\n\n".join(page_contents)
                    else:
                        material_content = material.description or ''
                
                elif material.material_type == 'document':
                    # For documents: try direct file upload to Gemini
                    try:
                        document_material = DocumentMaterial.objects.filter(
                            lesson_material=material
                        ).first()
                        
                        # Log what we found
                        if document_material:
                            logger.info(f"Found DocumentMaterial for {material.id}: file_url={document_material.file_url}, mime_type={document_material.mime_type}")
                        else:
                            logger.warning(f"No DocumentMaterial found for document material {material.id}, checking LessonMaterial.file_url")
                        
                        # Try DocumentMaterial first, then fallback to LessonMaterial.file_url
                        file_url = None
                        mime_type = None
                        
                        if document_material and document_material.file_url:
                            file_url = document_material.file_url
                            mime_type = document_material.mime_type or 'application/pdf'
                        elif material.file_url:
                            # Fallback: use file_url directly from LessonMaterial
                            file_url = material.file_url
                            # Try to infer mime_type from file_extension
                            if material.file_extension:
                                mime_type_map = {
                                    'pdf': 'application/pdf',
                                    'doc': 'application/msword',
                                    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                    'txt': 'text/plain',
                                    'rtf': 'application/rtf'
                                }
                                mime_type = mime_type_map.get(material.file_extension.lower(), 'application/pdf')
                            else:
                                mime_type = 'application/pdf'
                            logger.info(f"Using LessonMaterial.file_url as fallback: {file_url}")
                        
                        if file_url:
                            # Create Part object for direct file upload (like video transcription)
                            from vertexai.generative_models import Part
                            try:
                                document_part = Part.from_uri(
                                    uri=file_url,
                                    mime_type=mime_type
                                )
                                logger.info(f"Successfully created file part for document {material.id}: {file_url}")
                            except Exception as e:
                                logger.error(f"Failed to create file part for document {material.id}: {e}", exc_info=True)
                                # Fallback to description if file part creation fails
                                material_content = material.description or ''
                                logger.warning(f"Falling back to description for material {material.id}")
                        else:
                            # No file URL found anywhere
                            logger.warning(f"No file_url found for document material {material.id}, using description")
                            material_content = material.description or ''
                    except Exception as e:
                        logger.error(f"Error processing document material {material.id}: {e}", exc_info=True)
                        material_content = material.description or ''
                
                else:
                    # Other materials: use description
                    material_content = material.description or ''
                
                # Add to appropriate list
                if document_part:
                    file_parts.append(document_part)
                    logger.info(f"Added document file part for: {material.title} (total file_parts: {len(file_parts)})")
                elif material_content and material_content.strip():
                    text_content_parts.append(f"=== {material.title} ({material.material_type}) ===\n{material_content}")
                    logger.info(f"Added text content for: {material.title} (total text parts: {len(text_content_parts)})")
                else:
                    logger.warning(f"No content added for material {material.id} ({material.material_type}): document_part={document_part is not None}, material_content={'empty' if not material_content else 'has content'}")
            
            # Combine text content
            combined_content = "\n\n".join(text_content_parts) if text_content_parts else None
            
            # Log summary before validation
            logger.info(f"Content collection summary: text_parts={len(text_content_parts)}, file_parts={len(file_parts)}, combined_content_length={len(combined_content) if combined_content else 0}")
            
            # Validate that we have at least some content
            if not combined_content and not file_parts:
                logger.error(f"No content found in selected materials. Materials processed: {materials.count()}, text_parts: {len(text_content_parts)}, file_parts: {len(file_parts)}")
                return Response(
                    {'error': 'No content found in selected materials'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get question count parameters first (needed to enhance system instruction)
            total_questions = int(request.data.get('total_questions', 10))
            multiple_choice_count = int(request.data.get('multiple_choice_count', 7))
            true_false_count = int(request.data.get('true_false_count', 3))
            
            # Validate question counts match total
            if multiple_choice_count + true_false_count != total_questions:
                # Auto-adjust to match total
                if multiple_choice_count + true_false_count > total_questions:
                    # Reduce proportionally
                    ratio = total_questions / (multiple_choice_count + true_false_count)
                    multiple_choice_count = int(multiple_choice_count * ratio)
                    true_false_count = total_questions - multiple_choice_count
                else:
                    # Increase to match total
                    true_false_count = total_questions - multiple_choice_count
            
            # Get system instruction and enhance it with question type requirements
            system_instruction = request.data.get('system_instruction', '').strip()
            if not system_instruction:
                system_instruction = """You are an expert quiz creator specializing in educational content.
Generate comprehensive quiz questions that test understanding of the lesson material."""
            
            # Enhance system instruction with question type requirements
            # This makes the AI's role clearer while keeping specific counts in the prompt
            question_type_info = []
            if multiple_choice_count > 0:
                question_type_info.append(f"{multiple_choice_count} multiple choice question{'s' if multiple_choice_count != 1 else ''}")
            if true_false_count > 0:
                question_type_info.append(f"{true_false_count} true/false question{'s' if true_false_count != 1 else ''}")
            
            if question_type_info:
                type_requirement = f"Create {', and '.join(question_type_info)} with clear correct answers and helpful explanations."
                # Append to system instruction if not already present
                if type_requirement.lower() not in system_instruction.lower():
                    system_instruction = f"{system_instruction}\n{type_requirement}"
            
            # Get template attributes from request (with fallbacks)
            temperature = float(request.data.get('temperature', 0.7))
            model_name = request.data.get('model_name', '').strip() or None
            max_tokens = request.data.get('max_tokens')
            if max_tokens is not None:
                try:
                    max_tokens = int(max_tokens)
                except (ValueError, TypeError):
                    max_tokens = None
            
            # Initialize service and generate quiz
            service = GeminiQuizService()
            result = service.generate(
                system_instruction=system_instruction,
                lesson_title=lesson.title,
                lesson_description=lesson.description or '',
                content=combined_content if combined_content else None,
                file_parts=file_parts if file_parts else None,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
                total_questions=total_questions,
                multiple_choice_count=multiple_choice_count,
                true_false_count=true_false_count
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Validation error in AI quiz generation: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            logger.error(f"Error in AI quiz generation: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during AI generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AIGenerateAssignmentView(APIView):
    """
    REST API endpoint for generating assignments using AI from lesson materials.
    
    POST: Generate assignment from selected materials
    - Receives lesson_id, material_ids, system_instruction from frontend
    - Fetches content for each material
    - Handles transcription for video/audio materials
    - Combines all content and generates assignment
    
    Endpoint: POST /api/teacher/lessons/{lesson_id}/ai/generate-assignment/
    
    Request Body:
    {
        "material_ids": ["uuid1", "uuid2", ...],  // IDs of materials to include
        "system_instruction": "You are an expert assignment creator...",  // Optional
        "temperature": 0.7  // Optional
    }
    
    Response:
    {
        "title": "...",
        "description": "...",
        "questions": [...]
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, lesson_id):
        """
        POST: Generate assignment from selected materials using AI.
        
        Does NOT save to database - frontend handles saving.
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can use AI generation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get lesson and check ownership
            try:
                lesson = Lesson.objects.select_related('course__teacher').get(
                    id=lesson_id,
                    course__teacher=request.user
                )
            except Lesson.DoesNotExist:
                return Response(
                    {'error': 'Lesson not found or you do not have permission'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get material IDs from request
            material_ids = request.data.get('material_ids', [])
            if not material_ids or not isinstance(material_ids, list):
                return Response(
                    {'error': 'material_ids is required and must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Fetch all materials
            materials = LessonMaterial.objects.filter(
                id__in=material_ids,
                lessons=lesson
            ).prefetch_related('book_pages')
            
            if materials.count() != len(material_ids):
                return Response(
                    {'error': 'Some materials not found or not associated with this lesson'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Collect content from all materials
            # Support both text content and direct file uploads to Gemini
            text_content_parts = []
            file_parts = []
            transcription_service = VideoTranscriptionService()
            
            for material in materials:
                material_content = None
                document_part = None
                
                logger.info(f"Processing material {material.id}: type={material.material_type}, title={material.title}")
                
                if material.material_type == 'note':
                    material_content = material.description or ''
                    
                elif material.material_type == 'video' or material.material_type == 'audio':
                    try:
                        video_material = VideoMaterial.objects.filter(
                            lesson_material=material
                        ).first()
                        
                        if not video_material and material.file_url:
                            video_material = VideoMaterial.objects.filter(
                                video_url=material.file_url
                            ).first()
                        
                        if video_material and video_material.has_transcript and video_material.transcript:
                            material_content = video_material.transcript
                            logger.info(f"Using existing transcript for video material {material.id}")
                        elif material.file_url:
                            logger.info(f"Transcribing video/audio material {material.id}")
                            result = transcription_service.transcribe_video(material.file_url)
                            if result.get('success') and result.get('transcript'):
                                material_content = result['transcript']
                                logger.info(f"Successfully transcribed material {material.id}")
                            else:
                                logger.warning(f"Failed to transcribe material {material.id}: {result.get('error')}")
                                material_content = f"[Video/Audio URL: {material.file_url} - Transcription unavailable]"
                        else:
                            material_content = f"[Video/Audio material: {material.title} - No URL available]"
                    except Exception as e:
                        logger.error(f"Error processing video/audio material {material.id}: {e}")
                        material_content = f"[Video/Audio material: {material.title} - Error processing]"
                
                elif material.material_type == 'book':
                    pages = material.book_pages.all().order_by('page_number')
                    if pages.exists():
                        page_contents = []
                        for page in pages:
                            page_text = f"Page {page.page_number}"
                            if page.title:
                                page_text += f": {page.title}"
                            page_text += f"\n{page.content}"
                            page_contents.append(page_text)
                        material_content = "\n\n".join(page_contents)
                    else:
                        material_content = material.description or ''
                
                elif material.material_type == 'document':
                    # For documents: try direct file upload to Gemini
                    try:
                        document_material = DocumentMaterial.objects.filter(
                            lesson_material=material
                        ).first()
                        
                        # Log what we found
                        if document_material:
                            logger.info(f"Found DocumentMaterial for {material.id}: file_url={document_material.file_url}, mime_type={document_material.mime_type}")
                        else:
                            logger.warning(f"No DocumentMaterial found for document material {material.id}, checking LessonMaterial.file_url")
                        
                        # Try DocumentMaterial first, then fallback to LessonMaterial.file_url
                        file_url = None
                        mime_type = None
                        
                        if document_material and document_material.file_url:
                            file_url = document_material.file_url
                            mime_type = document_material.mime_type or 'application/pdf'
                        elif material.file_url:
                            # Fallback: use file_url directly from LessonMaterial
                            file_url = material.file_url
                            # Try to infer mime_type from file_extension
                            if material.file_extension:
                                mime_type_map = {
                                    'pdf': 'application/pdf',
                                    'doc': 'application/msword',
                                    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                    'txt': 'text/plain',
                                    'rtf': 'application/rtf'
                                }
                                mime_type = mime_type_map.get(material.file_extension.lower(), 'application/pdf')
                            else:
                                mime_type = 'application/pdf'
                            logger.info(f"Using LessonMaterial.file_url as fallback: {file_url}")
                        
                        if file_url:
                            # Create Part object for direct file upload (like video transcription)
                            from vertexai.generative_models import Part
                            try:
                                document_part = Part.from_uri(
                                    uri=file_url,
                                    mime_type=mime_type
                                )
                                logger.info(f"Successfully created file part for document {material.id}: {file_url}")
                            except Exception as e:
                                logger.error(f"Failed to create file part for document {material.id}: {e}", exc_info=True)
                                # Fallback to description if file part creation fails
                                material_content = material.description or ''
                                logger.warning(f"Falling back to description for material {material.id}")
                        else:
                            # No file URL found anywhere
                            logger.warning(f"No file_url found for document material {material.id}, using description")
                            material_content = material.description or ''
                    except Exception as e:
                        logger.error(f"Error processing document material {material.id}: {e}", exc_info=True)
                        material_content = material.description or ''
                
                else:
                    material_content = material.description or ''
                
                # Add to appropriate list
                if document_part:
                    file_parts.append(document_part)
                    logger.info(f"Added document file part for: {material.title} (total file_parts: {len(file_parts)})")
                elif material_content and material_content.strip():
                    text_content_parts.append(f"=== {material.title} ({material.material_type}) ===\n{material_content}")
                    logger.info(f"Added text content for: {material.title} (total text parts: {len(text_content_parts)})")
                else:
                    logger.warning(f"No content added for material {material.id} ({material.material_type}): document_part={document_part is not None}, material_content={'empty' if not material_content else 'has content'}")
            
            # Combine text content
            combined_content = "\n\n".join(text_content_parts) if text_content_parts else None
            
            # Log summary before validation
            logger.info(f"Content collection summary: text_parts={len(text_content_parts)}, file_parts={len(file_parts)}, combined_content_length={len(combined_content) if combined_content else 0}")
            
            # Validate that we have at least some content
            if not combined_content and not file_parts:
                logger.error(f"No content found in selected materials. Materials processed: {materials.count()}, text_parts: {len(text_content_parts)}, file_parts: {len(file_parts)}")
                return Response(
                    {'error': 'No content found in selected materials'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get question count parameters first (needed to enhance system instruction)
            total_questions = int(request.data.get('total_questions', 5))
            essay_count = int(request.data.get('essay_count', 2))
            fill_blank_count = int(request.data.get('fill_blank_count', 3))
            
            # Validate question counts match total
            if essay_count + fill_blank_count != total_questions:
                # Auto-adjust to match total
                if essay_count + fill_blank_count > total_questions:
                    # Reduce proportionally
                    ratio = total_questions / (essay_count + fill_blank_count)
                    essay_count = int(essay_count * ratio)
                    fill_blank_count = total_questions - essay_count
                else:
                    # Increase to match total
                    fill_blank_count = total_questions - essay_count
            
            # Get system instruction and enhance it with question type requirements
            system_instruction = request.data.get('system_instruction', '').strip()
            if not system_instruction:
                system_instruction = """You are an expert assignment creator specializing in educational content.
Generate comprehensive assignment questions that require students to demonstrate understanding and application of lesson material."""
            
            # Enhance system instruction with question type requirements
            # This makes the AI's role clearer while keeping specific counts in the prompt
            question_type_info = []
            if essay_count > 0:
                question_type_info.append(f"{essay_count} essay question{'s' if essay_count != 1 else ''}")
            if fill_blank_count > 0:
                question_type_info.append(f"{fill_blank_count} fill-in-the-blank question{'s' if fill_blank_count != 1 else ''}")
            
            # Check for other question types that might be in the request
            short_answer_count = int(request.data.get('short_answer_count', 0))
            if short_answer_count > 0:
                question_type_info.append(f"{short_answer_count} short answer question{'s' if short_answer_count != 1 else ''}")
            
            if question_type_info:
                type_requirement = f"Create {', and '.join(question_type_info)} with clear requirements, helpful explanations, and grading rubrics where applicable."
                # Append to system instruction if not already present
                if type_requirement.lower() not in system_instruction.lower():
                    system_instruction = f"{system_instruction}\n{type_requirement}"
            
            # Get template attributes from request (with fallbacks)
            temperature = float(request.data.get('temperature', 0.7))
            model_name = request.data.get('model_name', '').strip() or None
            max_tokens = request.data.get('max_tokens')
            if max_tokens is not None:
                try:
                    max_tokens = int(max_tokens)
                except (ValueError, TypeError):
                    max_tokens = None
            
            # Initialize service and generate assignment
            service = GeminiAssignmentService()
            result = service.generate(
                system_instruction=system_instruction,
                lesson_title=lesson.title,
                lesson_description=lesson.description or '',
                content=combined_content if combined_content else None,
                file_parts=file_parts if file_parts else None,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
                total_questions=total_questions,
                essay_count=essay_count,
                fill_blank_count=fill_blank_count
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Validation error in AI assignment generation: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            logger.error(f"Error in AI assignment generation: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error during AI generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===== MESSAGING VIEWS =====

class MessagePagination(PageNumberPagination):
    """Pagination for message lists"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class StudentConversationsListView(APIView):
    """
    List or create conversations for a specific student.
    Teachers can only access conversations for students in their classes.
    """
    permission_classes = [IsAuthenticated]
    
    def get_teacher_student_enrollment(self, teacher, student_profile):
        """Verify teacher teaches this student"""
        return EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course__teacher=teacher,
            status='active'
        ).exists()
    
    def get(self, request, student_id):
        """List conversations for a student"""
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student profile
            try:
                student_profile = StudentProfile.objects.get(user_id=student_id)
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify teacher teaches this student
            if not self.get_teacher_student_enrollment(teacher, student_profile):
                return Response(
                    {'error': 'You do not teach this student'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get recipient_type filter from query params
            recipient_type = request.query_params.get('recipient_type', None)
            
            # Query conversations
            conversations = Conversation.objects.filter(
                student_profile=student_profile,
                teacher=teacher
            ).select_related('student_profile', 'student_profile__user', 'teacher')
            
            if recipient_type:
                conversations = conversations.filter(recipient_type=recipient_type)
            
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
            logger.error(f"Error listing conversations: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': 'Failed to fetch conversations', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, student_id):
        """Create or get existing conversation"""
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student profile
            try:
                student_profile = StudentProfile.objects.get(user_id=student_id)
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify teacher teaches this student
            if not self.get_teacher_student_enrollment(teacher, student_profile):
                return Response(
                    {'error': 'You do not teach this student'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Validate request data
            serializer = CreateConversationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            recipient_type = serializer.validated_data.get('recipient_type', 'parent')
            subject = serializer.validated_data.get('subject', '')
            course_id = serializer.validated_data.get('course_id')
            
            # Validate course if provided
            course = None
            if course_id:
                try:
                    course = Course.objects.get(id=course_id, teacher=teacher)
                    # Verify student is enrolled in this course
                    if not EnrolledCourse.objects.filter(
                        student_profile=student_profile,
                        course=course
                    ).exists():
                        return Response(
                            {'error': 'Student is not enrolled in this course'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except Course.DoesNotExist:
                    return Response(
                        {'error': 'Course not found or you do not teach this course'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Get or create conversation (now course-specific)
            # Use filter().first() instead of get() to handle cases where multiple conversations exist
            # (e.g., before migration or duplicate data)
            try:
                conversation = Conversation.objects.filter(
                    student_profile=student_profile,
                    teacher=teacher,
                    recipient_type=recipient_type,
                    course=course
                ).first()
            except Exception as db_error:
                # Fallback: if course field doesn't exist yet (migration not run), filter without course
                # This handles the transition period gracefully
                if 'course' in str(db_error).lower() or 'no such column' in str(db_error).lower():
                    conversation = Conversation.objects.filter(
                        student_profile=student_profile,
                        teacher=teacher,
                        recipient_type=recipient_type
                    ).first()
                else:
                    raise
            
            if conversation:
                created = False
                # Update subject if provided and different
                if subject and conversation.subject != subject:
                    conversation.subject = subject
                    conversation.save(update_fields=['subject'])
                # If course field exists and conversation doesn't have course set, update it
                if course and hasattr(conversation, 'course') and conversation.course != course:
                    conversation.course = course
                    conversation.save(update_fields=['course'])
            else:
                created = True
                try:
                    conversation = Conversation.objects.create(
                        student_profile=student_profile,
                        teacher=teacher,
                        recipient_type=recipient_type,
                        course=course,
                        subject=subject
                    )
                except Exception as create_error:
                    # If course field doesn't exist, create without it
                    if 'course' in str(create_error).lower() or 'no such column' in str(create_error).lower():
                        conversation = Conversation.objects.create(
                            student_profile=student_profile,
                            teacher=teacher,
                            recipient_type=recipient_type,
                            subject=subject
                        )
                    else:
                        raise
            
            # Serialize response
            response_serializer = ConversationSerializer(conversation)
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
            
        except Exception as e:
            import traceback
            logger.error(f"Error creating conversation: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': 'Failed to create conversation', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConversationMessagesView(APIView):
    """
    Get messages in a conversation or send a new message.
    Teachers can only access conversations for students they teach.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = MessagePagination
    
    def verify_teacher_access(self, teacher, conversation):
        """Verify teacher has access to this conversation"""
        return conversation.teacher == teacher
    
    def get(self, request, conversation_id):
        """Get messages in conversation"""
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
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
            if not self.verify_teacher_access(teacher, conversation):
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
            logger.error(f"Error fetching messages: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': 'Failed to fetch messages', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, conversation_id):
        """Send a new message"""
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
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
            if not self.verify_teacher_access(teacher, conversation):
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
                sender=teacher,
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
            logger.error(f"Error sending message: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': 'Failed to send message', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MarkMessageReadView(APIView):
    """Mark a message as read"""
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, message_id):
        """Mark message as read"""
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get message
            try:
                message = Message.objects.select_related('conversation', 'conversation__teacher').get(id=message_id)
            except Message.DoesNotExist:
                return Response(
                    {'error': 'Message not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify teacher has access to conversation
            if message.conversation.teacher != teacher:
                return Response(
                    {'error': 'You do not have access to this message'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Mark as read
            message.mark_as_read(teacher)
            
            # Serialize response
            serializer = MessageSerializer(message, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            logger.error(f"Error marking message as read: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': 'Failed to mark message as read', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UnreadCountView(APIView):
    """Get unread message count for teacher"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get unread count, optionally filtered by recipient_type"""
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            recipient_type = request.query_params.get('recipient_type', None)
            
            # Get all conversations for this teacher
            conversations = Conversation.objects.filter(teacher=teacher)
            if recipient_type:
                conversations = conversations.filter(recipient_type=recipient_type)
            
            # Count unread messages (messages not sent by teacher and not read)
            total_unread = Message.objects.filter(
                conversation__in=conversations
            ).exclude(sender=teacher).filter(read_at__isnull=True).count()
            
            # Count by recipient_type
            by_recipient_type = {}
            for rt in ['parent', 'student']:
                convs = conversations.filter(recipient_type=rt)
                count = Message.objects.filter(
                    conversation__in=convs
                ).exclude(sender=teacher).filter(read_at__isnull=True).count()
                by_recipient_type[rt] = count
            
            return Response({
                'total_unread': total_unread,
                'by_recipient_type': by_recipient_type
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            logger.error(f"Error getting unread count: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': 'Failed to get unread count', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StudentUnreadCountView(APIView):
    """Get unread message count for a specific student conversation (lightweight endpoint)"""
    permission_classes = [IsAuthenticated]
    
    def get_teacher_student_enrollment(self, teacher, student_profile):
        """Verify teacher teaches this student"""
        return EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course__teacher=teacher,
            status='active'
        ).exists()
    
    def get(self, request, student_id):
        """Get unread count for a specific student, optionally filtered by recipient_type"""
        try:
            teacher = request.user
            if not teacher.is_teacher:
                return Response(
                    {'error': 'Only teachers can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student profile
            try:
                student_profile = StudentProfile.objects.get(user_id=student_id)
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify teacher teaches this student
            if not self.get_teacher_student_enrollment(teacher, student_profile):
                return Response(
                    {'error': 'You do not teach this student'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            recipient_type = request.query_params.get('recipient_type', None)
            
            # Get conversations for this student
            conversations = Conversation.objects.filter(
                student_profile=student_profile,
                teacher=teacher
            )
            
            if recipient_type:
                conversations = conversations.filter(recipient_type=recipient_type)
            
            # Count unread messages (messages not sent by teacher and not read)
            unread_count = Message.objects.filter(
                conversation__in=conversations
            ).exclude(sender=teacher).filter(read_at__isnull=True).count()
            
            # Return counts by recipient_type
            by_recipient_type = {}
            for rt in ['parent', 'student']:
                convs = conversations.filter(recipient_type=rt)
                count = Message.objects.filter(
                    conversation__in=convs
                ).exclude(sender=teacher).filter(read_at__isnull=True).count()
                by_recipient_type[rt] = count
            
            return Response({
                'unread_count': unread_count,
                'by_recipient_type': by_recipient_type
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            logger.error(f"Error getting student unread count: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': 'Failed to get unread count', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )