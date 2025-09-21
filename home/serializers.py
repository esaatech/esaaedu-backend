from rest_framework import serializers
from .models import ContactMethod, SupportTeamMember, FAQ, SupportHours, ContactSubmission


class ContactMethodSerializer(serializers.ModelSerializer):
    """Serializer for contact methods"""
    
    class Meta:
        model = ContactMethod
        fields = [
            'id', 'type', 'title', 'description', 'availability', 
            'response_time', 'action_text', 'action_value', 'icon', 
            'color', 'is_active', 'order'
        ]


class SupportTeamMemberSerializer(serializers.ModelSerializer):
    """Serializer for support team members"""
    
    class Meta:
        model = SupportTeamMember
        fields = [
            'id', 'name', 'title', 'responsibilities', 'email', 
            'avatar_initials', 'is_active', 'order'
        ]


class FAQSerializer(serializers.ModelSerializer):
    """Serializer for FAQs"""
    
    class Meta:
        model = FAQ
        fields = [
            'id', 'question', 'answer', 'category', 'is_active', 'order'
        ]


class SupportHoursSerializer(serializers.ModelSerializer):
    """Serializer for support hours"""
    
    class Meta:
        model = SupportHours
        fields = [
            'id', 'period', 'hours', 'is_emergency', 'is_active', 'order'
        ]


class ContactSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for contact form submissions"""
    
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = ContactSubmission
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone_number',
            'subject', 'child_age', 'message', 'wants_updates',
            'full_name', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value and len(value.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')) < 10:
            raise serializers.ValidationError("Please enter a valid phone number")
        return value
    
    def validate_message(self, value):
        """Validate message length"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long")
        return value


class ContactSubmissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating contact submissions (public endpoint)"""
    
    class Meta:
        model = ContactSubmission
        fields = [
            'first_name', 'last_name', 'email', 'phone_number',
            'subject', 'child_age', 'message', 'wants_updates'
        ]
    
    def validate_first_name(self, value):
        """Validate first name"""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("First name must be at least 2 characters long")
        return value.strip()
    
    def validate_last_name(self, value):
        """Validate last name"""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Last name must be at least 2 characters long")
        return value.strip()
    
    def validate_email(self, value):
        """Validate email format"""
        if not value or '@' not in value:
            raise serializers.ValidationError("Please enter a valid email address")
        return value.lower().strip()
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            # Remove all non-digit characters
            digits_only = ''.join(filter(str.isdigit, value))
            if len(digits_only) < 10:
                raise serializers.ValidationError("Please enter a valid phone number")
        return value
    
    def validate_message(self, value):
        """Validate message content"""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long")
        if len(value.strip()) > 2000:
            raise serializers.ValidationError("Message must be less than 2000 characters")
        return value.strip()


class ContactOverviewSerializer(serializers.Serializer):
    """Serializer for contact overview data"""
    contact_methods = ContactMethodSerializer(many=True)
    support_team = SupportTeamMemberSerializer(many=True)
    faqs = FAQSerializer(many=True)
    support_hours = SupportHoursSerializer(many=True)
