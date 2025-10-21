from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import UserDashboardSettings
from .serializers import UserDashboardSettingsSerializer, DashboardConfigSerializer


class UserDashboardSettingsView(APIView):
    """
    API View for managing user dashboard settings
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        GET: Retrieve current user's dashboard settings
        """
        try:
            settings = UserDashboardSettings.get_or_create_settings(request.user)
            serializer = UserDashboardSettingsSerializer(settings)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve dashboard settings', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        """
        PUT: Update current user's dashboard settings
        """
        try:
            settings = UserDashboardSettings.get_or_create_settings(request.user)
            serializer = UserDashboardSettingsSerializer(settings, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': 'Failed to update dashboard settings', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_dashboard_config(request):
    """
    GET: Get simplified dashboard configuration for current user
    This endpoint is optimized for dashboard views
    """
    try:
        settings = UserDashboardSettings.get_or_create_settings(request.user)
        config = settings.get_dashboard_config()
        serializer = DashboardConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Failed to get dashboard configuration', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reset_to_defaults(request):
    """
    POST: Reset user's dashboard settings to default values
    """
    try:
        settings = UserDashboardSettings.get_or_create_settings(request.user)
        
        # Reset to default values based on user type
        settings.live_lessons_limit = 3
        settings.continue_learning_limit = 25
        settings.show_today_only = True
        settings.theme_preference = 'system'
        settings.notifications_enabled = True
        
        # Reset teacher-specific defaults if user is a teacher
        if settings.user_type == 'teacher':
            settings.default_quiz_points = 1
            settings.default_assignment_points = 5
            settings.default_course_passing_score = 70
            settings.default_quiz_time_limit = 10
            settings.auto_grade_multiple_choice = False
            settings.show_correct_answers_by_default = True
        
        settings.save()
        
        serializer = UserDashboardSettingsSerializer(settings)
        return Response({
            'message': 'Dashboard settings reset to defaults',
            'settings': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to reset dashboard settings', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class TeacherDashboardSettingsView(APIView):
    """
    API View for managing teacher-specific dashboard settings
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        GET: Retrieve current teacher's dashboard settings
        """
        try:
            # Ensure user is a teacher
            if not hasattr(request.user, 'role') or request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can access teacher settings'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            settings = UserDashboardSettings.get_or_create_settings(request.user)
            serializer = UserDashboardSettingsSerializer(settings)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve teacher settings', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        """
        PUT: Update current teacher's dashboard settings
        """
        try:
            # Ensure user is a teacher
            if not hasattr(request.user, 'role') or request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can update teacher settings'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            settings = UserDashboardSettings.get_or_create_settings(request.user)
            serializer = UserDashboardSettingsSerializer(settings, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': 'Failed to update teacher settings', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_teacher_config(request):
    """
    GET: Get simplified teacher configuration for current teacher
    This endpoint is optimized for teacher dashboard views
    """
    try:
        # Ensure user is a teacher
        if not hasattr(request.user, 'role') or request.user.role != 'teacher':
            return Response(
                {'error': 'Only teachers can access teacher configuration'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        settings = UserDashboardSettings.get_or_create_settings(request.user)
        config = settings.get_dashboard_config()
        serializer = DashboardConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Failed to get teacher configuration', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )