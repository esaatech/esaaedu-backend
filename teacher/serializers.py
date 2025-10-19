from rest_framework import serializers
from users.models import User, TeacherProfile
from courses.models import Project, ProjectSubmission, Assignment, AssignmentQuestion, AssignmentSubmission


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


# ===== ASSIGNMENT SERIALIZERS =====

class AssignmentQuestionCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating assignment questions
    Handles content object format from frontend
    """
    # Content field that contains all question data
    content = serializers.JSONField(required=False, allow_null=True)
    
    class Meta:
        model = AssignmentQuestion
        fields = [
            'question_text', 'type', 'content', 'explanation', 'points', 'order'
        ]
        extra_kwargs = {
            'question_text': {'required': True},
            'type': {'required': True},
            'points': {'required': True},
            'order': {'required': True}
        }
    
    def create(self, validated_data):
        """Create assignment question with content from frontend"""
        # Content is already structured by frontend
        content = validated_data.get('content', {})
        validated_data['content'] = content
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update assignment question with content from frontend"""
        # Content is already structured by frontend
        content = validated_data.get('content', {})
        validated_data['content'] = content
        return super().update(instance, validated_data)


class AssignmentQuestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for assignment question details
    Returns both legacy and new format data
    """
    # Legacy fields extracted from content
    options = serializers.SerializerMethodField()
    correct_answer = serializers.SerializerMethodField()
    
    # New field for rich options with explanations
    full_options = serializers.SerializerMethodField()
    
    class Meta:
        model = AssignmentQuestion
        fields = [
            'id', 'question_text', 'type', 'options', 'correct_answer',
            'explanation', 'points', 'order', 'created_at', 'updated_at', 'full_options'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_options(self, obj):
        """Extract options from content JSONField"""
        return obj.content.get('options', []) if obj.content else []
    
    def get_correct_answer(self, obj):
        """Extract correct_answer from content JSONField"""
        return obj.content.get('correct_answer', '') if obj.content else ''
    
    def get_full_options(self, obj):
        """Extract full_options from content JSONField"""
        full_options = obj.content.get('full_options', None) if obj.content else None
        return full_options


class AssignmentQuestionSerializer(serializers.ModelSerializer):
    """
    Legacy serializer for assignment questions (kept for backward compatibility)
    """
    class Meta:
        model = AssignmentQuestion
        fields = [
            'id', 'question_text', 'order', 'points', 'type', 'content', 
            'explanation', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_content(self, value):
        """Validate question content based on type"""
        question_type = self.initial_data.get('type')
        
        if question_type == 'multiple_choice':
            if 'options' not in value or 'correct_answer' not in value:
                raise serializers.ValidationError("Multiple choice questions require 'options' and 'correct_answer'")
        
        elif question_type == 'true_false':
            if 'correct_answer' not in value:
                raise serializers.ValidationError("True/False questions require 'correct_answer'")
        
        elif question_type == 'flashcard':
            if 'answer' not in value:
                raise serializers.ValidationError("Flashcard questions require 'answer'")
        
        return value


class AssignmentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for assignment lists
    """
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_title = serializers.CharField(source='lesson.course.title', read_only=True)
    question_count = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'assignment_type', 'due_date',
            'lesson_title', 'course_title', 'question_count', 'submission_count',
            'graded_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_question_count(self, obj):
        return obj.questions.count()
    
    def get_submission_count(self, obj):
        return obj.submissions.count()
    
    def get_graded_count(self, obj):
        return obj.submissions.filter(is_graded=True).count()


class AssignmentDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for assignment with questions
    """
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_title = serializers.CharField(source='lesson.course.title', read_only=True)
    questions = AssignmentQuestionDetailSerializer(many=True, read_only=True)
    question_count = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'assignment_type', 'due_date',
            'passing_score', 'max_attempts', 'show_correct_answers', 'randomize_questions',
            'lesson_title', 'course_title', 'questions', 'question_count',
            'submission_count', 'graded_count', 'pending_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_question_count(self, obj):
        return obj.questions.count()
    
    def get_submission_count(self, obj):
        return obj.submissions.count()
    
    def get_graded_count(self, obj):
        return obj.submissions.filter(is_graded=True).count()
    
    def get_pending_count(self, obj):
        return obj.submissions.filter(is_graded=False).count()


class AssignmentCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating assignments
    """
    class Meta:
        model = Assignment
        fields = [
            'lesson', 'title', 'description', 'assignment_type', 'due_date',
            'passing_score', 'max_attempts', 'show_correct_answers', 'randomize_questions'
        ]
    
    def validate_lesson(self, value):
        """Ensure the lesson belongs to the requesting teacher"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.course.teacher != request.user:
                raise serializers.ValidationError("You can only create assignments for your own courses.")
        return value
    
    def validate_due_date(self, value):
        """Validate due date is in the future"""
        from django.utils import timezone
        if value and value <= timezone.now():
            raise serializers.ValidationError("Due date must be in the future")
        return value
    
    def validate_passing_score(self, value):
        """Validate passing score is between 0 and 100"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Passing score must be between 0 and 100")
        return value


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer for assignment submissions (teacher grading view)
    """
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    grader_name = serializers.CharField(read_only=True)
    display_status = serializers.CharField(read_only=True)
    
    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'student', 'student_name', 'student_email', 'attempt_number',
            'submitted_at', 'answers', 'is_graded', 'is_teacher_draft', 'graded_at', 'graded_by',
            'grader_name', 'points_earned', 'points_possible', 'percentage',
            'passed', 'instructor_feedback', 'feedback_checked', 'feedback_checked_at',
            'feedback_response', 'graded_questions', 'display_status'
        ]
        read_only_fields = [
            'id', 'student', 'student_name', 'student_email', 'attempt_number',
            'submitted_at', 'graded_at', 'grader_name', 'percentage', 'passed',
            'feedback_checked', 'feedback_checked_at', 'display_status'
        ]
    
    def validate_points_earned(self, value):
        """Validate points earned"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Points earned cannot be negative")
        return value
    
    def validate(self, data):
        """Validate grading data"""
        if data.get('is_graded') and not data.get('points_earned'):
            raise serializers.ValidationError("Graded submissions must have points earned")
        
        if data.get('points_earned') and not data.get('points_possible'):
            raise serializers.ValidationError("Points possible is required when points earned is provided")
        
        return data


class AssignmentGradingSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for grading assignments
    """
    class Meta:
        model = AssignmentSubmission
        fields = [
            'status', 'is_graded', 'is_teacher_draft', 'points_earned', 'points_possible', 'instructor_feedback',
            'graded_questions'
        ]
    
    def validate(self, data):
        """Validate grading data"""
        if data.get('is_graded'):
            if not data.get('points_earned'):
                raise serializers.ValidationError("Points earned is required for graded submissions")
            if not data.get('points_possible'):
                raise serializers.ValidationError("Points possible is required for graded submissions")
        
        return data


class AssignmentFeedbackSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for providing feedback on assignments
    """
    class Meta:
        model = AssignmentSubmission
        fields = [
            'instructor_feedback', 'feedback_response'
        ]
    
    def validate_instructor_feedback(self, value):
        """Validate instructor feedback"""
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("Instructor feedback must be at least 10 characters long")
        return value
