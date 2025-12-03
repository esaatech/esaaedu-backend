from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Q, Avg
from django.db import models
from .models import ContactMethod, SupportTeamMember, FAQ, SupportHours, ContactSubmission, AssessmentSubmission
from .serializers import (
    ContactMethodSerializer, SupportTeamMemberSerializer, FAQSerializer,
    SupportHoursSerializer, ContactSubmissionSerializer, ContactSubmissionCreateSerializer,
    ContactOverviewSerializer, AssessmentSubmissionSerializer, AssessmentSubmissionCreateSerializer
)
from courses.models import CourseReview, Course


class ContactView(APIView):
    """
    Contact Management CBV - Handles all contact-related functionality
    Based on the images, this represents different contact methods and support features
    
    GET: Retrieve contact overview (methods, team, FAQs, hours)
    POST: Submit contact form
    """
    permission_classes = [permissions.AllowAny]  # Public endpoint
    
    def get(self, request):
        """
        GET: Retrieve contact overview data
        Returns all contact methods, support team, FAQs, and support hours
        """
        try:
            # Get active contact methods
            contact_methods = ContactMethod.objects.filter(is_active=True).order_by('order')
            
            # Get active support team members
            support_team = SupportTeamMember.objects.filter(is_active=True).order_by('order')
            
            # Get active FAQs
            faqs = FAQ.objects.filter(is_active=True).order_by('order')
            
            # Get active support hours
            support_hours = SupportHours.objects.filter(is_active=True).order_by('order')
            
            # Serialize the data
            overview_data = {
                'contact_methods': ContactMethodSerializer(contact_methods, many=True).data,
                'support_team': SupportTeamMemberSerializer(support_team, many=True).data,
                'faqs': FAQSerializer(faqs, many=True).data,
                'support_hours': SupportHoursSerializer(support_hours, many=True).data,
            }
            
            return Response(overview_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve contact information', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """
        POST: Submit contact form
        Validates and saves contact form submission
        """
        try:
            serializer = ContactSubmissionCreateSerializer(data=request.data)
            
            if serializer.is_valid():
                # Save the contact submission
                contact_submission = serializer.save()
                
                # Send Slack notification
                try:
                    from slack_notifications import send_contact_notification
                    send_contact_notification(contact_submission)
                except Exception as e:
                    print(f"Failed to send Slack notification: {str(e)}")
                    # Don't fail the request if Slack notification fails
                
                # Return success response with submission details
                response_serializer = ContactSubmissionSerializer(contact_submission)
                
                return Response(
                    {
                        'message': 'Thank you for your message! We will get back to you soon.',
                        'submission': response_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to submit contact form', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ContactMethodView(APIView):
    """
    Contact Methods CBV - Manage individual contact methods
    GET: List all contact methods
    POST: Create new contact method (admin only)
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """GET: List all active contact methods"""
        try:
            contact_methods = ContactMethod.objects.filter(is_active=True).order_by('order')
            serializer = ContactMethodSerializer(contact_methods, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve contact methods', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SupportTeamView(APIView):
    """
    Support Team CBV - Manage support team members
    GET: List all support team members
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """GET: List all active support team members"""
        try:
            support_team = SupportTeamMember.objects.filter(is_active=True).order_by('order')
            serializer = SupportTeamMemberSerializer(support_team, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve support team', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FAQView(APIView):
    """
    FAQ CBV - Manage frequently asked questions
    GET: List all FAQs
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """GET: List all active FAQs"""
        try:
            faqs = FAQ.objects.filter(is_active=True).order_by('order')
            serializer = FAQSerializer(faqs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve FAQs', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SupportHoursView(APIView):
    """
    Support Hours CBV - Manage support hours
    GET: List all support hours
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """GET: List all active support hours"""
        try:
            support_hours = SupportHours.objects.filter(is_active=True).order_by('order')
            serializer = SupportHoursSerializer(support_hours, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve support hours', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ContactSubmissionView(APIView):
    """
    Contact Submissions CBV - Manage contact form submissions (admin only)
    GET: List all contact submissions
    PUT: Update submission status
    DELETE: Delete submission
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """GET: List all contact submissions (admin only)"""
        try:
            if not request.user.is_staff:
                return Response(
                    {'error': 'Only admin users can view contact submissions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get query parameters for filtering
            status_filter = request.query_params.get('status')
            search = request.query_params.get('search')
            
            submissions = ContactSubmission.objects.all()
            
            # Apply filters
            if status_filter:
                submissions = submissions.filter(status=status_filter)
            
            if search:
                submissions = submissions.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(email__icontains=search) |
                    Q(subject__icontains=search)
                )
            
            submissions = submissions.order_by('-created_at')
            serializer = ContactSubmissionSerializer(submissions, many=True)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve contact submissions', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, submission_id):
        """PUT: Update contact submission status (admin only)"""
        try:
            if not request.user.is_staff:
                return Response(
                    {'error': 'Only admin users can update submissions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                submission = ContactSubmission.objects.get(id=submission_id)
            except ContactSubmission.DoesNotExist:
                return Response(
                    {'error': 'Contact submission not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update submission
            submission.status = request.data.get('status', submission.status)
            submission.response_notes = request.data.get('response_notes', submission.response_notes)
            submission.responded_by = request.user
            submission.save()
            
            serializer = ContactSubmissionSerializer(submission)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to update submission', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, submission_id):
        """DELETE: Delete contact submission (admin only)"""
        try:
            if not request.user.is_staff:
                return Response(
                    {'error': 'Only admin users can delete submissions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                submission = ContactSubmission.objects.get(id=submission_id)
                submission.delete()
                return Response(
                    {'message': 'Contact submission deleted successfully'},
                    status=status.HTTP_200_OK
                )
            except ContactSubmission.DoesNotExist:
                return Response(
                    {'error': 'Contact submission not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
        except Exception as e:
            return Response(
                {'error': 'Failed to delete submission', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LandingPageView(APIView):
    """
    Landing Page CBV - Handles all landing page data
    GET: Retrieve comprehensive landing page data including testimonials, featured courses, etc.
    """
    permission_classes = [permissions.AllowAny]  # Public endpoint
    
    def get(self, request):
        """
        GET: Retrieve complete landing page data
        Returns testimonials, featured courses, and other landing page sections
        """
        try:
            # Build comprehensive landing page data using separate methods
            landing_data = {
                'testimonials': self._get_testimonials_data(),
                'featured_courses': self._get_featured_courses_data(),
                'stats': self._get_landing_stats_data(),
                'hero_section': self._get_hero_section_data(),
            }
            
            return Response(landing_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving landing page data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_testimonials_data(self):
        """
        Get testimonials data for "What People Are Saying" section
        Returns featured reviews with parent information and course tags
        """
        # Get featured reviews, ordered by display preference
        reviews = CourseReview.objects.filter(
            is_featured=True,
            is_verified=True
        ).select_related('course').order_by('-created_at')[:6]  # Limit to 6 for homepage
        
        testimonials = []
        for review in reviews:
            # Get parent name from review (we'll enhance the model)
            parent_name = getattr(review, 'parent_name', 'Parent')
            child_name = review.student_name
            child_age = review.student_age
            
            # Format parent display name
            if child_age:
                parent_display = f"{parent_name} of {child_name} ({child_age})"
            else:
                parent_display = f"{parent_name} of {child_name}"
            
            # Get course category for the tag
            course_category = review.course.category
            
            testimonial = {
                'id': str(review.id),
                'rating': review.rating,
                'quote': review.review_text,
                'reviewer_name': parent_display,
                'course_tag': course_category,
                'course_title': review.course.title,
                'avatar_initials': self._get_avatar_initials(parent_name),
                'created_at': review.created_at.isoformat(),
            }
            testimonials.append(testimonial)
        
        return testimonials
    
    def _get_featured_courses_data(self):
        """
        Get featured courses data for landing page
        """
        featured_courses = Course.objects.filter(
            featured=True,
            status='published'
        ).order_by('-created_at')[:6]
        
        courses = []
        for course in featured_courses:
            course_data = {
                'id': str(course.id),
                'title': course.title,
                'description': course.description,
                'category': course.category,
                'level': course.level,
                'age_range': course.age_range,
                'price': float(course.price),
                'is_free': course.is_free,
                'duration_weeks': course.duration_weeks,
                'enrolled_students_count': course.enrolled_students_count,
                'rating': self._get_course_average_rating(course),
                'image_url': course.image_url,
                'color': course.color,
                'icon': course.icon,
            }
            courses.append(course_data)
        
        return courses
    
    def _get_landing_stats_data(self):
        """
        Get landing page statistics
        """
        total_students = CourseReview.objects.values('student_name').distinct().count()
        total_courses = Course.objects.filter(status='published').count()
        total_reviews = CourseReview.objects.filter(is_verified=True).count()
        average_rating = CourseReview.objects.filter(is_verified=True).aggregate(
            avg_rating=Avg('rating')
        )['avg_rating'] or 0
        
        return {
            'total_students': total_students,
            'total_courses': total_courses,
            'total_reviews': total_reviews,
            'average_rating': round(float(average_rating), 1),
            'satisfaction_rate': 98,  # Could be calculated from ratings
        }
    
    def _get_hero_section_data(self):
        """
        Get hero section data
        """
        return {
            'title': "Empowering Young Minds Through Technology",
            'subtitle': "Interactive coding courses designed for kids and teens",
            'cta_text': "Start Learning Today",
            'background_image': "/static/images/hero-bg.jpg",
        }
    
    def _get_avatar_initials(self, name):
        """
        Generate avatar initials from name
        """
        if not name:
            return "P"
        
        words = name.split()
        if len(words) >= 2:
            return f"{words[0][0]}{words[1][0]}".upper()
        else:
            return f"{words[0][0]}".upper()
    
    def _get_course_average_rating(self, course):
        """
        Get average rating for a course
        """
        from django.db.models import Avg
        avg_rating = CourseReview.objects.filter(
            course=course,
            is_verified=True
        ).aggregate(avg_rating=Avg('rating'))['avg_rating']
        
        return round(float(avg_rating), 1) if avg_rating else 0.0


class AssessmentSubmissionView(APIView):
    """
    Assessment Submission CBV - Handles STEM assessment form submissions
    POST: Submit assessment form (public endpoint)
    """
    permission_classes = [permissions.AllowAny]  # Public endpoint
    
    def post(self, request):
        """
        POST: Submit assessment form
        Validates and saves assessment form submission
        """
        try:
            serializer = AssessmentSubmissionCreateSerializer(data=request.data)
            
            if serializer.is_valid():
                # Save the assessment submission
                assessment_submission = serializer.save()
                
                # Send Slack notification (optional)
                try:
                    from slack_notifications import send_assessment_notification
                    send_assessment_notification(assessment_submission)
                except Exception as e:
                    print(f"Failed to send Slack notification: {str(e)}")
                    # Don't fail the request if Slack notification fails
                
                # Return success response
                response_serializer = AssessmentSubmissionSerializer(assessment_submission)
                
                return Response(
                    {
                        'success': True,
                        'message': 'Thank you for your submission! Our team will contact you shortly.',
                        'submission_id': str(assessment_submission.id)
                    },
                    status=status.HTTP_201_CREATED
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Assessment submission error: {error_details}")
            return Response(
                {
                    'error': 'Failed to submit assessment form',
                    'details': str(e),
                    'traceback': error_details if settings.DEBUG else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssessmentSubmissionListView(APIView):
    """
    Assessment Submissions List CBV - View all submissions (admin only)
    GET: List all assessment submissions
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """GET: List all assessment submissions (admin only)"""
        try:
            if not request.user.is_staff:
                return Response(
                    {'error': 'Only admin users can view assessment submissions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get query parameters for filtering
            status_filter = request.query_params.get('status')
            search = request.query_params.get('search')
            
            submissions = AssessmentSubmission.objects.all()
            
            # Apply filters
            if status_filter:
                submissions = submissions.filter(status=status_filter)
            
            if search:
                submissions = submissions.filter(
                    Q(parent_name__icontains=search) |
                    Q(student_name__icontains=search) |
                    Q(email__icontains=search)
                )
            
            submissions = submissions.order_by('-created_at')
            serializer = AssessmentSubmissionSerializer(submissions, many=True)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve assessment submissions', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )