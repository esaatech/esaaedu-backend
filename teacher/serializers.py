from rest_framework import serializers
from users.models import User, TeacherProfile


class TeacherProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for teacher profile data
    """
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    role = serializers.CharField(source='user.role', read_only=True)
    created_at = serializers.DateTimeField(source='user.created_at', read_only=True)
    last_login_at = serializers.DateTimeField(source='user.last_login_at', read_only=True)
    
    class Meta:
        model = TeacherProfile
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'role',
            'bio', 'qualifications', 'department', 'profile_image', 'phone_number',
            'specializations', 'years_of_experience', 'linkedin_url', 'twitter_url',
            'created_at', 'last_login_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or f"{obj.user.first_name} {obj.user.last_name}".strip()


class TeacherProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating teacher profile data
    """
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    
    class Meta:
        model = TeacherProfile
        fields = [
            'bio', 'qualifications', 'department', 'profile_image', 'phone_number',
            'specializations', 'years_of_experience', 'linkedin_url', 'twitter_url',
            'first_name', 'last_name'
        ]
    
    def update(self, instance, validated_data):
        # Handle user fields separately
        user_data = {}
        if 'user' in validated_data:
            user_data = validated_data.pop('user')
        
        # Update user fields
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()
        
        # Update teacher profile fields
        return super().update(instance, validated_data)
