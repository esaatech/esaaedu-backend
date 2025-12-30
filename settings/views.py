from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import UserDashboardSettings, ClassroomToolDefaults, UserTutorXInstruction
from .serializers import UserDashboardSettingsSerializer, DashboardConfigSerializer, UserTutorXInstructionSerializer


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
        Includes app-wide defaults for classroom tool URLs
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
            
            # Get app-wide defaults for classroom tools
            app_defaults = ClassroomToolDefaults.get_or_create_defaults()
            
            # Add app defaults to response
            response_data = serializer.data
            response_data['app_defaults'] = {
                'whiteboard_url': app_defaults.whiteboard_url,
                'ide_url': app_defaults.ide_url,
                'virtual_lab_url': app_defaults.virtual_lab_url,
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
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


class UserTutorXInstructionView(APIView):
    """
    API View for managing user instructions for TutorX actions.
    
    Handles getting and updating user instructions per action type.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, action_type):
        """
        GET: Retrieve user instruction for a specific action type.
        
        If instruction doesn't exist, creates it with default from TutorXUserInstructionsDefaults.
        """
        action_type = action_type.lower()
        valid_actions = ['explain_more', 'give_examples', 'simplify', 'summarize', 'generate_questions']
        
        if action_type not in valid_actions:
            return Response(
                {'error': f'Invalid action type. Must be one of: {", ".join(valid_actions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_instruction = UserTutorXInstruction.get_or_create_settings(
                user=request.user,
                action_type=action_type
            )
            serializer = UserTutorXInstructionSerializer(user_instruction)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to get user instruction', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, action_type):
        """
        PUT: Update user instruction for a specific action type.
        """
        action_type = action_type.lower()
        valid_actions = ['explain_more', 'give_examples', 'simplify', 'summarize', 'generate_questions']
        
        if action_type not in valid_actions:
            return Response(
                {'error': f'Invalid action type. Must be one of: {", ".join(valid_actions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_instruction = UserTutorXInstruction.get_or_create_settings(
                user=request.user,
                action_type=action_type
            )
            serializer = UserTutorXInstructionSerializer(
                user_instruction,
                data=request.data,
                partial=True
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update user instruction', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, action_type):
        """
        POST: Reset user instruction to default.
        """
        action_type = action_type.lower()
        valid_actions = ['explain_more', 'give_examples', 'simplify', 'summarize', 'generate_questions']
        
        if action_type not in valid_actions:
            return Response(
                {'error': f'Invalid action type. Must be one of: {", ".join(valid_actions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_instruction = UserTutorXInstruction.get_or_create_settings(
                user=request.user,
                action_type=action_type
            )
            
            if user_instruction.reset_to_default():
                serializer = UserTutorXInstructionSerializer(user_instruction)
                return Response({
                    **serializer.data,
                    'message': 'Instruction reset to default',
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Failed to reset instruction to default'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            return Response(
                {'error': 'Failed to reset user instruction', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )