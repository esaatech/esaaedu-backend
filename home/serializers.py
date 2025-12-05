from rest_framework import serializers
from .models import ContactMethod, SupportTeamMember, FAQ, SupportHours, ContactSubmission, AssessmentSubmission


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


class AssessmentSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for assessment form submissions"""
    
    class Meta:
        model = AssessmentSubmission
        fields = [
            'id', 'parent_name', 'parent_contact', 'email',
            'student_name', 'student_age', 'school_level', 'city_country',
            'interest_areas', 'has_coding_experience', 'coding_tools',
            'device_access', 'availability_days', 'preferred_time_slots',
            'goals', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']


class AssessmentSubmissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating assessment submissions (public endpoint)"""
    
    class Meta:
        model = AssessmentSubmission
        fields = [
            'parent_name', 'parent_contact', 'email',
            'student_name', 'student_age', 'school_level', 'city_country',
            'interest_areas', 'has_coding_experience', 'coding_tools',
            'computer_skills_level',
            'device_access', 'availability_days', 'preferred_time_slots',
            'goals'
        ]
    
    def validate_parent_name(self, value):
        """Validate parent name"""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Parent name must be at least 2 characters long")
        return value.strip()
    
    def validate_parent_contact(self, value):
        """Validate contact number"""
        if not value:
            raise serializers.ValidationError("Contact number is required")
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, value))
        if len(digits_only) < 10:
            raise serializers.ValidationError("Please enter a valid contact number")
        return value
    
    def validate_email(self, value):
        """Validate email format"""
        if not value or '@' not in value:
            raise serializers.ValidationError("Please enter a valid email address")
        return value.lower().strip()
    
    def validate_student_name(self, value):
        """Validate student name"""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Student name must be at least 2 characters long")
        return value.strip()
    
    def validate_student_age(self, value):
        """Validate student age"""
        if not value or value < 3 or value > 18:
            raise serializers.ValidationError("Student age must be between 3 and 18")
        return value
    
    def validate_interest_areas(self, value):
        """Validate interest areas"""
        if not value or not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("Please select at least one interest area")
        return value
    
    def validate_device_access(self, value):
        """Validate device access"""
        if not value or not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("Please select at least one device option")
        return value
    
    def validate_availability_days(self, value):
        """Validate availability days"""
        if not value or not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("Please select at least one day")
        return value
    
    def validate_computer_skills_level(self, value):
        """Validate computer skills level"""
        if value is None or value == '':
            return None
        if value not in ['beginner', 'intermediate', 'advanced']:
            raise serializers.ValidationError("Please select a valid computer skills level")
        return value
