from rest_framework import serializers
from .models import UserDashboardSettings, UserTutorXInstruction


class UserDashboardSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for User Dashboard Settings
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    
    class Meta:
        model = UserDashboardSettings
        fields = [
            'id',
            'user',
            'user_type',
            'user_email',
            'user_role',
            'live_lessons_limit',
            'continue_learning_limit',
            'show_today_only',
            'theme_preference',
            'notifications_enabled',
            # Teacher-specific fields
            'default_quiz_points',
            'default_assignment_points',
            'default_course_passing_score',
            'default_quiz_time_limit',
            'auto_grade_multiple_choice',
            'show_correct_answers_by_default',
            # Classroom tool URLs (teachers only)
            'whiteboard_url',
            'ide_url',
            'virtual_lab_url',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'user_email', 'user_role', 'created_at', 'updated_at']
    
    def validate_live_lessons_limit(self, value):
        """Validate live lessons limit"""
        if value < 1 or value > 50:
            raise serializers.ValidationError("Live lessons limit must be between 1 and 50")
        return value
    
    def validate_continue_learning_limit(self, value):
        """Validate continue learning limit"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Continue learning limit must be between 1 and 100")
        return value
    
    def validate_default_quiz_points(self, value):
        """Validate default quiz points"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Default quiz points must be between 1 and 100")
        return value
    
    def validate_default_assignment_points(self, value):
        """Validate default assignment points"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Default assignment points must be between 1 and 100")
        return value
    
    def validate_default_course_passing_score(self, value):
        """Validate default course passing score"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Default course passing score must be between 0 and 100")
        return value
    
    def validate_default_quiz_time_limit(self, value):
        """Validate default quiz time limit"""
        if value < 1 or value > 180:
            raise serializers.ValidationError("Default quiz time limit must be between 1 and 180 minutes")
        return value


class DashboardConfigSerializer(serializers.Serializer):
    """
    Simplified serializer for dashboard configuration
    Used by the dashboard view to get current settings
    """
    live_lessons_limit = serializers.IntegerField()
    continue_learning_limit = serializers.IntegerField()
    show_today_only = serializers.BooleanField()
    theme_preference = serializers.CharField()
    notifications_enabled = serializers.BooleanField()
    # Teacher-specific fields
    default_quiz_points = serializers.IntegerField(required=False)
    default_assignment_points = serializers.IntegerField(required=False)
    default_course_passing_score = serializers.IntegerField(required=False)
    default_quiz_time_limit = serializers.IntegerField(required=False)
    auto_grade_multiple_choice = serializers.BooleanField(required=False)
    show_correct_answers_by_default = serializers.BooleanField(required=False)
    # Classroom tool URLs (teachers only)
    whiteboard_url = serializers.URLField(required=False, allow_blank=True)
    ide_url = serializers.URLField(required=False, allow_blank=True)
    virtual_lab_url = serializers.URLField(required=False, allow_blank=True)


class UserTutorXInstructionSerializer(serializers.ModelSerializer):
    """
    Serializer for User TutorX Instructions
    """
    is_customized = serializers.SerializerMethodField()
    
    class Meta:
        model = UserTutorXInstruction
        fields = [
            'id',
            'action_type',
            'user_instruction',
            'is_customized',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'action_type', 'is_customized', 'created_at', 'updated_at']
    
    def get_is_customized(self, obj):
        """Return whether the instruction has been customized from default"""
        return obj.is_customized()
    
    def validate_user_instruction(self, value):
        """Validate user instruction"""
        if not value or not value.strip():
            raise serializers.ValidationError("User instruction cannot be empty")
        
        if len(value) > 5000:
            raise serializers.ValidationError("User instruction cannot exceed 5000 characters")
        
        return value.strip()
