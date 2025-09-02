from rest_framework import serializers
from .models import UserDashboardSettings


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
            'user_email',
            'user_role',
            'live_lessons_limit',
            'continue_learning_limit',
            'show_today_only',
            'theme_preference',
            'notifications_enabled',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user_email', 'user_role', 'created_at', 'updated_at']
    
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
