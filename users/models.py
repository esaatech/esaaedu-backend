from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Avg, Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta


class User(AbstractUser):
    """
    Custom User model that integrates with Firebase Authentication
    """
    
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        TEACHER = 'teacher', 'Teacher'
        PARENT = 'parent', 'Parent'
        ADMIN = 'admin', 'Admin'
    
    # Firebase UID is the primary identifier
    firebase_uid = models.CharField(max_length=255, unique=True)
    
    # User role
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    
    # Additional fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    
    # Override username to use email as primary identifier
    username = models.CharField(max_length=150, unique=False, blank=True)
    email = models.EmailField(unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['firebase_uid']
    
    class Meta:
        db_table = 'users'
        
    def __str__(self):
        return f"{self.email} ({self.role})"
    
    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER
    
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT
    
    @property
    def is_parent(self):
        return self.role == self.Role.PARENT


class TeacherProfile(models.Model):
    """
    Extended profile information for teachers
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='teacher_profile'
    )
    
    bio = models.TextField(blank=True, help_text="Teacher's biography")
    qualifications = models.TextField(blank=True, help_text="Educational qualifications and certifications")
    department = models.CharField(max_length=100, blank=True, help_text="Department or subject area")
    profile_image = models.URLField(blank=True, help_text="URL to profile image")
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Teaching preferences
    specializations = models.JSONField(default=list, help_text="List of subject specializations")
    years_of_experience = models.PositiveIntegerField(null=True, blank=True)
    
    # Social links
    linkedin_url = models.URLField(max_length=500, blank=True)
    twitter_url = models.URLField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teacher_profiles'
        
    def __str__(self):
        return f"Teacher Profile: {self.user.get_full_name() or self.user.email}"


class StudentProfile(models.Model):
    """
    Extended profile information for students
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='student_profile'
    )
    
    # Student/Child information
    child_first_name = models.CharField(max_length=50, blank=True, help_text="Child's first name")
    child_last_name = models.CharField(max_length=50, blank=True, help_text="Child's last name") 
    child_email = models.EmailField(blank=True, help_text="Child's email (for older students)")
    child_phone = models.CharField(max_length=20, blank=True, help_text="Child's phone (for older students)")
    grade_level = models.CharField(max_length=20, blank=True, help_text="Current grade level")
    date_of_birth = models.DateField(null=True, blank=True)
    profile_image = models.URLField(blank=True, help_text="URL to profile image")
    
    # Parent/Guardian information
    parent_email = models.EmailField(blank=True, help_text="Parent/Guardian email")
    parent_name = models.CharField(max_length=100, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=255, blank=True)
    
    # Learning preferences
    learning_goals = models.TextField(blank=True, help_text="Student's learning goals")
    interests = models.JSONField(default=list, help_text="List of interests and hobbies")
    
    # Account settings
    notifications_enabled = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    
    # Performance Aggregates (denormalized for fast dashboard queries)
    # These are updated automatically via signals when quizzes/assignments are submitted/graded
    total_quizzes_completed = models.PositiveIntegerField(
        default=0,
        help_text="Total number of completed quiz attempts across all courses"
    )
    total_assignments_completed = models.PositiveIntegerField(
        default=0,
        help_text="Total number of completed assignment submissions across all courses"
    )
    overall_quiz_average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Overall average quiz score percentage across all courses"
    )
    overall_assignment_average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Overall average assignment score percentage across all courses"
    )
    overall_average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Combined average of quiz and assignment scores"
    )
    last_performance_update = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last performance aggregate update"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_profiles'
        
    def __str__(self):
        return f"Student Profile: {self.user.get_full_name() or self.user.email}"
    
    @property
    def age(self):
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    def recalculate_quiz_aggregates(self):
        """
        Recalculate overall quiz statistics from all enrollments.
        Uses weighted average based on number of quizzes completed per course.
        """
        try:
            enrollments = self.course_enrollments.filter(
                status__in=['active', 'completed']
            )
            
            total_score_weighted = Decimal('0.0')
            total_quizzes = 0
            
            for enrollment in enrollments:
                if enrollment.average_quiz_score is not None:
                    # Use enrollment's tracked quiz count as weight
                    quiz_count = enrollment.total_quizzes_taken
                    
                    if quiz_count > 0:
                        total_score_weighted += Decimal(str(enrollment.average_quiz_score)) * quiz_count
                        total_quizzes += quiz_count
            
            # Update aggregates
            self.total_quizzes_completed = total_quizzes
            
            if total_quizzes > 0:
                self.overall_quiz_average_score = round(total_score_weighted / total_quizzes, 2)
            else:
                self.overall_quiz_average_score = None
            
            self.last_performance_update = timezone.now()
            self.save(update_fields=[
                'total_quizzes_completed',
                'overall_quiz_average_score',
                'last_performance_update'
            ])
            
            # Recalculate overall average (quiz + assignment)
            self.recalculate_overall_average()
            
            return True
        except Exception as e:
            print(f"Error recalculating quiz aggregates for {self.user.email}: {e}")
            return False
    
    def recalculate_assignment_aggregates(self):
        """
        Recalculate overall assignment statistics from all enrollments.
        Uses weighted average based on number of assignments completed per course.
        """
        try:
            enrollments = self.course_enrollments.filter(
                status__in=['active', 'completed']
            )
            
            total_score_weighted = Decimal('0.0')
            total_assignments = 0
            
            for enrollment in enrollments:
                if enrollment.average_assignment_score is not None:
                    # Use completed assignments count as weight
                    count = enrollment.total_assignments_completed
                    if count > 0:
                        total_score_weighted += Decimal(str(enrollment.average_assignment_score)) * count
                        total_assignments += count
            
            # Update aggregates
            self.total_assignments_completed = total_assignments
            
            if total_assignments > 0:
                self.overall_assignment_average_score = round(total_score_weighted / total_assignments, 2)
            else:
                self.overall_assignment_average_score = None
            
            self.last_performance_update = timezone.now()
            self.save(update_fields=[
                'total_assignments_completed',
                'overall_assignment_average_score',
                'last_performance_update'
            ])
            
            # Recalculate overall average (quiz + assignment)
            self.recalculate_overall_average()
            
            return True
        except Exception as e:
            print(f"Error recalculating assignment aggregates for {self.user.email}: {e}")
            return False
    
    def recalculate_overall_average(self):
        """
        Recalculate the combined overall average of quiz and assignment scores.
        """
        try:
            quiz_score = self.overall_quiz_average_score
            assignment_score = self.overall_assignment_average_score
            
            # Calculate weighted average if both exist
            if quiz_score is not None and assignment_score is not None:
                quiz_weight = self.total_quizzes_completed
                assignment_weight = self.total_assignments_completed
                total_weight = quiz_weight + assignment_weight
                
                if total_weight > 0:
                    weighted_sum = (Decimal(str(quiz_score)) * quiz_weight + 
                                   Decimal(str(assignment_score)) * assignment_weight)
                    self.overall_average_score = round(weighted_sum / total_weight, 2)
                else:
                    self.overall_average_score = None
            elif quiz_score is not None:
                self.overall_average_score = quiz_score
            elif assignment_score is not None:
                self.overall_average_score = assignment_score
            else:
                self.overall_average_score = None
            
            self.save(update_fields=['overall_average_score'])
            return True
        except Exception as e:
            print(f"Error recalculating overall average for {self.user.email}: {e}")
            return False


class StudentWeeklyPerformance(models.Model):
    """
    Weekly performance aggregates for students
    Stores pre-calculated weekly averages to avoid expensive queries on dashboard load
    Automatically maintained via signals when quizzes/assignments are completed/graded
    """
    student_profile = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='weekly_performance'
    )
    
    # Week identification (ISO week format)
    week_start_date = models.DateField(
        help_text="Monday of the week (ISO week start)"
    )
    year = models.IntegerField(
        help_text="Year of the week"
    )
    week_number = models.IntegerField(
        help_text="ISO week number (1-53)"
    )
    
    # Weekly aggregates
    quiz_average = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average quiz score percentage for this week"
    )
    quiz_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of quizzes completed this week"
    )
    
    assignment_average = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average assignment score percentage for this week"
    )
    assignment_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of assignments completed/graded this week"
    )
    
    overall_average = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Combined weighted average of quiz and assignment scores for this week"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_weekly_performance'
        unique_together = ['student_profile', 'year', 'week_number']
        ordering = ['-year', '-week_number']
        indexes = [
            models.Index(fields=['student_profile', 'year', 'week_number']),
            models.Index(fields=['student_profile', 'week_start_date']),
        ]
        verbose_name = 'Student Weekly Performance'
        verbose_name_plural = 'Student Weekly Performances'
    
    def __str__(self):
        return f"{self.student_profile.user.email} - {self.year}-W{self.week_number:02d}"
    
    def recalculate_week_averages(self):
        """
        Recalculate averages for this specific week from QuizAttempt and AssignmentSubmission records.
        Called automatically when a quiz/assignment is completed in this week.
        """
        from courses.models import QuizAttempt, AssignmentSubmission
        
        # Get the week date range (Monday to Sunday)
        week_end = self.week_start_date + timedelta(days=6)
        
        # Calculate quiz average for this week
        quiz_attempts = QuizAttempt.objects.filter(
            student=self.student_profile.user,
            completed_at__isnull=False,
            completed_at__date__gte=self.week_start_date,
            completed_at__date__lte=week_end,
            score__isnull=False
        )
        
        quiz_aggregate = quiz_attempts.aggregate(
            avg_score=Avg('score'),
            count=Count('id')
        )
        
        self.quiz_count = quiz_aggregate['count'] or 0
        self.quiz_average = round(Decimal(str(quiz_aggregate['avg_score'])), 2) if quiz_aggregate['avg_score'] else None
        
        # Calculate assignment average for this week
        # Use graded_at if available, otherwise submitted_at
        assignment_submissions = AssignmentSubmission.objects.filter(
            student=self.student_profile.user,
            is_graded=True,
            percentage__isnull=False
        ).filter(
            Q(graded_at__isnull=False, graded_at__date__gte=self.week_start_date, graded_at__date__lte=week_end) |
            Q(graded_at__isnull=True, submitted_at__date__gte=self.week_start_date, submitted_at__date__lte=week_end)
        )
        
        assignment_aggregate = assignment_submissions.aggregate(
            avg_score=Avg('percentage'),
            count=Count('id')
        )
        
        self.assignment_count = assignment_aggregate['count'] or 0
        self.assignment_average = round(Decimal(str(assignment_aggregate['avg_score'])), 2) if assignment_aggregate['avg_score'] else None
        
        # Calculate combined overall average (weighted)
        if self.quiz_average is not None and self.assignment_average is not None:
            total_weight = self.quiz_count + self.assignment_count
            if total_weight > 0:
                weighted_sum = (Decimal(str(self.quiz_average)) * self.quiz_count +
                               Decimal(str(self.assignment_average)) * self.assignment_count)
                self.overall_average = round(weighted_sum / total_weight, 2)
            else:
                self.overall_average = None
        elif self.quiz_average is not None:
            self.overall_average = self.quiz_average
        elif self.assignment_average is not None:
            self.overall_average = self.assignment_average
        else:
            self.overall_average = None
        
        self.save()
        return True
    
    @staticmethod
    def get_or_create_week_performance(student_profile, date):
        """
        Get or create a StudentWeeklyPerformance record for the week containing the given date.
        
        Args:
            student_profile: StudentProfile instance
            date: datetime or date object - the date to find the week for
            
        Returns:
            tuple: (StudentWeeklyPerformance instance, created boolean)
        """
        if isinstance(date, datetime):
            date = date.date()
        
        # Calculate ISO week (Monday is start of week)
        # Get Monday of the week
        days_since_monday = date.weekday()  # Monday is 0
        week_start = date - timedelta(days=days_since_monday)
        
        # Get ISO year and week number
        iso_year, iso_week, _ = date.isocalendar()
        
        # Get or create the weekly performance record
        weekly_perf, created = StudentWeeklyPerformance.objects.get_or_create(
            student_profile=student_profile,
            year=iso_year,
            week_number=iso_week,
            defaults={
                'week_start_date': week_start,
            }
        )
        
        return weekly_perf, created
    
    @staticmethod
    def update_weekly_performance(student_profile, completion_date):
        """
        Update weekly performance aggregates for the week containing the completion_date.
        This is called from signal handlers when a quiz/assignment is completed.
        
        Args:
            student_profile: StudentProfile instance
            completion_date: datetime - when the quiz/assignment was completed/graded
        """
        try:
            weekly_perf, _ = StudentWeeklyPerformance.get_or_create_week_performance(
                student_profile,
                completion_date
            )
            weekly_perf.recalculate_week_averages()
        except Exception as e:
            print(f"Error updating weekly performance for {student_profile.user.email}: {e}")


class ParentProfile(models.Model):
    """
    Extended profile information for parents
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='parent_profile'
    )
    
    phone_number = models.CharField(max_length=20, blank=True)
    profile_image = models.URLField(blank=True, help_text="URL to profile image")
    
    # Parent preferences
    preferred_communication_method = models.CharField(
        max_length=50, 
        blank=True, 
        choices=[
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('sms', 'SMS'),
        ],
        default='email'
    )
    
    # Notification preferences
    notifications_enabled = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'parent_profiles'
        
    def __str__(self):
        return f"Parent Profile: {self.user.get_full_name() or self.user.email}"