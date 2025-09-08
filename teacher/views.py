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