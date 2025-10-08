from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from users.models import User, TeacherProfile
from .serializers import (
    TeacherProfileSerializer, TeacherProfileUpdateSerializer,
    ProjectSerializer, ProjectCreateUpdateSerializer,
    ProjectSubmissionSerializer, ProjectSubmissionGradingSerializer,
    ProjectSubmissionFeedbackSerializer,
    AssignmentListSerializer, AssignmentDetailSerializer, AssignmentCreateUpdateSerializer,
    AssignmentQuestionSerializer, AssignmentSubmissionSerializer, AssignmentGradingSerializer,
    AssignmentFeedbackSerializer
)
from courses.models import Course, ClassEvent, CourseReview, Project, ProjectSubmission, Assignment, AssignmentQuestion, AssignmentSubmission
from student.models import EnrolledCourse
from datetime import datetime, timedelta


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
            'project_platform'
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
            'project_platform'
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
            'project_platform'
        )
        
        events_by_type = {
            'lesson': [],
            'meeting': [],
            'break': [],
            'project': []
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
                'due_date': event.due_date.isoformat() if event.due_date else None,
                'submission_type': event.submission_type,
            }
            events_by_type[event.event_type].append(event_data)
        
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
            'project_platform'
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
            
            # Order by creation date (newest first)
            projects = projects.order_by('-created_at')
            
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
                    assignment = Assignment.objects.select_related(
                        'lesson', 'lesson__course'
                    ).prefetch_related(
                        'questions', 'submissions', 'submissions__student'
                    ).get(
                        id=assignment_id,
                        lesson__course__teacher=request.user
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
                lesson__course__teacher=request.user
            ).select_related('lesson', 'lesson__course').prefetch_related('questions', 'submissions')
            
            # Apply filters
            course_id = request.query_params.get('course_id')
            if course_id:
                assignments = assignments.filter(lesson__course_id=course_id)
            
            lesson_id = request.query_params.get('lesson_id')
            if lesson_id:
                assignments = assignments.filter(lesson_id=lesson_id)
            
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
            assignment_data = {
                'id': str(assignment.id),
                'title': assignment.title,
                'lesson': assignment.lesson.title,
                'course': assignment.lesson.course.title
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
                    assignment = Assignment.objects.get(
                        id=assignment_id, 
                        lesson__course__teacher=request.user
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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
                    enrollment = EnrolledCourse.objects.get(
                        student_profile__user=submission.student,
                        course=assignment.lesson.course
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
                assignment = Assignment.objects.get(
                    id=assignment_id, 
                    lesson__course__teacher=request.user
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