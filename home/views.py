from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Q
from .models import ContactMethod, SupportTeamMember, FAQ, SupportHours, ContactSubmission
from .serializers import (
    ContactMethodSerializer, SupportTeamMemberSerializer, FAQSerializer,
    SupportHoursSerializer, ContactSubmissionSerializer, ContactSubmissionCreateSerializer,
    ContactOverviewSerializer
)


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