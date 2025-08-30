from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class EnrolledCourse(models.Model):
    """
    Through model for StudentProfile and Course relationship
    Tracks detailed enrollment and progress information
    """
    ENROLLMENT_STATUS = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
        ('paused', 'Paused'),
        ('pending', 'Pending Approval'),
        ('suspended', 'Suspended'),
    ]
    
    PAYMENT_STATUS = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('overdue', 'Overdue'),
        ('scholarship', 'Scholarship'),
        ('free', 'Free'),
    ]
    
    # Basic Relationship
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_profile = models.ForeignKey(
        'users.StudentProfile', 
        on_delete=models.CASCADE,
        related_name='course_enrollments'
    )
    course = models.ForeignKey(
        'courses.Course', 
        on_delete=models.CASCADE,
        related_name='student_enrollments'
    )
    
    # Enrollment Details
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS, default='active')
    enrolled_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='enrolled_students',
        help_text="Teacher or admin who enrolled the student"
    )
    
    # Academic Progress
    progress_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        help_text="Overall course completion percentage"
    )
    current_lesson = models.ForeignKey(
        'courses.Lesson', 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='current_students',
        help_text="Current lesson the student is working on"
    )
    completed_lessons_count = models.PositiveIntegerField(default=0)
    total_lessons_count = models.PositiveIntegerField(default=0)
    
    # Performance Metrics
    overall_grade = models.CharField(
        max_length=2, 
        blank=True,
        help_text="Overall letter grade (A+, B, C, etc.)"
    )
    gpa_points = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="GPA points for this course"
    )
    average_quiz_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    total_assignments_completed = models.PositiveIntegerField(default=0)
    total_assignments_assigned = models.PositiveIntegerField(default=0)
    
    # Engagement Analytics
    total_study_time = models.DurationField(
        default=timezone.timedelta,
        help_text="Total time spent studying this course"
    )
    last_accessed = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Last time student accessed the course"
    )
    login_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times student logged into this course"
    )
    total_video_watch_time = models.DurationField(
        default=timezone.timedelta,
        help_text="Total video content watched"
    )
    
    # Financial Information
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Amount paid for this course"
    )
    payment_due_date = models.DateField(null=True, blank=True)
    discount_applied = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        help_text="Discount percentage applied"
    )
    
    # Completion & Certification
    completion_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date when course was completed"
    )
    certificate_issued = models.BooleanField(
        default=False,
        help_text="Whether completion certificate was issued"
    )
    certificate_url = models.URLField(
        blank=True,
        help_text="URL to download the certificate"
    )
    final_grade_issued = models.BooleanField(default=False)
    
    # Communication & Support
    parent_notifications_enabled = models.BooleanField(
        default=True,
        help_text="Send progress notifications to parents"
    )
    reminder_emails_enabled = models.BooleanField(
        default=True,
        help_text="Send reminder emails for assignments/classes"
    )
    special_accommodations = models.TextField(
        blank=True,
        help_text="Special learning accommodations for this student"
    )
    
    # Assessment Metrics
    lesson_assessments_count = models.PositiveIntegerField(default=0)
    teacher_assessments_count = models.PositiveIntegerField(default=0)
    last_assessment_date = models.DateTimeField(null=True, blank=True)
    
    # Enhanced Quiz Metrics
    total_quizzes_taken = models.PositiveIntegerField(default=0)
    total_quizzes_passed = models.PositiveIntegerField(default=0)
    highest_quiz_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    lowest_quiz_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Tracking & Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_progress_update = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'enrolled_courses'
        unique_together = ['student_profile', 'course']
        ordering = ['-enrollment_date']
        indexes = [
            models.Index(fields=['student_profile', 'status']),
            models.Index(fields=['course', 'status']),
            models.Index(fields=['enrollment_date']),
            models.Index(fields=['last_accessed']),
        ]
    
    def __str__(self):
        return f"{self.student_profile.user.get_full_name()} enrolled in {self.course.title}"
    
    def update_quiz_metrics(self, quiz_score, passed):
        """Update quiz-related metrics when a quiz is completed"""
        self.total_quizzes_taken += 1
        if passed:
            self.total_quizzes_passed += 1
        
        # Update average score
        if self.average_quiz_score is None:
            self.average_quiz_score = quiz_score
        else:
            total_score = self.average_quiz_score * (self.total_quizzes_taken - 1) + quiz_score
            self.average_quiz_score = total_score / self.total_quizzes_taken
        
        # Update highest/lowest scores
        if quiz_score > self.highest_quiz_score:
            self.highest_quiz_score = quiz_score
        if quiz_score < self.lowest_quiz_score or self.lowest_quiz_score == 0:
            self.lowest_quiz_score = quiz_score
        
        self.save()
    
    def update_assessment_metrics(self, assessment_type):
        """Update assessment counts when an assessment is added"""
        if assessment_type == 'lesson':
            self.lesson_assessments_count += 1
        elif assessment_type == 'teacher':
            self.teacher_assessments_count += 1
        
        self.last_assessment_date = timezone.now()
        self.save()
    
    def update_progress_metrics(self):
        """Update overall progress metrics"""
        # Calculate completion percentage
        if self.total_lessons_count > 0:
            self.progress_percentage = (self.completed_lessons_count / self.total_lessons_count) * 100
        
        # Update current lesson if needed
        if not self.current_lesson and self.completed_lessons_count < self.total_lessons_count:
            # Find next uncompleted lesson
            next_lesson = self.course.lessons.filter(
                order__gt=self.completed_lessons_count
            ).first()
            if next_lesson:
                self.current_lesson = next_lesson
        
        self.save()
    
    @property
    def is_active(self):
        """Check if enrollment is currently active"""
        return self.status == 'active'
    
    @property
    def is_completed(self):
        """Check if course is completed"""
        return self.status == 'completed' or self.progress_percentage >= 100
    
    @property
    def days_since_enrollment(self):
        """Calculate days since enrollment"""
        return (timezone.now().date() - self.enrollment_date).days
    
    @property
    def days_since_last_access(self):
        """Calculate days since last access"""
        if not self.last_accessed:
            return None
        return (timezone.now().date() - self.last_accessed.date()).days
    
    @property
    def completion_rate(self):
        """Calculate lesson completion rate"""
        if self.total_lessons_count == 0:
            return 0
        return (self.completed_lessons_count / self.total_lessons_count) * 100
    
    @property
    def assignment_completion_rate(self):
        """Calculate assignment completion rate"""
        if self.total_assignments_assigned == 0:
            return 0
        return (self.total_assignments_completed / self.total_assignments_assigned) * 100
    
    @property
    def is_at_risk(self):
        """Determine if student is at risk based on engagement metrics"""
        if self.days_since_last_access and self.days_since_last_access > 7:
            return True
        if self.progress_percentage < 50 and self.days_since_enrollment > 30:
            return True
        if self.assignment_completion_rate < 60:
            return True
        return False
    
    def update_progress(self):
        """Update progress metrics based on completed lessons and assignments"""
        from courses.models import Lesson, QuizAttempt
        
        # Update lesson progress
        total_lessons = Lesson.objects.filter(course=self.course).count()
        # This would need to be implemented based on your lesson progress tracking
        # completed_lessons = ... (based on your LessonProgress model)
        
        self.total_lessons_count = total_lessons
        # self.completed_lessons_count = completed_lessons
        
        if total_lessons > 0:
            self.progress_percentage = (self.completed_lessons_count / total_lessons) * 100
        
        # Update quiz average
        quiz_attempts = QuizAttempt.objects.filter(
            student=self.student_profile.user,
            quiz__lesson__course=self.course
        )
        if quiz_attempts.exists():
            self.average_quiz_score = quiz_attempts.aggregate(
                avg_score=models.Avg('score')
            )['avg_score']
        
        self.last_progress_update = timezone.now()
        self.save()
    
    def mark_completed(self):
        """Mark the course as completed"""
        self.status = 'completed'
        self.completion_date = timezone.now().date()
        self.progress_percentage = 100
        self.save()
    
    def issue_certificate(self, certificate_url=None):
        """Issue completion certificate"""
        if self.is_completed:
            self.certificate_issued = True
            if certificate_url:
                self.certificate_url = certificate_url
            self.save()
            return True
        return False


class StudentAttendance(models.Model):
    """
    Track student attendance for classes
    """
    ATTENDANCE_STATUS = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='attendance_records',
        limit_choices_to={'role': 'student'}
    )
    class_session = models.ForeignKey(
        'courses.Class', 
        on_delete=models.CASCADE, 
        related_name='attendance_records'
    )
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='present')
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Additional notes about attendance")
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    recorded_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='recorded_attendance',
        limit_choices_to={'role': 'teacher'}
    )
    
    class Meta:
        db_table = 'student_attendance'
        unique_together = ['student', 'class_session', 'date']
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.class_session.name} - {self.date} ({self.status})"


class StudentGrade(models.Model):
    """
    Track student grades and assessments
    """
    GRADE_TYPES = [
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
        ('project', 'Project'),
        ('exam', 'Exam'),
        ('participation', 'Participation'),
        ('homework', 'Homework'),
    ]
    
    LETTER_GRADES = [
        ('A+', 'A+ (97-100)'),
        ('A', 'A (93-96)'),
        ('A-', 'A- (90-92)'),
        ('B+', 'B+ (87-89)'),
        ('B', 'B (83-86)'),
        ('B-', 'B- (80-82)'),
        ('C+', 'C+ (77-79)'),
        ('C', 'C (73-76)'),
        ('C-', 'C- (70-72)'),
        ('D+', 'D+ (67-69)'),
        ('D', 'D (63-66)'),
        ('D-', 'D- (60-62)'),
        ('F', 'F (0-59)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='grades',
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='student_grades')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, null=True, blank=True)
    quiz_attempt = models.ForeignKey('courses.QuizAttempt', on_delete=models.CASCADE, null=True, blank=True)
    
    # Grade Information
    grade_type = models.CharField(max_length=20, choices=GRADE_TYPES)
    title = models.CharField(max_length=200, help_text="Title of the assessment")
    description = models.TextField(blank=True)
    
    # Scoring
    points_earned = models.DecimalField(max_digits=6, decimal_places=2)
    points_possible = models.DecimalField(max_digits=6, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Calculated percentage")
    letter_grade = models.CharField(max_length=2, choices=LETTER_GRADES, blank=True)
    
    # Feedback
    teacher_comments = models.TextField(blank=True)
    private_notes = models.TextField(blank=True, help_text="Private notes for teacher only")
    
    # Question-level grading
    graded_questions = models.JSONField(
        default=list,
        help_text="Individual question grades and feedback - list of {question_id, is_correct, teacher_feedback, points_earned, points_possible}"
    )
    
    # Dates
    assigned_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    submitted_date = models.DateTimeField(null=True, blank=True)
    graded_date = models.DateTimeField(auto_now_add=True)
    
    # Tracking
    graded_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='graded_assessments',
        limit_choices_to={'role': 'teacher'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_grades'
        ordering = ['-graded_date']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.title} - {self.letter_grade or self.percentage}%"
    
    def save(self, *args, **kwargs):
        # Auto-calculate percentage
        if self.points_possible > 0:
            self.percentage = (self.points_earned / self.points_possible) * 100
        
        # Auto-assign letter grade based on percentage
        if self.percentage >= 97:
            self.letter_grade = 'A+'
        elif self.percentage >= 93:
            self.letter_grade = 'A'
        elif self.percentage >= 90:
            self.letter_grade = 'A-'
        elif self.percentage >= 87:
            self.letter_grade = 'B+'
        elif self.percentage >= 83:
            self.letter_grade = 'B'
        elif self.percentage >= 80:
            self.letter_grade = 'B-'
        elif self.percentage >= 77:
            self.letter_grade = 'C+'
        elif self.percentage >= 73:
            self.letter_grade = 'C'
        elif self.percentage >= 70:
            self.letter_grade = 'C-'
        elif self.percentage >= 67:
            self.letter_grade = 'D+'
        elif self.percentage >= 63:
            self.letter_grade = 'D'
        elif self.percentage >= 60:
            self.letter_grade = 'D-'
        else:
            self.letter_grade = 'F'
        
        super().save(*args, **kwargs)


class StudentBehavior(models.Model):
    """
    Track student behavior incidents and positive reinforcements
    """
    BEHAVIOR_TYPES = [
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
    ]
    
    BEHAVIOR_CATEGORIES = [
        ('participation', 'Class Participation'),
        ('homework', 'Homework Completion'),
        ('respect', 'Respectful Behavior'),
        ('helping', 'Helping Others'),
        ('leadership', 'Leadership'),
        ('creativity', 'Creativity'),
        ('disruption', 'Class Disruption'),
        ('tardiness', 'Tardiness'),
        ('incomplete_work', 'Incomplete Work'),
        ('disrespect', 'Disrespectful Behavior'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='behavior_records',
        limit_choices_to={'role': 'student'}
    )
    class_session = models.ForeignKey(
        'courses.Class', 
        on_delete=models.CASCADE, 
        related_name='behavior_records'
    )
    
    # Behavior Details
    behavior_type = models.CharField(max_length=20, choices=BEHAVIOR_TYPES)
    category = models.CharField(max_length=20, choices=BEHAVIOR_CATEGORIES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.IntegerField(
        choices=[(1, 'Minor'), (2, 'Moderate'), (3, 'Major')],
        default=1,
        help_text="1=Minor, 2=Moderate, 3=Major"
    )
    
    # Actions Taken
    action_taken = models.TextField(blank=True, help_text="What action was taken")
    parent_contacted = models.BooleanField(default=False)
    parent_contact_date = models.DateTimeField(null=True, blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    
    # Tracking
    incident_date = models.DateField(default=timezone.now)
    reported_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reported_behaviors',
        limit_choices_to={'role': 'teacher'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_behavior'
        ordering = ['-incident_date', '-created_at']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.title} ({self.behavior_type})"


class StudentNote(models.Model):
    """
    Private notes about students for teachers
    """
    NOTE_CATEGORIES = [
        ('academic', 'Academic'),
        ('behavioral', 'Behavioral'),
        ('personal', 'Personal'),
        ('parent_communication', 'Parent Communication'),
        ('medical', 'Medical/Health'),
        ('general', 'General'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='teacher_notes',
        limit_choices_to={'role': 'student'}
    )
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='student_notes',
        limit_choices_to={'role': 'teacher'}
    )
    
    # Note Details
    category = models.CharField(max_length=20, choices=NOTE_CATEGORIES, default='general')
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_private = models.BooleanField(default=True, help_text="Private notes only visible to teacher")
    is_important = models.BooleanField(default=False, help_text="Mark as important for quick reference")
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_notes'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Note about {self.student.get_full_name()} - {self.title}"


class StudentCommunication(models.Model):
    """
    Track communication with students and parents
    """
    COMMUNICATION_TYPES = [
        ('email', 'Email'),
        ('phone', 'Phone Call'),
        ('meeting', 'In-Person Meeting'),
        ('message', 'Platform Message'),
        ('letter', 'Written Letter'),
    ]
    
    COMMUNICATION_PURPOSES = [
        ('progress_update', 'Progress Update'),
        ('behavior_concern', 'Behavior Concern'),
        ('academic_concern', 'Academic Concern'),
        ('positive_feedback', 'Positive Feedback'),
        ('schedule_change', 'Schedule Change'),
        ('general_inquiry', 'General Inquiry'),
        ('parent_request', 'Parent Request'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='communications',
        limit_choices_to={'role': 'student'}
    )
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='student_communications',
        limit_choices_to={'role': 'teacher'}
    )
    
    # Communication Details
    communication_type = models.CharField(max_length=20, choices=COMMUNICATION_TYPES)
    purpose = models.CharField(max_length=20, choices=COMMUNICATION_PURPOSES)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Recipients
    contacted_student = models.BooleanField(default=False)
    contacted_parent = models.BooleanField(default=False)
    parent_email = models.EmailField(blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    
    # Response
    response_received = models.BooleanField(default=False)
    response_date = models.DateTimeField(null=True, blank=True)
    response_content = models.TextField(blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_completed = models.BooleanField(default=False)
    
    # Tracking
    sent_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_communications'
        ordering = ['-sent_date']
    
    def __str__(self):
        return f"Communication with {self.student.get_full_name()} - {self.subject}"


class LessonAssessment(models.Model):
    """
    Teacher's assessment for a student on a specific lesson within a course enrollment
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    enrollment = models.ForeignKey(
        EnrolledCourse, 
        on_delete=models.CASCADE, 
        related_name='lesson_assessments'
    )
    lesson = models.ForeignKey(
        'courses.Lesson', 
        on_delete=models.CASCADE, 
        related_name='student_assessments'
    )
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='lesson_assessments_given'
    )
    
    # Assessment content
    title = models.CharField(max_length=200)
    content = models.TextField()
    assessment_type = models.CharField(max_length=50, choices=[
        ('strength', 'Strength'),
        ('weakness', 'Weakness'),
        ('improvement', 'Improvement Area'),
        ('general', 'General Note'),
        ('achievement', 'Achievement'),
        ('challenge', 'Challenge Faced')
    ])
    
    # Optional: Link to quiz attempt if assessment was added during grading
    quiz_attempt = models.ForeignKey(
        'courses.QuizAttempt', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lesson_assessments'
        unique_together = ['enrollment', 'lesson', 'teacher']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['enrollment', 'lesson']),
            models.Index(fields=['teacher', '-created_at']),
            models.Index(fields=['assessment_type']),
        ]
    
    def __str__(self):
        return f"{self.teacher.get_full_name()}'s {self.assessment_type} assessment for {self.enrollment.student_profile.user.get_full_name()} on {self.lesson.title}"


class TeacherAssessment(models.Model):
    """
    Overall teacher evaluation of student performance in a specific course
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    enrollment = models.ForeignKey(
        EnrolledCourse, 
        on_delete=models.CASCADE, 
        related_name='teacher_assessments'
    )
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='teacher_assessments_given'
    )
    
    # Overall evaluation
    academic_performance = models.CharField(max_length=20, choices=[
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('satisfactory', 'Satisfactory'),
        ('needs_improvement', 'Needs Improvement'),
        ('poor', 'Poor')
    ])
    
    participation_level = models.CharField(max_length=20, choices=[
        ('very_active', 'Very Active'),
        ('active', 'Active'),
        ('moderate', 'Moderate'),
        ('passive', 'Passive'),
        ('inactive', 'Inactive')
    ])
    
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    general_comments = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teacher_assessments'
        # Removed unique_together to allow weekly assessments
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['enrollment', 'teacher']),
            models.Index(fields=['teacher', '-created_at']),
            models.Index(fields=['academic_performance']),
        ]
    
    def __str__(self):
        return f"{self.teacher.get_full_name()}'s assessment for {self.enrollment.student_profile.user.get_full_name()} in {self.enrollment.course.title}"


class BaseFeedback(models.Model):
    """
    Abstract base model for all feedback types
    Provides common fields and behavior
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Common feedback fields
    feedback_text = models.TextField(help_text="The actual feedback content")
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='%(class)s_feedbacks_given'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.teacher.get_full_name()}'s feedback - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class QuizQuestionFeedback(BaseFeedback):
    """
    Feedback for individual quiz questions
    Links directly to quiz attempts and questions
    """
    quiz_attempt = models.ForeignKey(
        'courses.QuizAttempt', 
        on_delete=models.CASCADE, 
        related_name='question_feedbacks'
    )
    question = models.ForeignKey(
        'courses.Question', 
        on_delete=models.CASCADE, 
        related_name='feedbacks'
    )
    
    # Question-specific feedback fields
    points_earned = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Points earned for this specific question"
    )
    points_possible = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Total points possible for this question"
    )
    is_correct = models.BooleanField(
        null=True, 
        blank=True,
        help_text="Whether the student's answer was correct"
    )
    
    # Snapshot data for reference (in case question/answer changes later)
    question_text_snapshot = models.TextField(
        blank=True,
        help_text="Snapshot of question text when feedback was given"
    )
    student_answer_snapshot = models.TextField(
        blank=True,
        help_text="Snapshot of student's answer when feedback was given"
    )
    correct_answer_snapshot = models.TextField(
        blank=True,
        help_text="Snapshot of correct answer when feedback was given"
    )
    
    class Meta:
        db_table = 'quiz_question_feedbacks'
        unique_together = ['quiz_attempt', 'question', 'teacher']
        indexes = [
            models.Index(fields=['quiz_attempt', 'question']),
            models.Index(fields=['teacher', '-created_at']),
            models.Index(fields=['is_correct']),
        ]
    
    def __str__(self):
        return f"{self.teacher.get_full_name()}'s feedback on question {self.question.id} for {self.quiz_attempt.student.get_full_name()}"
    
    def save(self, *args, **kwargs):
        # Auto-capture snapshots if not provided
        if not self.question_text_snapshot and self.question:
            self.question_text_snapshot = self.question.question_text
        if not self.student_answer_snapshot and self.quiz_attempt:
            student_answer = self.quiz_attempt.answers.get(str(self.question.id), '')
            self.student_answer_snapshot = str(student_answer)
        if not self.correct_answer_snapshot and self.question:
            correct_answer = self.question.content.get('correct_answer', '')
            self.correct_answer_snapshot = str(correct_answer)
        
        super().save(*args, **kwargs)


class QuizAttemptFeedback(BaseFeedback):
    """
    Overall feedback for an entire quiz attempt
    Provides comprehensive feedback on student performance
    """
    quiz_attempt = models.ForeignKey(
        'courses.QuizAttempt', 
        on_delete=models.CASCADE, 
        related_name='attempt_feedbacks'
    )
    
    # Overall assessment feedback
    overall_rating = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('satisfactory', 'Satisfactory'),
            ('needs_improvement', 'Needs Improvement'),
            ('poor', 'Poor'),
        ],
        null=True,
        blank=True,
        help_text="Overall rating of the quiz attempt"
    )
    
    # Detailed feedback sections
    strengths_highlighted = models.TextField(
        blank=True,
        help_text="Student strengths demonstrated in this quiz"
    )
    areas_for_improvement = models.TextField(
        blank=True,
        help_text="Specific areas where the student can improve"
    )
    study_recommendations = models.TextField(
        blank=True,
        help_text="Recommended study strategies or resources"
    )
    
    # Private notes (not visible to students)
    private_notes = models.TextField(
        blank=True,
        help_text="Private notes for teachers (not visible to students)"
    )
    
    class Meta:
        db_table = 'quiz_attempt_feedbacks'
        unique_together = ['quiz_attempt', 'teacher']
        indexes = [
            models.Index(fields=['quiz_attempt']),
            models.Index(fields=['teacher', '-created_at']),
            models.Index(fields=['overall_rating']),
        ]
    
    def __str__(self):
        return f"{self.teacher.get_full_name()}'s overall feedback for {self.quiz_attempt.student.get_full_name()}'s quiz attempt"
    
    @property
    def has_detailed_feedback(self):
        """Check if this feedback has detailed sections filled out"""
        return bool(
            self.strengths_highlighted or 
            self.areas_for_improvement or 
            self.study_recommendations
        )


