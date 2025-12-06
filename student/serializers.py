from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    EnrolledCourse, StudentAttendance, StudentGrade, 
    StudentBehavior, StudentNote, StudentCommunication,
    QuizQuestionFeedback, QuizAttemptFeedback,
    Conversation, Message, CodeSnippet
)
from courses.models import AssignmentSubmission

User = get_user_model()


# ===== BASIC SERIALIZERS =====

class BasicUserSerializer(serializers.ModelSerializer):
    """Basic user information for nested serialization"""
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'name']
    
    def get_name(self, obj):
        return obj.get_full_name() or obj.email


class BasicStudentProfileSerializer(serializers.ModelSerializer):
    """Basic student profile information"""
    user = BasicUserSerializer(read_only=True)
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = 'users.StudentProfile'
        fields = [
            'user', 'name', 'child_first_name', 'child_last_name', 
            'grade_level', 'profile_image'
        ]
    
    def get_name(self, obj):
        return f"{obj.child_first_name} {obj.child_last_name}".strip() or obj.user.get_full_name()


class BasicCourseSerializer(serializers.ModelSerializer):
    """Basic course information for nested serialization"""
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    
    class Meta:
        model = 'courses.Course'
        fields = ['id', 'title', 'description', 'teacher_name', 'level', 'status']


# ===== ENROLLED COURSE SERIALIZERS =====

class EnrolledCourseListSerializer(serializers.ModelSerializer):
    """List view of enrolled courses"""
    student_name = serializers.CharField(source='student_profile.user.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_level = serializers.CharField(source='course.level', read_only=True)
    teacher_name = serializers.CharField(source='course.teacher.get_full_name', read_only=True)
    
    # Computed properties
    is_active = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    days_since_enrollment = serializers.ReadOnlyField()
    days_since_last_access = serializers.ReadOnlyField()
    completion_rate = serializers.ReadOnlyField()
    is_at_risk = serializers.ReadOnlyField()
    
    class Meta:
        model = EnrolledCourse
        fields = [
            'id', 'student_name', 'course_title', 'course_level', 'teacher_name',
            'status', 'progress_percentage', 'overall_grade', 'enrollment_date',
            'last_accessed', 'payment_status', 'certificate_issued',
            'is_active', 'is_completed', 'days_since_enrollment', 
            'days_since_last_access', 'completion_rate', 'is_at_risk'
        ]


class EnrolledCourseDetailSerializer(serializers.ModelSerializer):
    """Detailed view of enrolled course"""
    student_profile = BasicStudentProfileSerializer(read_only=True)
    course = BasicCourseSerializer(read_only=True)
    enrolled_by_name = serializers.CharField(source='enrolled_by.get_full_name', read_only=True)
    current_lesson_title = serializers.CharField(source='current_lesson.title', read_only=True)
    
    # Computed properties
    is_active = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    days_since_enrollment = serializers.ReadOnlyField()
    days_since_last_access = serializers.ReadOnlyField()
    completion_rate = serializers.ReadOnlyField()
    assignment_completion_rate = serializers.ReadOnlyField()
    is_at_risk = serializers.ReadOnlyField()
    
    class Meta:
        model = EnrolledCourse
        fields = [
            'id', 'student_profile', 'course', 'status', 'enrolled_by_name',
            'enrollment_date', 'progress_percentage', 'current_lesson', 'current_lesson_title',
            'completed_lessons_count', 'total_lessons_count', 'overall_grade', 'gpa_points',
            'average_quiz_score', 'total_assignments_completed', 'total_assignments_assigned',
            'total_study_time', 'last_accessed', 'login_count', 'total_video_watch_time',
            'payment_status', 'amount_paid', 'payment_due_date', 'discount_applied',
            'completion_date', 'certificate_issued', 'certificate_url', 'final_grade_issued',
            'parent_notifications_enabled', 'reminder_emails_enabled', 'special_accommodations',
            'is_active', 'is_completed', 'days_since_enrollment', 'days_since_last_access',
            'completion_rate', 'assignment_completion_rate', 'is_at_risk',
            'created_at', 'updated_at', 'last_progress_update'
        ]


class EnrolledCourseCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update enrolled course"""
    
    class Meta:
        model = EnrolledCourse
        fields = [
            'student_profile', 'course', 'status', 'enrolled_by',
            'progress_percentage', 'current_lesson', 'completed_lessons_count',
            'total_lessons_count', 'overall_grade', 'gpa_points', 'average_quiz_score',
            'total_assignments_completed', 'total_assignments_assigned',
            'payment_status', 'amount_paid', 'payment_due_date', 'discount_applied',
            'parent_notifications_enabled', 'reminder_emails_enabled', 'special_accommodations'
        ]
    
    def validate(self, data):
        """Validate enrollment data"""
        student_profile = data.get('student_profile')
        course = data.get('course')
        
        # Check if student is already enrolled (for create)
        if not self.instance and EnrolledCourse.objects.filter(
            student_profile=student_profile, course=course
        ).exists():
            raise serializers.ValidationError(
                "Student is already enrolled in this course"
            )
        
        return data


# ===== STUDENT ATTENDANCE SERIALIZERS =====

class StudentAttendanceListSerializer(serializers.ModelSerializer):
    """List view of student attendance"""
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    class_name = serializers.CharField(source='class_session.name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    
    class Meta:
        model = StudentAttendance
        fields = [
            'id', 'student_name', 'class_name', 'date', 'status',
            'check_in_time', 'check_out_time', 'recorded_by_name', 'created_at'
        ]


class StudentAttendanceDetailSerializer(serializers.ModelSerializer):
    """Detailed view of student attendance"""
    student = BasicUserSerializer(read_only=True)
    recorded_by = BasicUserSerializer(read_only=True)
    
    class Meta:
        model = StudentAttendance
        fields = [
            'id', 'student', 'class_session', 'date', 'status',
            'check_in_time', 'check_out_time', 'notes', 'recorded_by',
            'created_at', 'updated_at'
        ]


class StudentAttendanceCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update student attendance"""
    
    class Meta:
        model = StudentAttendance
        fields = [
            'student', 'class_session', 'date', 'status',
            'check_in_time', 'check_out_time', 'notes'
        ]


# ===== STUDENT GRADE SERIALIZERS =====

class StudentGradeListSerializer(serializers.ModelSerializer):
    """List view of student grades"""
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    graded_by_name = serializers.CharField(source='graded_by.get_full_name', read_only=True)
    
    class Meta:
        model = StudentGrade
        fields = [
            'id', 'student_name', 'course_title', 'title', 'grade_type',
            'points_earned', 'points_possible', 'percentage', 'letter_grade',
            'graded_date', 'graded_by_name'
        ]


class StudentGradeDetailSerializer(serializers.ModelSerializer):
    """Detailed view of student grade"""
    student = BasicUserSerializer(read_only=True)
    course = BasicCourseSerializer(read_only=True)
    graded_by = BasicUserSerializer(read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = StudentGrade
        fields = [
            'id', 'student', 'course', 'lesson', 'lesson_title', 'quiz_attempt',
            'grade_type', 'title', 'description', 'points_earned', 'points_possible',
            'percentage', 'letter_grade', 'teacher_comments', 'private_notes',
            'assigned_date', 'due_date', 'submitted_date', 'graded_date',
            'graded_by', 'created_at', 'updated_at'
        ]


class StudentGradeCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update student grade"""
    
    class Meta:
        model = StudentGrade
        fields = [
            'student', 'course', 'lesson', 'quiz_attempt', 'grade_type',
            'title', 'description', 'points_earned', 'points_possible',
            'teacher_comments', 'private_notes', 'assigned_date', 'due_date',
            'submitted_date'
        ]
    
    def validate(self, data):
        """Validate grade data"""
        points_earned = data.get('points_earned', 0)
        points_possible = data.get('points_possible', 0)
        
        if points_possible <= 0:
            raise serializers.ValidationError("Points possible must be greater than 0")
        
        if points_earned < 0:
            raise serializers.ValidationError("Points earned cannot be negative")
        
        if points_earned > points_possible:
            raise serializers.ValidationError("Points earned cannot exceed points possible")
        
        return data


# ===== STUDENT BEHAVIOR SERIALIZERS =====

class StudentBehaviorListSerializer(serializers.ModelSerializer):
    """List view of student behavior"""
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    class_name = serializers.CharField(source='class_session.name', read_only=True)
    reported_by_name = serializers.CharField(source='reported_by.get_full_name', read_only=True)
    
    class Meta:
        model = StudentBehavior
        fields = [
            'id', 'student_name', 'class_name', 'behavior_type', 'category',
            'title', 'severity', 'incident_date', 'reported_by_name',
            'parent_contacted', 'follow_up_required'
        ]


class StudentBehaviorDetailSerializer(serializers.ModelSerializer):
    """Detailed view of student behavior"""
    student = BasicUserSerializer(read_only=True)
    reported_by = BasicUserSerializer(read_only=True)
    
    class Meta:
        model = StudentBehavior
        fields = [
            'id', 'student', 'class_session', 'behavior_type', 'category',
            'title', 'description', 'severity', 'action_taken',
            'parent_contacted', 'parent_contact_date', 'follow_up_required',
            'follow_up_date', 'incident_date', 'reported_by',
            'created_at', 'updated_at'
        ]


class StudentBehaviorCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update student behavior"""
    
    class Meta:
        model = StudentBehavior
        fields = [
            'student', 'class_session', 'behavior_type', 'category',
            'title', 'description', 'severity', 'action_taken',
            'parent_contacted', 'parent_contact_date', 'follow_up_required',
            'follow_up_date', 'incident_date'
        ]


# ===== STUDENT NOTE SERIALIZERS =====

class StudentNoteListSerializer(serializers.ModelSerializer):
    """List view of student notes"""
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    
    class Meta:
        model = StudentNote
        fields = [
            'id', 'student_name', 'teacher_name', 'category', 'title',
            'is_important', 'created_at', 'updated_at'
        ]


class StudentNoteDetailSerializer(serializers.ModelSerializer):
    """Detailed view of student note"""
    student = BasicUserSerializer(read_only=True)
    teacher = BasicUserSerializer(read_only=True)
    
    class Meta:
        model = StudentNote
        fields = [
            'id', 'student', 'teacher', 'category', 'title', 'content',
            'is_private', 'is_important', 'created_at', 'updated_at'
        ]


class StudentNoteCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update student note"""
    
    class Meta:
        model = StudentNote
        fields = [
            'student', 'category', 'title', 'content',
            'is_private', 'is_important'
        ]


# ===== STUDENT COMMUNICATION SERIALIZERS =====

class StudentCommunicationListSerializer(serializers.ModelSerializer):
    """List view of student communications"""
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    
    class Meta:
        model = StudentCommunication
        fields = [
            'id', 'student_name', 'teacher_name', 'communication_type',
            'purpose', 'subject', 'sent_date', 'response_received',
            'follow_up_required'
        ]


class StudentCommunicationDetailSerializer(serializers.ModelSerializer):
    """Detailed view of student communication"""
    student = BasicUserSerializer(read_only=True)
    teacher = BasicUserSerializer(read_only=True)
    
    class Meta:
        model = StudentCommunication
        fields = [
            'id', 'student', 'teacher', 'communication_type', 'purpose',
            'subject', 'message', 'contacted_student', 'contacted_parent',
            'parent_email', 'parent_phone', 'response_received', 'response_date',
            'response_content', 'follow_up_required', 'follow_up_date',
            'follow_up_completed', 'sent_date', 'created_at', 'updated_at'
        ]


class StudentCommunicationCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update student communication"""
    
    class Meta:
        model = StudentCommunication
        fields = [
            'student', 'communication_type', 'purpose', 'subject', 'message',
            'contacted_student', 'contacted_parent', 'parent_email', 'parent_phone',
            'follow_up_required', 'follow_up_date', 'sent_date'
        ]


# ===== QUIZ FEEDBACK SERIALIZERS =====

class QuizQuestionFeedbackListSerializer(serializers.ModelSerializer):
    """List view of quiz question feedback"""
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    student_name = serializers.CharField(source='quiz_attempt.student.get_full_name', read_only=True)
    quiz_title = serializers.CharField(source='quiz_attempt.quiz.title', read_only=True)
    lesson_title = serializers.SerializerMethodField()
    
    def get_lesson_title(self, obj):
        """Get the first lesson title for the quiz"""
        quiz = obj.quiz_attempt.quiz
        first_lesson = quiz.lessons.first() if quiz else None
        return first_lesson.title if first_lesson else None
    
    class Meta:
        model = QuizQuestionFeedback
        fields = [
            'id', 'teacher_name', 'student_name', 'quiz_title', 'lesson_title',
            'feedback_text', 'points_earned', 'points_possible', 'is_correct',
            'created_at', 'updated_at'
        ]


class QuizQuestionFeedbackDetailSerializer(serializers.ModelSerializer):
    """Detailed view of quiz question feedback"""
    teacher = BasicUserSerializer(read_only=True)
    quiz_attempt = serializers.PrimaryKeyRelatedField(read_only=True)
    question = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = QuizQuestionFeedback
        fields = [
            'id', 'teacher', 'quiz_attempt', 'question', 'feedback_text',
            'points_earned', 'points_possible', 'is_correct',
            'question_text_snapshot', 'student_answer_snapshot', 'correct_answer_snapshot',
            'created_at', 'updated_at'
        ]


class QuizQuestionFeedbackCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update quiz question feedback"""
    
    class Meta:
        model = QuizQuestionFeedback
        fields = [
            'feedback_text', 'points_earned', 'points_possible', 'is_correct'
        ]
    
    def validate_feedback_text(self, value):
        """Ensure feedback text is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Feedback text is required")
        return value.strip()
    
    def validate_points_earned(self, value):
        """Validate points earned is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Points earned cannot be negative")
        return value
    
    def validate_points_possible(self, value):
        """Validate points possible is positive"""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Points possible must be positive")
        return value


class QuizAttemptFeedbackListSerializer(serializers.ModelSerializer):
    """List view of quiz attempt feedback"""
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    student_name = serializers.CharField(source='quiz_attempt.student.get_full_name', read_only=True)
    quiz_title = serializers.CharField(source='quiz_attempt.quiz.title', read_only=True)
    lesson_title = serializers.SerializerMethodField()
    
    def get_lesson_title(self, obj):
        """Get the first lesson title for the quiz"""
        quiz = obj.quiz_attempt.quiz
        first_lesson = quiz.lessons.first() if quiz else None
        return first_lesson.title if first_lesson else None
    
    class Meta:
        model = QuizAttemptFeedback
        fields = [
            'id', 'teacher_name', 'student_name', 'quiz_title', 'lesson_title',
            'feedback_text', 'overall_rating', 'strengths_highlighted',
            'areas_for_improvement', 'study_recommendations', 'created_at', 'updated_at'
        ]


class QuizAttemptFeedbackDetailSerializer(serializers.ModelSerializer):
    """Detailed view of quiz attempt feedback"""
    teacher = BasicUserSerializer(read_only=True)
    quiz_attempt = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = QuizAttemptFeedback
        fields = [
            'id', 'teacher', 'quiz_attempt', 'feedback_text', 'overall_rating',
            'strengths_highlighted', 'areas_for_improvement', 'study_recommendations',
            'private_notes', 'created_at', 'updated_at'
        ]


class QuizAttemptFeedbackCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update quiz attempt feedback"""
    
    class Meta:
        model = QuizAttemptFeedback
        fields = [
            'feedback_text', 'overall_rating', 'strengths_highlighted',
            'areas_for_improvement', 'study_recommendations', 'private_notes'
        ]
    
    def validate_feedback_text(self, value):
        """Ensure feedback text is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Feedback text is required")
        return value.strip()
    
    def validate_overall_rating(self, value):
        """Validate overall rating is a valid choice"""
        valid_ratings = ['excellent', 'good', 'satisfactory', 'needs_improvement', 'poor']
        if value and value not in valid_ratings:
            raise serializers.ValidationError(f"Overall rating must be one of: {', '.join(valid_ratings)}")
        return value


class StudentFeedbackOverviewSerializer(serializers.Serializer):
    """Serializer for student feedback overview"""
    question_feedbacks = QuizQuestionFeedbackListSerializer(many=True, read_only=True)
    attempt_feedbacks = QuizAttemptFeedbackListSerializer(many=True, read_only=True)
    total_feedbacks = serializers.IntegerField(read_only=True)


# ===== SCHEDULE SERIALIZERS =====

class ScheduleEventSerializer(serializers.Serializer):
    """Serializer for individual schedule events"""
    id = serializers.UUIDField()
    title = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    description = serializers.CharField(allow_blank=True)
    event_type = serializers.CharField()
    meeting_platform = serializers.CharField(allow_null=True, allow_blank=True)
    meeting_link = serializers.URLField(allow_null=True, allow_blank=True)
    meeting_id = serializers.CharField(allow_null=True, allow_blank=True)
    meeting_password = serializers.CharField(allow_null=True, allow_blank=True)
    backgroundColor = serializers.CharField()
    borderColor = serializers.CharField()
    textColor = serializers.CharField()


class ClassWithEventsSerializer(serializers.Serializer):
    """Serializer for a class with its events"""
    id = serializers.CharField()
    name = serializers.CharField()
    course_name = serializers.CharField()
    color = serializers.CharField()
    events = ScheduleEventSerializer(many=True)


class StudentScheduleSerializer(serializers.Serializer):
    """Serializer for complete student schedule"""
    classes = ClassWithEventsSerializer(many=True)
    total_events = serializers.IntegerField()
    date_range = serializers.DictField()
    summary = serializers.DictField()


# ===== DASHBOARD OVERVIEW SERIALIZERS =====

class DashboardStatisticsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    courses_enrolled = serializers.IntegerField()
    hours_learned = serializers.FloatField()
    learning_streak = serializers.IntegerField()
    total_courses = serializers.IntegerField()


class AudioVideoLessonSerializer(serializers.Serializer):
    """Serializer for audio/video lessons"""
    id = serializers.UUIDField()  # Changed from IntegerField to UUIDField
    title = serializers.CharField()
    type = serializers.CharField()
    course_title = serializers.CharField()
    course_id = serializers.UUIDField()
    duration = serializers.CharField(allow_null=True, allow_blank=True)
    media_url = serializers.CharField(allow_null=True, allow_blank=True)  # Changed from URLField to CharField
    description = serializers.CharField(allow_null=True, allow_blank=True)
    start_time = serializers.DateTimeField()  # Added for sorting
    progress_percentage = serializers.FloatField()  # Added for real progress display
    total_lessons = serializers.IntegerField()  # Added for progress bar
    completed_lessons_count = serializers.IntegerField()  # Added for progress bar


class LiveLessonSerializer(serializers.Serializer):
    """Serializer for live lessons"""
    id = serializers.UUIDField()
    title = serializers.CharField()
    course_title = serializers.CharField()
    class_name = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    meeting_platform = serializers.CharField(allow_null=True, allow_blank=True)
    meeting_link = serializers.URLField(allow_null=True, allow_blank=True)
    meeting_id = serializers.CharField(allow_null=True, allow_blank=True)
    meeting_password = serializers.CharField(allow_null=True, allow_blank=True)
    description = serializers.CharField(allow_null=True, allow_blank=True)


class TextLessonSerializer(serializers.Serializer):
    """Serializer for text lessons"""
    id = serializers.UUIDField()  # Changed from IntegerField to UUIDField
    title = serializers.CharField()
    course_title = serializers.CharField()
    course_id = serializers.UUIDField()
    description = serializers.CharField(allow_null=True, allow_blank=True)
    media_url = serializers.CharField(allow_null=True, allow_blank=True)  # Added for lesson navigation
    start_time = serializers.DateTimeField()  # Added for sorting
    progress_percentage = serializers.FloatField()  # Added for real progress display
    total_lessons = serializers.IntegerField()  # Added for progress bar
    completed_lessons_count = serializers.IntegerField()  # Added for progress bar


class InteractiveLessonSerializer(serializers.Serializer):
    """Serializer for interactive lessons"""
    id = serializers.UUIDField()  # Changed from IntegerField to UUIDField
    title = serializers.CharField()
    course_title = serializers.CharField()
    course_id = serializers.UUIDField()
    description = serializers.CharField(allow_null=True, allow_blank=True)
    interactive_type = serializers.CharField()
    media_url = serializers.CharField(allow_null=True, allow_blank=True)  # Added for lesson navigation
    start_time = serializers.DateTimeField()  # Added for sorting
    progress_percentage = serializers.FloatField()  # Added for real progress display
    total_lessons = serializers.IntegerField()  # Added for progress bar
    completed_lessons_count = serializers.IntegerField()  # Added for progress bar


class AchievementSerializer(serializers.Serializer):
    """Serializer for achievements"""
    type = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    achieved_at = serializers.DateTimeField()
    course_title = serializers.CharField()
    icon = serializers.CharField()



class DashboardOverviewSerializer(serializers.Serializer):
    """Serializer for complete dashboard overview"""
    statistics = DashboardStatisticsSerializer()
    audio_video_lessons = AudioVideoLessonSerializer(many=True)
    live_lessons = LiveLessonSerializer(many=True)
    text_lessons = TextLessonSerializer(many=True)
    interactive_lessons = InteractiveLessonSerializer(many=True)
    recent_achievements = AchievementSerializer(many=True)


# ===== ASSIGNMENT SUBMISSION SERIALIZERS =====

class AssignmentSubmissionSerializer(serializers.Serializer):
    """Serializer for assignment submission requests"""
    answers = serializers.JSONField(help_text="Student answers for each question")
    is_draft = serializers.BooleanField(default=False, help_text="Whether this is a draft submission")
    submission_type = serializers.ChoiceField(
        choices=['draft', 'completed'],
        default='draft',
        help_text="Type of submission"
    )
    
    def validate_answers(self, value):
        """Validate that answers is a dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Answers must be a dictionary")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        is_draft = data.get('is_draft', False)
        submission_type = data.get('submission_type', 'draft')
        
        # Ensure consistency between is_draft and submission_type
        if is_draft and submission_type != 'draft':
            raise serializers.ValidationError("Draft submissions must have submission_type='draft'")
        elif not is_draft and submission_type != 'completed':
            raise serializers.ValidationError("Final submissions must have submission_type='completed'")
        
        return data


class AssignmentSubmissionResponseSerializer(serializers.ModelSerializer):
    """Serializer for assignment submission responses"""
    
    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'attempt_number', 'status', 'submitted_at', 
            'answers', 'is_graded', 'is_teacher_draft', 'points_earned', 'points_possible', 
            'percentage', 'passed'
        ]
        read_only_fields = fields


# ===== MESSAGING SERIALIZERS =====

class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    sender_id = serializers.UUIDField(source='sender.id', read_only=True)
    sender_name = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender_id', 'sender_name', 'sender_type',
            'content', 'created_at', 'read_at', 'is_read'
        ]
        read_only_fields = ['id', 'sender_id', 'sender_name', 'sender_type', 'created_at', 'read_at', 'is_read']
    
    def get_sender_name(self, obj):
        return obj.sender.get_full_name() or obj.sender.email
    
    def get_sender_type(self, obj):
        return obj.sender.role
    
    def get_is_read(self, obj):
        """
        Check if the current user has read this message.
        - Messages sent by the current user are always considered "read"
        - Otherwise, check if read_by matches the current user
        """
        request = self.context.get('request')
        if not request or not request.user:
            # If no request context, fall back to model's is_read property
            return obj.is_read
        
        current_user = request.user
        
        # Messages you send are always considered "read" for you
        if obj.sender == current_user:
            return True
        
        # Check if this message was read by the current user
        if obj.read_by == current_user:
            return True
        
        # Message is unread for the current user
        return False


class ConversationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing conversations"""
    student_profile_id = serializers.UUIDField(source='student_profile.id', read_only=True)
    student_name = serializers.SerializerMethodField()
    teacher_id = serializers.UUIDField(source='teacher.id', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    course_id = serializers.UUIDField(source='course.id', read_only=True, allow_null=True)
    course_name = serializers.CharField(source='course.title', read_only=True, allow_null=True)
    unread_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'student_profile_id', 'student_name',
            'teacher_id', 'teacher_name', 'recipient_type',
            'course_id', 'course_name', 'subject',
            'last_message_at', 'created_at',
            'unread_count', 'last_message_preview'
        ]
        read_only_fields = fields
    
    def get_student_name(self, obj):
        return f"{obj.student_profile.child_first_name} {obj.student_profile.child_last_name}".strip() or obj.student_profile.user.get_full_name()
    
    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.email
    
    def get_unread_count(self, obj):
        """Count unread messages in this conversation"""
        request = self.context.get('request')
        if not request or not request.user:
            return 0
        
        # Count messages not sent by current user and not read
        return obj.messages.exclude(sender=request.user).filter(read_at__isnull=True).count()
    
    def get_last_message_preview(self, obj):
        """Get preview of last message (first 50 chars)"""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            preview = last_message.content[:50]
            return preview + "..." if len(last_message.content) > 50 else preview
        return ""


class ConversationSerializer(serializers.ModelSerializer):
    """Full serializer for Conversation with related data"""
    student_profile_id = serializers.UUIDField(source='student_profile.id', read_only=True)
    student_name = serializers.SerializerMethodField()
    teacher_id = serializers.UUIDField(source='teacher.id', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    course_id = serializers.UUIDField(source='course.id', read_only=True, allow_null=True)
    course_name = serializers.CharField(source='course.title', read_only=True, allow_null=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'student_profile_id', 'student_name',
            'teacher_id', 'teacher_name', 'recipient_type',
            'course_id', 'course_name', 'subject',
            'created_at', 'updated_at', 'last_message_at'
        ]
        read_only_fields = ['id', 'student_profile_id', 'student_name', 'teacher_id', 'teacher_name', 'course_id', 'course_name', 'created_at', 'updated_at', 'last_message_at']
    
    def get_student_name(self, obj):
        return f"{obj.student_profile.child_first_name} {obj.student_profile.child_last_name}".strip() or obj.student_profile.user.get_full_name()
    
    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.email


class CreateConversationSerializer(serializers.Serializer):
    """Serializer for creating a new conversation"""
    recipient_type = serializers.ChoiceField(
        choices=Conversation.RECIPIENT_TYPE_CHOICES,
        default='parent'
    )
    course_id = serializers.UUIDField(required=False, allow_null=True, help_text="Course ID for course-specific conversations")
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)


class CreateMessageSerializer(serializers.Serializer):
    """Serializer for creating a new message"""
    content = serializers.CharField(
        max_length=5000,
        help_text="Message content (max 5000 characters)"
    )
    
    def validate_content(self, value):
        """Validate message content is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        return value.strip()


# ===== CODE SNIPPET SERIALIZERS =====

class CodeSnippetListSerializer(serializers.ModelSerializer):
    """List view of code snippets"""
    student_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()
    is_teacher_snippet = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CodeSnippet
        fields = [
            'id', 'student_name', 'teacher_name', 'title', 'language', 'code',
            'is_shared', 'share_token', 'share_url', 'is_teacher_snippet',
            'lesson', 'class_instance', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student_name', 'teacher_name', 'share_token', 'share_url', 'is_teacher_snippet', 'created_at', 'updated_at']
    
    def get_student_name(self, obj):
        return obj.student.get_full_name() if obj.student else None
    
    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None
    
    def get_share_url(self, obj):
        """Get shareable URL"""
        request = self.context.get('request')
        base_url = request.build_absolute_uri('/')[:-1] if request else ''
        return obj.get_share_link(base_url)


class CodeSnippetDetailSerializer(serializers.ModelSerializer):
    """Detailed view of code snippet"""
    student = BasicUserSerializer(read_only=True)
    teacher = BasicUserSerializer(read_only=True)
    share_url = serializers.SerializerMethodField()
    is_teacher_snippet = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CodeSnippet
        fields = [
            'id', 'student', 'teacher', 'title', 'code', 'language',
            'is_shared', 'share_token', 'share_url', 'is_teacher_snippet',
            'lesson', 'class_instance', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student', 'teacher', 'share_token', 'share_url', 'is_teacher_snippet', 'created_at', 'updated_at']
    
    def get_share_url(self, obj):
        """Get shareable URL"""
        request = self.context.get('request')
        base_url = request.build_absolute_uri('/')[:-1] if request else ''
        return obj.get_share_link(base_url)


class CodeSnippetCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/Update code snippet"""
    
    class Meta:
        model = CodeSnippet
        fields = [
            'title', 'code', 'language', 'is_shared', 'lesson', 'class_instance'
        ]
    
    def validate_code(self, value):
        """Validate code is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Code cannot be empty")
        return value.strip()
    
    def validate_language(self, value):
        """Validate language is a valid choice"""
        valid_languages = [choice[0] for choice in CodeSnippet.LANGUAGE_CHOICES]
        if value not in valid_languages:
            raise serializers.ValidationError(f"Language must be one of: {', '.join(valid_languages)}")
        return value


class CodeSnippetShareSerializer(serializers.ModelSerializer):
    """Serializer for viewing shared code snippets (public access)"""
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    
    class Meta:
        model = CodeSnippet
        fields = [
            'id', 'student_name', 'title', 'code', 'language',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

