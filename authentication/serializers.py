from rest_framework import serializers
from django.contrib.auth import get_user_model
from users.models import TeacherProfile, StudentProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model
    """
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'firebase_uid', 'email', 'first_name', 'last_name', 
            'full_name', 'role', 'is_active', 'created_at', 'last_login_at'
        ]
        read_only_fields = ['id', 'firebase_uid', 'created_at', 'last_login_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class TeacherProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for TeacherProfile model
    """
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = TeacherProfile
        fields = [
            'user', 'bio', 'qualifications', 'department', 'profile_image',
            'phone_number', 'specializations', 'years_of_experience',
            'linkedin_url', 'twitter_url', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class StudentProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for StudentProfile model
    """
    user = UserSerializer(read_only=True)
    age = serializers.ReadOnlyField()
    
    class Meta:
        model = StudentProfile
        fields = [
            'user', 'child_first_name', 'child_last_name', 'child_email', 'child_phone',
            'grade_level', 'date_of_birth', 'profile_image',
            'parent_email', 'parent_name', 'parent_phone', 'emergency_contact',
            'learning_goals', 'interests', 'notifications_enabled',
            'email_notifications', 'age', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'age']


class AuthTokenSerializer(serializers.Serializer):
    """
    Serializer for Firebase ID token authentication
    """
    token = serializers.CharField(
        help_text="Firebase ID token obtained from frontend authentication"
    )


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Combined user profile serializer that includes role-specific profile data
    """
    teacher_profile = TeacherProfileSerializer(read_only=True)
    student_profile = StudentProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'firebase_uid', 'email', 'first_name', 'last_name',
            'full_name', 'role', 'is_active', 'created_at', 'last_login_at',
            'teacher_profile', 'student_profile'
        ]
        read_only_fields = ['id', 'firebase_uid', 'created_at', 'last_login_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class RoleUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating user role
    """
    role = serializers.ChoiceField(choices=User.Role.choices)
    
    def validate_role(self, value):
        """
        Validate role change permissions
        """
        user = self.context['request'].user
        
        # Only allow admin to change roles for now
        # In the future, you might want more complex role change logic
        if not user.is_staff:
            raise serializers.ValidationError("Only administrators can change user roles")
        
        return value
