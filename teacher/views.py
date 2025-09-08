from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from users.models import User, TeacherProfile
from .serializers import TeacherProfileSerializer, TeacherProfileUpdateSerializer
from courses.models import Course, ClassEvent, CourseReview, LessonProgress
from student.models import EnrolledCourse
from django.db.models import Count, Avg, Sum
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
            'lesson'
        ).order_by('start_time')
        
        return [
            {
                'id': str(event.id),
                'title': event.title,
                'description': event.description,
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
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
        
        now = datetime.now()
        future_date = now + timedelta(days=30)
        
        events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher,
            start_time__gte=now,
            start_time__lte=future_date
        ).select_related(
            'class_instance__course',
            'lesson'
        ).order_by('start_time')
        
        return [
            {
                'id': str(event.id),
                'title': event.title,
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
                'event_type': event.event_type,
                'course_title': event.class_instance.course.title,
                'class_name': event.class_instance.name,
                'meeting_link': event.meeting_link,
                'meeting_platform': event.meeting_platform,
            }
            for event in events
        ]
    
    def get_events_by_type(self, teacher):
        """
        Get events grouped by type
        """
        events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).select_related('class_instance__course')
        
        events_by_type = {
            'lesson': [],
            'meeting': [],
            'break': []
        }
        
        for event in events:
            event_data = {
                'id': str(event.id),
                'title': event.title,
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
                'course_title': event.class_instance.course.title,
                'class_name': event.class_instance.name,
            }
            events_by_type[event.event_type].append(event_data)
        
        return events_by_type
    
    def get_events_by_course(self, teacher):
        """
        Get events grouped by course
        """
        events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).select_related('class_instance__course')
        
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
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
                'event_type': event.event_type,
                'lesson_type': event.lesson_type,
                'class_name': event.class_instance.name,
            }
            events_by_course[course_id]['events'].append(event_data)
        
        return list(events_by_course.values())
    
    def get_schedule_summary(self, teacher):
        """
        Get schedule summary statistics
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Total events
        total_events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher
        ).count()
        
        # This week's events
        this_week_events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher,
            start_time__date__gte=week_start,
            start_time__date__lte=week_end
        ).count()
        
        # Today's events
        today_events = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher,
            start_time__date=today
        ).count()
        
        # Upcoming live classes
        upcoming_live_classes = ClassEvent.objects.filter(
            class_instance__course__teacher=teacher,
            event_type='lesson',
            lesson_type='live',
            start_time__gte=now
        ).count()
        
        return {
            'total_events': total_events,
            'this_week_events': this_week_events,
            'today_events': today_events,
            'upcoming_live_classes': upcoming_live_classes,
        }