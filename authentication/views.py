from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from django.contrib.auth import get_user_model
from firebase_admin import auth
from .serializers import (
    AuthTokenSerializer, UserProfileSerializer, RoleUpdateSerializer,
    TeacherProfileSerializer, StudentProfileSerializer
)
from users.models import TeacherProfile, StudentProfile
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_token(request):
    """
    Verify Firebase ID token and return user information.
    
    This endpoint can be used by the frontend to verify tokens
    and get user information without full authentication.
    """
    serializer = AuthTokenSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    token = serializer.validated_data['token']
    
    try:
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(token)
        
        return Response({
            'valid': True,
            'user_info': {
                'uid': decoded_token.get('uid'),
                'email': decoded_token.get('email'),
                'name': decoded_token.get('name'),
                'email_verified': decoded_token.get('email_verified', False),
            }
        })
        
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid token verification: {e}")
        return Response(
            {'valid': False, 'error': 'Invalid token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return Response(
            {'valid': False, 'error': 'Token verification failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class AuthenticatedUserView(APIView):
    """
    Get current authenticated user information.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Return current user profile information.
        """
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class UserProfileView(RetrieveUpdateAPIView):
    """
    Retrieve and update user profile.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        """
        Update user profile information.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Update user fields
        user = serializer.save()
        
        # Update role-specific profile if data provided
        if user.is_teacher and 'teacher_profile' in request.data:
            teacher_profile, created = TeacherProfile.objects.get_or_create(user=user)
            teacher_serializer = TeacherProfileSerializer(
                teacher_profile, 
                data=request.data['teacher_profile'], 
                partial=partial
            )
            if teacher_serializer.is_valid():
                teacher_serializer.save()
        
        elif user.is_student and 'student_profile' in request.data:
            student_profile, created = StudentProfile.objects.get_or_create(user=user)
            student_serializer = StudentProfileSerializer(
                student_profile,
                data=request.data['student_profile'],
                partial=partial
            )
            if student_serializer.is_valid():
                student_serializer.save()
        
        # Return updated data
        updated_serializer = UserProfileSerializer(user)
        return Response(updated_serializer.data)


class UpdateUserRoleView(APIView):
    """
    Update user role (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request, user_id):
        """
        Update user role.
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = RoleUpdateSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_role = serializer.validated_data['role']
        old_role = user.role
        
        # Update user role
        user.role = new_role
        user.save()
        
        # Create appropriate profile if role changed
        if new_role == User.Role.TEACHER and old_role != User.Role.TEACHER:
            TeacherProfile.objects.get_or_create(user=user)
        elif new_role == User.Role.STUDENT and old_role != User.Role.STUDENT:
            StudentProfile.objects.get_or_create(user=user)
        
        logger.info(f"User {user.email} role changed from {old_role} to {new_role}")
        
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def complete_profile_setup(request):
    """
    Complete user profile setup after initial authentication.
    
    This endpoint is called after a user first logs in to set up
    their role and profile information.
    """
    user = request.user
    role = request.data.get('role')
    
    if not role or role not in [choice[0] for choice in User.Role.choices]:
        return Response(
            {'error': 'Valid role is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update user role
    user.role = role
    user.save()
    
    # Create appropriate profile
    if role == User.Role.TEACHER:
        profile, created = TeacherProfile.objects.get_or_create(user=user)
        if 'profile_data' in request.data:
            serializer = TeacherProfileSerializer(
                profile, 
                data=request.data['profile_data'], 
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
    
    elif role == User.Role.STUDENT:
        profile, created = StudentProfile.objects.get_or_create(user=user)
        if 'profile_data' in request.data:
            serializer = StudentProfileSerializer(
                profile,
                data=request.data['profile_data'],
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
    
    # Return updated user profile
    serializer = UserProfileSerializer(user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)