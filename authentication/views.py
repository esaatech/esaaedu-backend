from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from django.contrib.auth import get_user_model
from firebase_admin import auth
from .authentication import FirebaseAuthentication
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
        # Optimize query by prefetching related profiles
        user = User.objects.select_related('student_profile', 'teacher_profile').get(id=request.user.id)
        serializer = UserProfileSerializer(user)
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
    Complete student profile setup after initial authentication.
    
    This endpoint is called after a student first logs in to set up
    their profile information. Defaults to student role.
    """
    user = request.user
    
    # Default to student role (since we're focusing on students first)
    role = request.data.get('role', User.Role.STUDENT)
    
    # For now, we only support student role in this endpoint
    if role != User.Role.STUDENT:
        return Response(
            {'error': 'Only student registration is currently supported'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update user role to student
    user.role = User.Role.STUDENT
    user.save()
    
    # Create student profile
    student_profile, created = StudentProfile.objects.get_or_create(user=user)
    
    # Update student profile with provided data
    if 'profile_data' in request.data:
        serializer = StudentProfileSerializer(
            student_profile,
            data=request.data['profile_data'],
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
        else:
            return Response(
                {'error': 'Invalid profile data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    logger.info(f"Student profile created/updated for user: {user.email}")
    
    # Return complete user profile
    serializer = UserProfileSerializer(user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def student_signup(request):
    """
    Complete student signup flow - combines Firebase token verification 
    with student profile creation in one endpoint.
    
    Expected payload:
    {
        "token": "firebase-id-token",
        "profile_data": {
            "grade_level": "Grade 5",
            "parent_email": "parent@example.com",
            "parent_name": "John Doe Sr.",
            "interests": ["coding", "robotics"]
        }
    }
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
        firebase_uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        name = decoded_token.get('name', '')
        
        if not firebase_uid or not email:
            return Response(
                {'error': 'Invalid token: missing required fields'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user already exists
        try:
            existing_user = User.objects.get(firebase_uid=firebase_uid)
            
            # Check if user has a student profile
            try:
                existing_profile = existing_user.student_profile
                
                # User exists and has profile - return existing user
                user_serializer = UserProfileSerializer(existing_user)
                return Response({
                    'message': 'User already exists with complete profile',
                    'user': user_serializer.data
                }, status=status.HTTP_200_OK)
                
            except Exception as profile_error:
                # User exists but no profile - complete the signup
                # We'll continue with the normal signup flow below
                pass
        except User.DoesNotExist:
            # User doesn't exist - proceed with creation
            pass
        
        # Extract user data from request (prioritize React data over Firebase token)
        user_data = request.data.get('user_data', {})
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        
        # Fallback to Firebase token name if React data not provided
        if not first_name and not last_name and name:
            name_parts = name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        logger.info(f"Creating user with: first_name='{first_name}', last_name='{last_name}', email='{email}'")
        
        # Check if we're completing an existing user's signup or creating a new one
        if 'existing_user' in locals() and existing_user:
            user = existing_user
            # Update user info if provided
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save()
            
            # Create the missing student profile
            student_profile = StudentProfile.objects.create(user=user)
        else:
            # Create new student user
            user = User.objects.create_user(
                firebase_uid=firebase_uid,
                email=email,
                first_name=first_name,
                last_name=last_name,
                username=email,
                role=User.Role.STUDENT
            )
            
            # Create student profile
            student_profile = StudentProfile.objects.create(user=user)
        
        # Prepare complete profile data (combine user_data and profile_data)
        profile_update_data = request.data.get('profile_data', {}).copy()
        
        # Handle parent vs student registration differently
        # Check if this is a parent registration (has parent_name and child_name fields)
        is_parent_registration = profile_update_data.get('parent_name') and profile_update_data.get('child_name')
        
        if is_parent_registration:
            print(f"🔍 PARENT REGISTRATION detected for child: {profile_update_data.get('child_name')}")
            # This is a parent registering for their child
            # Extract child name from child_name field
            child_name = profile_update_data.get('child_name', first_name)
            child_name_parts = child_name.split(' ', 1) if child_name else [first_name, '']
            
            profile_update_data['child_first_name'] = child_name_parts[0]
            profile_update_data['child_last_name'] = child_name_parts[1] if len(child_name_parts) > 1 else ''
            # Keep parent info as provided
            if user_data.get('phone'):
                profile_update_data['parent_phone'] = user_data['phone']
        else:
            print(f"🔍 STUDENT REGISTRATION detected (13+ years)")
            # This is a student registering themselves
            profile_update_data['child_first_name'] = first_name
            profile_update_data['child_last_name'] = last_name
            profile_update_data['child_email'] = email
            if user_data.get('phone'):
                profile_update_data['child_phone'] = user_data['phone']
        
        print(f"🔍 Final profile_update_data: {profile_update_data}")
        
        logger.info(f"Updating student profile with data: {profile_update_data}")
        
        # Update student profile with provided data
        if profile_update_data:
            profile_serializer = StudentProfileSerializer(
                student_profile,
                data=profile_update_data,
                partial=True
            )
            if profile_serializer.is_valid():
                profile_serializer.save()
                logger.info(f"Student profile updated successfully for {email}")
            else:
                # If profile data is invalid, still return the user but log the error
                logger.warning(f"Invalid profile data for user {email}: {profile_serializer.errors}")
        else:
            logger.info(f"No profile data provided for user {email}")
        
        logger.info(f"New student user created: {email}")
        
        # Return complete user profile
        user_serializer = UserProfileSerializer(user)
        return Response({
            'message': 'Student account created successfully',
            'user': user_serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid token in student signup: {e}")
        return Response(
            {'error': 'Invalid authentication token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Student signup error: {e}")
        return Response(
            {'error': 'Signup failed', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def student_login(request):
    """
    Student login endpoint - verifies Firebase token and returns student profile.
    
    Expected payload:
    {
        "token": "firebase-id-token"
    }
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
        firebase_uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        
        if not firebase_uid or not email:
            return Response(
                {'error': 'Invalid token: missing required fields'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Find existing user
        try:
            user = User.objects.get(firebase_uid=firebase_uid)
            
            # Ensure user is a student
            if user.role != User.Role.STUDENT:
                if user.role == User.Role.TEACHER:
                    return Response(
                        {'error': 'This account is registered as a Teacher. Please use the Teacher Portal to sign in.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                else:
                    return Response(
                        {'error': 'This account is not registered as a Student. Please check your account type.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Update last login
            from django.utils import timezone
            user.last_login_at = timezone.now()
            user.save(update_fields=['last_login_at'])
            
            # Return user profile
            user_serializer = UserProfileSerializer(user)
            return Response({
                'message': 'Login successful',
                'user': user_serializer.data
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found. Please sign up first.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid token in student login: {e}")
        return Response(
            {'error': 'Invalid authentication token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Student login error: {e}")
        return Response(
            {'error': 'Login failed', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def teacher_signup(request):
    """
    Teacher signup endpoint - creates a new teacher user and profile
    """
    try:
        # Get Firebase token and profile data
        token = request.data.get('token')
        if not token:
            return Response(
                {'error': 'Firebase token is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify Firebase token
        try:
            decoded_token = auth.verify_id_token(token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email', '')
            
            print(f"🎓 Teacher signup - Firebase UID: {firebase_uid}, Email: {email}")
            
        except Exception as e:
            logger.error(f"Invalid token verification: {str(e)}")
            return Response(
                {'error': 'Invalid Firebase token'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user already exists
        if User.objects.filter(firebase_uid=firebase_uid).exists():
            return Response(
                {'error': 'Teacher account already exists'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract user data and teacher profile data
        user_data = request.data.get('user_data', {})
        teacher_data = request.data.get('teacher_data', {})
        
        print(f"🎓 Received user_data: {user_data}")
        print(f"🎓 Received teacher_data: {teacher_data}")
        
        # Extract user information
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        phone = user_data.get('phone', '')

        print(f"🎓 Extracted - First: {first_name}, Last: {last_name}, Phone: {phone}")

        # Create User with TEACHER role
        user = User.objects.create_user(
            firebase_uid=firebase_uid,
            email=email,
            first_name=first_name,
            last_name=last_name,
            username=email,
            role=User.Role.TEACHER
        )
        
        print(f"🎓 Created teacher user: {user.id}")
        
        # Create teacher profile
        from users.models import TeacherProfile
        teacher_profile = TeacherProfile.objects.create(user=user)
        
        # Update teacher profile with provided data
        if teacher_data:
            profile_serializer = TeacherProfileSerializer(
                teacher_profile,
                data=teacher_data,
                partial=True
            )
            if profile_serializer.is_valid():
                profile_serializer.save()
                print(f"🎓 Updated teacher profile: {profile_serializer.data}")
            else:
                print(f"🎓 Teacher profile serializer errors: {profile_serializer.errors}")

        # Serialize and return the complete teacher data
        user_serializer = UserProfileSerializer(user)
        
        response_data = {
            'user': user_serializer.data,
            'message': 'Teacher account created successfully'
        }
        
        print(f"🎓 Teacher signup successful: {user.email}")
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Teacher signup error: {str(e)}")
        return Response(
            {'error': 'Signup failed'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def teacher_login(request):
    """
    Teacher login endpoint - verifies Firebase token and returns teacher profile
    """
    # Validate request data
    serializer = AuthTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Token is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    token = serializer.validated_data['token']
    
    try:
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(token)
        firebase_uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        
        if not firebase_uid or not email:
            return Response(
                {'error': 'Invalid token: missing required fields'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Find existing user
        try:
            user = User.objects.get(firebase_uid=firebase_uid)
            
            # Ensure user is a teacher
            if user.role != User.Role.TEACHER:
                if user.role == User.Role.STUDENT:
                    return Response(
                        {'error': 'This account is registered as a Student. Please use the Student Portal to sign in.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                else:
                    return Response(
                        {'error': 'This account is not registered as a Teacher. Please check your account type.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Update last login
            from django.utils import timezone
            user.last_login_at = timezone.now()
            user.save(update_fields=['last_login_at'])
            
            # Return user profile
            user_serializer = UserProfileSerializer(user)
            return Response({
                'message': 'Teacher login successful',
                'user': user_serializer.data
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Teacher account not found. Please sign up first.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid token in teacher login: {e}")
        return Response(
            {'error': 'Invalid authentication token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Teacher login error: {e}")
        return Response(
            {'error': 'Login failed', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )