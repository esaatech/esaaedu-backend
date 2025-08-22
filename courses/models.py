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