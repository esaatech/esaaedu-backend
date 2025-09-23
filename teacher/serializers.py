from rest_framework import serializers
from users.models import User, TeacherProfile
from courses.models import Project, ProjectSubmission


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


class ProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for Project model - Teacher project management
    """
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_id = serializers.UUIDField(source='course.id', read_only=True)
    submission_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    submission_type_display = serializers.CharField(read_only=True)
    requires_file_upload = serializers.BooleanField(read_only=True)
    requires_text_input = serializers.BooleanField(read_only=True)
    requires_url_input = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'course', 'course_id', 'course_title', 'title', 'instructions',
            'submission_type', 'submission_type_display', 'allowed_file_types',
            'points', 'due_at', 'created_at', 'submission_count', 'graded_count',
            'pending_count', 'requires_file_upload', 'requires_text_input', 'requires_url_input'
        ]
        read_only_fields = ['id', 'created_at', 'submission_count', 'graded_count', 'pending_count']
    
    def get_submission_count(self, obj):
        return obj.submissions.count()
    
    def get_graded_count(self, obj):
        return obj.submissions.filter(status='GRADED').count()
    
    def get_pending_count(self, obj):
        return obj.submissions.filter(status__in=['ASSIGNED', 'SUBMITTED', 'RETURNED']).count()


class ProjectCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating projects
    """
    class Meta:
        model = Project
        fields = [
            'course', 'title', 'instructions', 'submission_type',
            'allowed_file_types', 'points', 'due_at'
        ]
    
    def validate_course(self, value):
        """Ensure the course belongs to the requesting teacher"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.teacher != request.user:
                raise serializers.ValidationError("You can only create projects for your own courses.")
        return value
    
    def validate_points(self, value):
        """Ensure points is positive"""
        if value <= 0:
            raise serializers.ValidationError("Points must be greater than 0.")
        return value


class ProjectSubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer for ProjectSubmission model - Teacher grading view
    """
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    project_id = serializers.UUIDField(source='project.id', read_only=True)
    grader_name = serializers.CharField(source='grader.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ProjectSubmission
        fields = [
            'id', 'project', 'project_id', 'project_title', 'student', 'student_name',
            'student_email', 'status', 'status_display', 'content', 'file_url',
            'reflection', 'submitted_at', 'graded_at', 'grader', 'grader_name',
            'points_earned', 'feedback', 'feedback_response', 'feedback_checked',
            'feedback_checked_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'project', 'student', 'submitted_at', 'created_at', 'updated_at'
        ]


class ProjectSubmissionGradingSerializer(serializers.ModelSerializer):
    """
    Serializer for grading project submissions
    """
    class Meta:
        model = ProjectSubmission
        fields = [
            'status', 'points_earned', 'feedback'
        ]
    
    def validate_status(self, value):
        """Validate status transitions"""
        if value not in ['ASSIGNED', 'SUBMITTED', 'RETURNED', 'GRADED']:
            raise serializers.ValidationError("Invalid status value.")
        return value
    
    def validate_points_earned(self, value):
        """Validate points earned"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Points earned cannot be negative.")
        return value
    
    def validate(self, data):
        """Validate grading data"""
        status = data.get('status')
        points_earned = data.get('points_earned')
        
        # If status is GRADED, points_earned should be provided
        if status == 'GRADED' and points_earned is None:
            raise serializers.ValidationError("Points earned is required when status is GRADED.")
        
        return data


class ProjectSubmissionFeedbackSerializer(serializers.ModelSerializer):
    """
    Serializer for providing feedback on project submissions
    """
    class Meta:
        model = ProjectSubmission
        fields = [
            'status', 'feedback'
        ]
    
    def validate_status(self, value):
        """Validate status for feedback"""
        if value not in ['RETURNED', 'GRADED']:
            raise serializers.ValidationError("Status must be RETURNED or GRADED for feedback.")
        return value
