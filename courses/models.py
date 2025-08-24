from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

User = get_user_model()


class Course(models.Model):
    """
    Course model representing a complete learning course
    """
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="Course title")
    description = models.TextField(help_text="Short course description")
    long_description = models.TextField(help_text="Detailed course description")
    
    # Teacher & Management
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_courses',
        limit_choices_to={'role': 'teacher'}
    )
    category = models.CharField(max_length=100, help_text="Course category")
    
    # Course Details (matching frontend structure)
    age_range = models.CharField(max_length=50, help_text="Target age range (e.g., 'Ages 6-10')")
    duration = models.CharField(max_length=50, help_text="Course duration (e.g., '8 weeks')")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    
    # Pricing & Features
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        help_text="Course price in USD"
    )
    features = models.JSONField(
        default=list, 
        help_text="List of course features/highlights"
    )
    
    # Display & Marketing
    featured = models.BooleanField(
        default=False, 
        help_text="Show on home page as featured course"
    )
    popular = models.BooleanField(
        default=False, 
        help_text="Mark as 'Most Popular' course"
    )
    color = models.CharField(
        max_length=100, 
        default="bg-gradient-primary",
        help_text="CSS class for course color/gradient"
    )
    icon = models.CharField(
        max_length=50, 
        default="Code",
        help_text="Lucide icon name for course"
    )
    
    # Course Management
    max_students = models.IntegerField(
        default=8, 
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Maximum number of students per class"
    )
    schedule = models.CharField(
        max_length=100, 
        default="2 sessions per week",
        help_text="Class schedule description"
    )
    certificate = models.BooleanField(
        default=True, 
        help_text="Award certificate upon completion"
    )
    
    # Prerequisites
    prerequisites = models.ManyToManyField(
        'self', 
        blank=True, 
        symmetrical=False,
        help_text="Required courses before taking this course"
    )
    
    # Status & Metadata
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Computed fields
    @property
    def total_lessons(self):
        return self.lessons.count()
    
    @property
    def total_duration_minutes(self):
        return sum(lesson.duration for lesson in self.lessons.all())
    
    @property
    def enrolled_students_count(self):
        return self.enrollments.count()
    
    @property
    def is_featured_eligible(self):
        return (
            self.status == 'published' and 
            self.featured == True
        )
    
    # Student Relationships (using through model)
    enrolled_students = models.ManyToManyField(
        'users.StudentProfile',
        through='student.EnrolledCourse',
        related_name='enrolled_courses',
        blank=True,
        help_text="Students enrolled in this course"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'featured']),
            models.Index(fields=['teacher', 'status']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.title} by {self.teacher.get_full_name()}"


class Lesson(models.Model):
    """
    Individual lesson within a course
    """
    LESSON_TYPES = [
        ('live_class', 'Live Class'),
        ('video_audio', 'Video/Audio Lesson'),
        ('text_lesson', 'Text Lesson'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    order = models.IntegerField(help_text="Lesson sequence within the course")
    duration = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Lesson duration in minutes"
    )
    
    # Lesson Type & Content
    type = models.CharField(max_length=20, choices=LESSON_TYPES)
    
    # Content fields based on lesson type
    text_content = models.TextField(
        blank=True, 
        null=True,
        help_text="Rich text content for text lessons"
    )
    
    video_url = models.URLField(
        blank=True, 
        null=True,
        help_text="Video URL for video/audio lessons"
    )
    
    audio_url = models.URLField(
        blank=True, 
        null=True,
        help_text="Audio URL for video/audio lessons"
    )
    
    live_class_date = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="Scheduled date for live class"
    )
    

    
    live_class_status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('ongoing', 'Ongoing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        default='scheduled',
        help_text="Current status of live class"
    )
    
    content = models.JSONField(
        default=dict, 
        help_text="Additional type-specific lesson content and configuration"
    )
    
    # Prerequisites & Dependencies
    prerequisites = models.ManyToManyField(
        'self', 
        blank=True, 
        symmetrical=False,
        help_text="Lessons that must be completed before this one"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['course', 'order']
        unique_together = ['course', 'order']
        indexes = [
            models.Index(fields=['course', 'order']),
            models.Index(fields=['type']),
        ]
    
    def __str__(self):
        return f"{self.course.title} - Lesson {self.order}: {self.title}"


class Quiz(models.Model):
    """
    Quiz associated with a lesson
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Quiz Configuration
    time_limit = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Time limit in minutes (null = no limit)"
    )
    passing_score = models.IntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum percentage to pass"
    )
    max_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of attempts allowed"
    )
    show_correct_answers = models.BooleanField(
        default=True,
        help_text="Show correct answers after completion"
    )
    randomize_questions = models.BooleanField(
        default=False,
        help_text="Randomize question order for each attempt"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def total_points(self):
        return sum(question.points for question in self.questions.all())
    
    @property
    def question_count(self):
        return self.questions.count()
    
    class Meta:
        ordering = ['lesson__course', 'lesson__order']
    
    def __str__(self):
        return f"Quiz: {self.title} ({self.lesson.course.title})"


class Question(models.Model):
    """
    Individual question within a quiz
    """
    QUESTION_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('fill_blank', 'Fill in the Blank'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
        ('matching', 'Matching'),
        ('ordering', 'Ordering/Ranking'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField(help_text="The question text")
    order = models.IntegerField(help_text="Question order within the quiz")
    points = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Points awarded for correct answer"
    )
    
    # Question Type & Content
    type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    content = models.JSONField(
        default=dict,
        help_text="Question-specific content (options, answers, etc.)"
    )
    
    # Optional fields
    explanation = models.TextField(
        blank=True,
        help_text="Explanation shown after answering"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['quiz', 'order']
        unique_together = ['quiz', 'order']
        indexes = [
            models.Index(fields=['quiz', 'order']),
            models.Index(fields=['type']),
        ]
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."


class CourseEnrollment(models.Model):
    """
    Student enrollment in a course
    """
    ENROLLMENT_STATUS = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
        ('paused', 'Paused'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='course_enrollments',
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    
    # Enrollment Details
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS, default='active')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(default=timezone.now)
    
    # Progress Tracking
    current_lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Current lesson the student is on"
    )
    
    @property
    def progress_percentage(self):
        if not self.course.total_lessons:
            return 0
        completed_lessons = self.lesson_progress.filter(status='completed').count()
        return round((completed_lessons / self.course.total_lessons) * 100)
    
    @property
    def completed_lessons_count(self):
        return self.lesson_progress.filter(status='completed').count()
    
    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.course.title}"


class LessonProgress(models.Model):
    """
    Student progress on individual lessons
    """
    LESSON_STATUS = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('locked', 'Locked'),
    ]
    
    # Basic Information
    enrollment = models.ForeignKey(
        CourseEnrollment, 
        on_delete=models.CASCADE, 
        related_name='lesson_progress'
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    
    # Progress Details
    status = models.CharField(max_length=20, choices=LESSON_STATUS, default='not_started')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent = models.IntegerField(default=0, help_text="Time spent in minutes")
    
    # Content-specific progress (e.g., video progress, reading progress)
    progress_data = models.JSONField(
        default=dict,
        help_text="Lesson-specific progress data"
    )
    
    class Meta:
        unique_together = ['enrollment', 'lesson']
        indexes = [
            models.Index(fields=['enrollment', 'status']),
            models.Index(fields=['lesson', 'status']),
        ]
    
    def __str__(self):
        return f"{self.enrollment.student.get_full_name()} - {self.lesson.title} ({self.status})"


class QuizAttempt(models.Model):
    """
    Student attempts at quizzes
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    enrollment = models.ForeignKey(CourseEnrollment, on_delete=models.CASCADE)
    
    # Attempt Details
    attempt_number = models.IntegerField(validators=[MinValueValidator(1)])
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Score as percentage"
    )
    points_earned = models.IntegerField(default=0)
    passed = models.BooleanField(default=False)
    
    # Attempt Data
    answers = models.JSONField(
        default=dict,
        help_text="Student answers for each question"
    )
    
    class Meta:
        unique_together = ['student', 'quiz', 'attempt_number']
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'quiz']),
            models.Index(fields=['enrollment', 'completed_at']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.quiz.title} (Attempt {self.attempt_number})"


class Note(models.Model):
    """
    Note model for teachers to take personal notes about courses and lessons
    """
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('lesson', 'Lesson Specific'),
        ('idea', 'Idea'),
        ('reminder', 'Reminder'),
        ('issue', 'Issue'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="Note title")
    content = models.TextField(help_text="Note content")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general',
        help_text="Note category"
    )
    
    # Relationships
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='notes',
        help_text="Course this note belongs to"
    )
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='course_notes',
        help_text="Teacher who created this note"
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='notes',
        null=True,
        blank=True,
        help_text="Optional lesson this note is linked to"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at', '-created_at']
        indexes = [
            models.Index(fields=['course', 'teacher']),
            models.Index(fields=['lesson', 'category']),
            models.Index(fields=['-updated_at']),
        ]
    
    def __str__(self):
        lesson_info = f" - {self.lesson.title}" if self.lesson else ""
        return f"{self.title} ({self.get_category_display()}){lesson_info}"


class CourseIntroduction(models.Model):
    """
    Detailed course introduction information including student reviews
    """
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='introduction')
    
    # Course Overview
    overview = models.TextField(help_text="Detailed course description")
    learning_objectives = models.JSONField(default=list, help_text="List of learning objectives")
    prerequisites = models.TextField(blank=True, help_text="What students should know before starting")
    
    # Course Details
    duration_weeks = models.PositiveIntegerField(default=8, help_text="Course duration in weeks")
    max_students = models.PositiveIntegerField(default=12, help_text="Maximum number of students")
    sessions_per_week = models.PositiveIntegerField(default=2, help_text="Number of sessions per week")
    total_projects = models.PositiveIntegerField(default=5, help_text="Number of projects students will create")
    
    # Value Propositions
    value_propositions = models.JSONField(default=list, help_text="List of course benefits")
    
    # Student Reviews
    reviews = models.JSONField(default=list, help_text="Student reviews and ratings")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Course Introduction"
        verbose_name_plural = "Course Introductions"
    
    def __str__(self):
        return f"Introduction for {self.course.title}"
    
    def get_average_rating(self):
        """Calculate average rating from reviews"""
        if not self.reviews:
            return 0
        total_rating = sum(review.get('rating', 0) for review in self.reviews)
        return round(total_rating / len(self.reviews), 1)
    
    def get_review_count(self):
        """Get total number of reviews"""
        return len(self.reviews) if self.reviews else 0


class Class(models.Model):
    """
    A class is a specific instance of a course with assigned students
    Teachers can create multiple classes for the same course to manage capacity
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Name of the class (e.g., 'Morning Group A')")
    description = models.TextField(blank=True, help_text="Brief description of the class")
    
    # Relationships
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='classes',
        help_text="The course this class is based on"
    )
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='taught_classes',
        limit_choices_to={'role': 'teacher'},
        help_text="Teacher managing this class"
    )
    students = models.ManyToManyField(
        User,
        related_name='enrolled_classes',
        limit_choices_to={'role': 'student'},
        blank=True,
        help_text="Students enrolled in this class"
    )
    
    # Class Configuration
    max_capacity = models.PositiveIntegerField(
        default=10, 
        help_text="Maximum number of students allowed in this class"
    )
    schedule = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Class schedule (e.g., 'Mon/Wed 9:00 AM')"
    )
    meeting_link = models.URLField(
        blank=True,
        help_text="Online meeting link for virtual classes"
    )
    
    # Status and Metadata
    is_active = models.BooleanField(default=True, help_text="Whether the class is currently active")
    start_date = models.DateField(null=True, blank=True, help_text="Class start date")
    end_date = models.DateField(null=True, blank=True, help_text="Class end date")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'classes'
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        ordering = ['course__title', 'name']
    
    def __str__(self):
        return f"{self.course.title} - {self.name}"
    
    @property
    def student_count(self):
        """Get current number of enrolled students"""
        return self.students.count()
    
    @property
    def is_full(self):
        """Check if class has reached maximum capacity"""
        return self.student_count >= self.max_capacity
    
    @property
    def available_spots(self):
        """Get number of available spots in the class"""
        return max(0, self.max_capacity - self.student_count)
    
    def can_enroll_student(self, student):
        """Check if a student can be enrolled in this class"""
        if self.is_full:
            return False, "Class is at maximum capacity"
        
        if student in self.students.all():
            return False, "Student is already enrolled in this class"
        
        # Check if student is enrolled in the course
        try:
            enrollment = CourseEnrollment.objects.get(
                student=student, 
                course=self.course,
                status='active'
            )
            return True, "Student can be enrolled"
        except CourseEnrollment.DoesNotExist:
            return False, "Student must be enrolled in the course first"
    
    def enroll_student(self, student):
        """Enroll a student in this class"""
        can_enroll, message = self.can_enroll_student(student)
        if can_enroll:
            self.students.add(student)
            return True, f"Student {student.get_full_name()} enrolled successfully"
        return False, message
    
    def remove_student(self, student):
        """Remove a student from this class"""
        if student in self.students.all():
            self.students.remove(student)
            return True, f"Student {student.get_full_name()} removed successfully"
        return False, "Student is not enrolled in this class"


class ClassEvent(models.Model):
    """
    Individual events/sessions scheduled for a class
    """
    EVENT_TYPES = [
        ('lesson', 'Lesson'),
        ('meeting', 'Meeting'),
        ('break', 'Break'),
    ]
    
    MEETING_PLATFORMS = [
        ('google-meet', 'Google Meet'),
        ('zoom', 'Zoom'),
        ('other', 'Other'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="Event title")
    description = models.TextField(blank=True, help_text="Event description")
    
    # Relationships
    class_instance = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='events',
        help_text="The class this event belongs to"
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Associated lesson (if event type is lesson)"
    )
    
    # Event Details
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        default='lesson',
        help_text="Type of event"
    )
    start_time = models.DateTimeField(help_text="Event start time")
    end_time = models.DateTimeField(help_text="Event end time")
    
    # Meeting Details (for live classes)
    meeting_platform = models.CharField(
        max_length=20,
        choices=MEETING_PLATFORMS,
        blank=True,
        null=True,
        help_text="Platform for live class meetings"
    )
    meeting_link = models.URLField(
        blank=True,
        help_text="Meeting link for live classes (Google Meet, Zoom, etc.)"
    )
    meeting_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Meeting ID or room number"
    )
    meeting_password = models.CharField(
        max_length=50,
        blank=True,
        help_text="Meeting password if required"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'class_events'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['class_instance', 'start_time']),
            models.Index(fields=['event_type']),
            models.Index(fields=['start_time']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.class_instance.name} ({self.start_time.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def duration_minutes(self):
        """Calculate event duration in minutes"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0
    
    def clean(self):
        """Validate event data"""
        from django.core.exceptions import ValidationError
        
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError("End time must be after start time")
        
        if self.event_type == 'lesson' and not self.lesson:
            raise ValidationError("Lesson events must have an associated lesson")
        
        # Validate meeting details for live classes
        if self.event_type == 'lesson' and self.lesson and self.lesson.type == 'live_class':
            if self.meeting_link and not self.meeting_platform:
                raise ValidationError("Meeting platform is required when meeting link is provided")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class CourseIntroduction(models.Model):
    """
    Extended course introduction and marketing information
    """
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name='introduction'
    )
    
    # Course Overview
    overview = models.TextField(help_text="Detailed course description")
    learning_objectives = models.JSONField(
        default=list,
        help_text="List of learning objectives"
    )
    prerequisites = models.TextField(
        blank=True,
        help_text="What students should know before starting"
    )
    
    # Course Structure
    duration_weeks = models.PositiveIntegerField(
        default=8,
        help_text="Course duration in weeks"
    )
    max_students = models.PositiveIntegerField(
        default=12,
        help_text="Maximum number of students"
    )
    sessions_per_week = models.PositiveIntegerField(
        default=2,
        help_text="Number of sessions per week"
    )
    total_projects = models.PositiveIntegerField(
        default=5,
        help_text="Number of projects students will create"
    )
    
    # Marketing Content
    value_propositions = models.JSONField(
        default=list,
        help_text="List of course benefits"
    )
    reviews = models.JSONField(
        default=list,
        help_text="Student reviews and ratings"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Course Introduction"
        verbose_name_plural = "Course Introductions"
    
    def __str__(self):
        return f"Introduction for {self.course.title}"
    
    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        if not self.reviews:
            return 0
        
        ratings = [review.get('rating', 0) for review in self.reviews if review.get('rating')]
        return sum(ratings) / len(ratings) if ratings else 0
    
    @property
    def review_count(self):
        """Get total number of reviews"""
        # Count both JSONField reviews and CourseReview model reviews
        json_reviews = len(self.reviews) if self.reviews else 0
        model_reviews = self.course.reviews.count() if hasattr(self, 'course') else 0
        return json_reviews + model_reviews


class CourseReview(models.Model):
    """
    Individual course reviews and ratings
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    
    # Student Information
    student_name = models.CharField(
        max_length=100,
        help_text="Student's display name"
    )
    student_age = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(18)],
        help_text="Student's age when review was written"
    )
    
    # Review Content
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    review_text = models.TextField(help_text="Review content")
    
    # Review Management
    is_verified = models.BooleanField(
        default=False,
        help_text="Admin verified this is a real review"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Show this review prominently on course details"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['course', '-created_at']),
            models.Index(fields=['course', 'is_featured']),
            models.Index(fields=['rating']),
        ]
    
    def __str__(self):
        return f"Review by {self.student_name} for {self.course.title} ({self.rating}★)"
    
    @property
    def display_name(self):
        """Get display name with age if available"""
        if self.student_age:
            return f"{self.student_name}, Age {self.student_age}"
        return self.student_name
    
    @property
    def star_rating(self):
        """Get star rating as list of booleans for template rendering"""
        return [i < self.rating for i in range(5)]