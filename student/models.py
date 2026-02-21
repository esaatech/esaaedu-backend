from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
import secrets

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
    average_assignment_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Average assignment score percentage"
    )
    total_assignments_assigned = models.PositiveIntegerField(default=0)
    total_assignments_completed = models.PositiveIntegerField(default=0)
    
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
        if not self.enrollment_date:
            return None
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
        # Note: This property is currently unused in the UI but kept for potential future use
        if self.total_assignments_assigned == 0:
            return 0
        return (self.total_assignments_completed / self.total_assignments_assigned) * 100
    
    @property
    def quiz_completion_rate(self):
        """Calculate quiz completion rate"""
        if self.total_quizzes_taken == 0:
            return 0
        return (self.total_quizzes_passed / self.total_quizzes_taken) * 100
    
    @property
    def is_at_risk(self):
        """Determine if student is at risk based on engagement metrics"""
        if self.days_since_last_access and self.days_since_last_access > 7:
            return True
        if self.days_since_enrollment and self.progress_percentage < 50 and self.days_since_enrollment > 30:
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
            quiz__lessons__course=self.course
        ).distinct()
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
    
    def update_performance_metrics(self, quiz_score, passed, lesson_completed=False, assignment_completed=False):
        """
        Comprehensive performance metrics update function
        Updates all relevant metrics when various events occur
        
        Args:
            quiz_score (float): Quiz score percentage (0-100)
            passed (bool): Whether the quiz was passed
            lesson_completed (bool): Whether a lesson was completed
            assignment_completed (bool): Whether an assignment was completed
        """
        try:
            # Update quiz metrics
            self.total_quizzes_taken += 1
            if passed:
                self.total_quizzes_passed += 1
            
            # Update average quiz score
            if self.average_quiz_score is None:
                self.average_quiz_score = quiz_score
            else:
                total_score = self.average_quiz_score * (self.total_quizzes_taken - 1) + quiz_score
                self.average_quiz_score = total_score / self.total_quizzes_taken
            
            # Update highest/lowest quiz scores
            if quiz_score > self.highest_quiz_score:
                self.highest_quiz_score = quiz_score
            if quiz_score < self.lowest_quiz_score or self.lowest_quiz_score == 0:
                self.lowest_quiz_score = quiz_score
            
            # Update lesson progress if lesson was completed
            if lesson_completed:
                self.completed_lessons_count += 1
                self.update_progress_metrics()
                
                # Check if course is completed
                if self.completed_lessons_count >= self.total_lessons_count:
                    self.mark_completed()
            
            # Update assignment progress if assignment was completed
            if assignment_completed:
                self.total_assignments_completed += 1
            
            # Update last access time
            self.last_accessed = timezone.now()
            
            # Save all changes
            self.save()
            
            return True
            
        except Exception as e:
            print(f"Error updating performance metrics: {e}")
            return False
    
    def update_quiz_performance(self, quiz_score, passed):
        """
        Simple quiz performance update function
        Updates quiz-related metrics when a quiz is submitted
        
        Args:
            quiz_score (float): Quiz score percentage (0-100)
            passed (bool): Whether the quiz was passed
        """
        try:
            # Update quiz metrics
            self.total_quizzes_taken += 1
            if passed:
                self.total_quizzes_passed += 1
            
            # Update average quiz score
            if self.average_quiz_score is None:
                self.average_quiz_score = quiz_score
            else:
                total_score = self.average_quiz_score * (self.total_quizzes_taken - 1) + quiz_score
                self.average_quiz_score = total_score / self.total_quizzes_taken
            
            # Update highest/lowest quiz scores
            if quiz_score > self.highest_quiz_score:
                self.highest_quiz_score = quiz_score
            if quiz_score < self.lowest_quiz_score or self.lowest_quiz_score == 0:
                self.lowest_quiz_score = quiz_score
            
            # Update last access time
            self.last_accessed = timezone.now()
            
            # Save all changes
            self.save()
            
            return True
            
        except Exception as e:
            print(f"Error updating quiz performance: {e}")
            return False
    
    def update_assignment_performance(self, assignment_score, is_graded=False):
        """
        Update assignment performance metrics when an assignment is graded
        
        Args:
            assignment_score (float): Assignment score percentage (0-100)
            is_graded (bool): Whether the assignment is fully graded (not draft)
        """
        try:
            # Only update metrics if assignment is fully graded (not draft)
            if is_graded:
                # Calculate average assignment score dynamically
                from courses.models import AssignmentSubmission
                
                graded_submissions = AssignmentSubmission.objects.filter(
                    enrollment=self,
                    is_graded=True,
                    points_earned__isnull=False,
                    points_possible__isnull=False,
                    points_possible__gt=0
                )
                
                if graded_submissions.exists():
                    total_score = 0
                    for submission in graded_submissions:
                        score_percentage = (submission.points_earned / submission.points_possible) * 100
                        total_score += score_percentage
                    
                    self.average_assignment_score = total_score / graded_submissions.count()
                else:
                    self.average_assignment_score = assignment_score
                
                # Update last access time
                self.last_accessed = timezone.now()
                
                # Save all changes
                self.save()
                
                return True
            else:
                # For draft saves, just update last access time
                self.last_accessed = timezone.now()
                self.save()
                return True
            
        except Exception as e:
            print(f"Error updating assignment performance: {e}")
            return False
    
    @classmethod
    def get_total_lessons_completed_for_student(cls, student_profile):
        """
        Calculate total lessons completed across all courses for a student
        
        Args:
            student_profile: StudentProfile instance
            
        Returns:
            int: Total number of lessons completed across all courses
        """
        return cls.objects.filter(
            student_profile=student_profile,
            status__in=['active', 'completed']
        ).aggregate(
            total=models.Sum('completed_lessons_count')
        )['total'] or 0
    
    @classmethod
    def get_average_quiz_score_for_student(cls, student_profile):
        """
        Calculate average quiz score across all courses for a student
        
        Args:
            student_profile: StudentProfile instance
            
        Returns:
            float: Average quiz score across all courses (0-100)
        """
        enrollments = cls.objects.filter(
            student_profile=student_profile,
            status__in=['active', 'completed'],
            average_quiz_score__isnull=False
        )
        
        if not enrollments.exists():
            return 0.0
        
        total_score = 0
        total_courses = 0
        
        for enrollment in enrollments:
            if enrollment.average_quiz_score is not None:
                total_score += float(enrollment.average_quiz_score)
                total_courses += 1
        
        return round(total_score / total_courses, 2) if total_courses > 0 else 0.0
    
    @classmethod
    def get_learning_streak_for_student(cls, student_profile):
        """
        Calculate learning streak for a student
        For now, this returns a simple calculation based on active enrollments
        You can enhance this later with more sophisticated streak logic
        
        Args:
            student_profile: StudentProfile instance
            
        Returns:
            int: Current learning streak in days
        """
        # Simple implementation: count active enrollments as streak
        # You can enhance this with actual activity tracking later
        active_enrollments = cls.objects.filter(
            student_profile=student_profile,
            status='active'
        ).count()
        
        # For now, return a simple calculation
        # You might want to add a learning_streak field to track actual consecutive days
        return min(active_enrollments * 7, 30)  # Max 30 days for now
    
    def mark_lesson_complete(self, lesson, require_quiz=True):
        """
        Mark a lesson as complete and recalculate current_lesson from progress records.
        Uses StudentLessonProgress records as the single source of truth.
        
        Args:
            lesson: Lesson instance to mark as complete
            require_quiz: Whether to require quiz completion (default: True)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Verify the lesson belongs to this course
            if lesson.course != self.course:
                return False, f"Lesson {lesson.id} does not belong to course {self.course.id}"
            
            # Get or create lesson progress record
            lesson_progress, created = StudentLessonProgress.objects.get_or_create(
                enrollment=self,
                lesson=lesson,
                defaults={'status': 'not_started'}
            )
            
            # Check if lesson is already completed
            if lesson_progress.is_completed:
                return False, "Lesson already completed"
            
            # Check quiz requirement if enabled
            if require_quiz and lesson_progress.requires_quiz and lesson_progress.quiz_attempts_count == 0:
                return False, "You must complete the quiz before completing this lesson"
            
            # Mark lesson as completed in progress tracking (single source of truth)
            lesson_progress.mark_as_completed()
            
            # Recalculate all enrollment fields from progress records (single source of truth)
            self._recalculate_from_progress_records()
            
            # Update last accessed time
            self.last_accessed = timezone.now()
            
            # Save all changes
            self.save()
            
            print(f"Successfully marked lesson '{lesson.title}' as complete for {self.student_profile.user.get_full_name()}")
            print(f"Recalculated: current_lesson={self.current_lesson.title if self.current_lesson else None}, completed_count={self.completed_lessons_count}")
            return True, f"Lesson '{lesson.title}' marked as complete"
            
        except Exception as e:
            print(f"Error marking lesson complete: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Error completing lesson: {str(e)}"
    
    def _recalculate_from_progress_records(self):
        """
        Recalculate enrollment fields from StudentLessonProgress records (single source of truth).
        This ensures consistency between progress records and enrollment metadata.
        Refreshes total_lessons_count from the course and reverts to active when new lessons exist.
        """
        # Refresh total from current course (teacher may have added/removed lessons)
        self.total_lessons_count = self.course.lessons.count()

        # Get all progress records for this enrollment
        progress_records = StudentLessonProgress.objects.filter(
            enrollment=self
        ).select_related('lesson')
        
        # Calculate actual completed count from progress records
        completed_lesson_ids = set()
        for progress in progress_records:
            if progress.is_completed:
                completed_lesson_ids.add(progress.lesson.id)
        
        actual_completed_count = len(completed_lesson_ids)
        self.completed_lessons_count = actual_completed_count
        
        # Debug logging for overflow detection
        print(f"🔍 DEBUG _recalculate_from_progress_records:")
        print(f"   - Course: {self.course.title if self.course else 'Unknown'}")
        print(f"   - Total progress records: {progress_records.count()}")
        print(f"   - Completed lesson IDs: {completed_lesson_ids}")
        print(f"   - actual_completed_count: {actual_completed_count}")
        print(f"   - total_lessons_count: {self.total_lessons_count}")
        
        # Recalculate current_lesson from progress records
        # Current lesson = next lesson after the highest completed lesson order
        highest_completed_order = 0
        for progress in progress_records:
            if progress.is_completed:
                highest_completed_order = max(highest_completed_order, progress.lesson.order)
        
        if highest_completed_order > 0:
            # Find next lesson after highest completed order
            next_lesson = self.course.lessons.filter(
                order__gt=highest_completed_order
            ).order_by('order').first()
            if next_lesson:
                self.current_lesson = next_lesson
            else:
                # All lessons completed
                self.current_lesson = None
                self.status = 'completed'
                self.completion_date = timezone.now().date()
                self.progress_percentage = 100.0
        else:
            # No lessons completed yet, start with first lesson
            self.current_lesson = self.course.lessons.order_by('order').first()
        
        # Recalculate progress percentage
        # Cap at 100.0 since it's a percentage (0-100%)
        # This prevents DecimalField overflow errors
        if self.total_lessons_count > 0:
            calculated_percentage = (self.completed_lessons_count / self.total_lessons_count) * 100
            # Cap at 100.0 to prevent overflow and because progress can't exceed 100%
            self.progress_percentage = min(calculated_percentage, 100.0)
            
            # Debug logging for overflow detection
            if calculated_percentage > 100.0:
                print(f"⚠️ WARNING: Progress percentage calculated as {calculated_percentage}% (capped at 100.0%)")
                print(f"   - completed_lessons_count: {self.completed_lessons_count}")
                print(f"   - total_lessons_count: {self.total_lessons_count}")
                print(f"   - Course: {self.course.title if self.course else 'Unknown'}")
        else:
            self.progress_percentage = 0.0

        # If course was marked completed but teacher added more lessons, revert to active
        if self.status == 'completed' and self.completed_lessons_count < self.total_lessons_count:
            self.status = 'active'
            self.completion_date = None


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
    viewed_at = models.DateTimeField(null=True, blank=True, help_text="When the student first viewed this assessment")
    
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


class StudentLessonProgress(models.Model):
    """
    Student progress on individual lessons
    Tracks detailed progress for each lesson within an enrollment
    """
    LESSON_STATUS = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('locked', 'Locked'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(
        EnrolledCourse, 
        on_delete=models.CASCADE, 
        related_name='lesson_progress'
    )
    lesson = models.ForeignKey(
        'courses.Lesson', 
        on_delete=models.CASCADE,
        related_name='student_progress'
    )
    
    # Progress Details
    status = models.CharField(max_length=20, choices=LESSON_STATUS, default='not_started')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent = models.IntegerField(default=0, help_text="Time spent in minutes")
    
    # Content-specific progress (e.g., video progress, reading progress)
    progress_data = models.JSONField(
        default=dict,
        help_text="Lesson-specific progress data (video position, reading progress, etc.)"
    )
    
    # Quiz Performance (if lesson has quiz)
    quiz_attempts_count = models.IntegerField(default=0)
    quiz_passed = models.BooleanField(default=False)
    best_quiz_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Best quiz score as percentage"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['enrollment', 'lesson']
        ordering = ['lesson__order']
        verbose_name = 'Student Lesson Progress'
        verbose_name_plural = 'Student Lesson Progress'
    
    def __str__(self):
        return f"{self.enrollment.student_profile.user.get_full_name()} - {self.lesson.title} ({self.status})"
    
    def mark_as_started(self):
        """Mark lesson as started"""
        if self.status == 'not_started':
            self.status = 'in_progress'
            self.started_at = timezone.now()
            self.save()
    
    def mark_as_completed(self):
        """Mark lesson as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def update_quiz_performance(self, score, passed):
        """Update quiz performance for this lesson"""
        self.quiz_attempts_count += 1
        if passed:
            self.quiz_passed = True
        if not self.best_quiz_score or score > self.best_quiz_score:
            self.best_quiz_score = score
        self.save()
    
    def update_progress_data(self, data):
        """Update lesson-specific progress data"""
        self.progress_data.update(data)
        self.save()
    
    @property
    def is_completed(self):
        """Check if lesson is completed"""
        return self.status == 'completed'
    
    @property
    def can_be_completed(self):
        """Check if lesson can be marked as completed"""
        # Can be completed if it's in progress or not started
        return self.status in ['not_started', 'in_progress']
    
    @property
    def requires_quiz(self):
        """Check if lesson requires quiz completion"""
        return hasattr(self.lesson, 'quiz') and self.lesson.quiz is not None
    
    @property
    def can_complete_without_quiz(self):
        """Check if lesson can be completed without quiz"""
        if not self.requires_quiz:
            return True
        return self.quiz_passed


class Conversation(models.Model):
    """
    Conversation thread between a teacher and a student's parent or the student themselves.
    Supports separate conversations for parent and student messaging.
    """
    RECIPIENT_TYPE_CHOICES = [
        ('parent', 'Parent'),
        ('student', 'Student'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_profile = models.ForeignKey(
        'users.StudentProfile',
        on_delete=models.CASCADE,
        related_name='conversations',
        help_text="Student profile this conversation is about"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_conversations',
        limit_choices_to={'role': 'teacher'},
        help_text="Teacher in this conversation"
    )
    recipient_type = models.CharField(
        max_length=10,
        choices=RECIPIENT_TYPE_CHOICES,
        default='parent',
        help_text="Whether messages are for parent or student"
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        help_text="Course this conversation is about (null for general conversations)"
    )
    subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional conversation topic/subject"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of most recent message (for sorting)"
    )
    
    class Meta:
        db_table = 'conversations'
        indexes = [
            models.Index(fields=['student_profile', 'recipient_type', '-last_message_at']),
            models.Index(fields=['teacher', 'recipient_type', '-last_message_at']),
            models.Index(fields=['course', 'student_profile', '-last_message_at']),
        ]
        unique_together = [['student_profile', 'teacher', 'recipient_type', 'course']]
        ordering = ['-last_message_at', '-created_at']
    
    def __str__(self):
        recipient_name = self.student_profile.user.get_full_name() or self.student_profile.user.email
        teacher_name = self.teacher.get_full_name() or self.teacher.email
        course_info = f" - {self.course.title}" if self.course else ""
        return f"Conversation ({self.recipient_type}){course_info}: {teacher_name} ↔ {recipient_name}"
    
    def clean(self):
        """Validate that teacher has role 'teacher'"""
        if self.teacher.role != 'teacher':
            raise ValidationError("Conversation teacher must have role 'teacher'")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Message(models.Model):
    """
    Individual message within a conversation.
    Messages inherit recipient_type from their conversation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Conversation this message belongs to"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        help_text="User who sent this message"
    )
    content = models.TextField(help_text="Message content")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When message was read (null if unread)"
    )
    read_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='read_messages',
        help_text="User who read this message"
    )
    
    class Meta:
        db_table = 'messages'
        indexes = [
            models.Index(fields=['conversation', '-created_at']),
            models.Index(fields=['conversation', 'read_at']),
        ]
        ordering = ['created_at']
    
    def __str__(self):
        sender_name = self.sender.get_full_name() or self.sender.email
        return f"Message from {sender_name} in {self.conversation}"
    
    def mark_as_read(self, user):
        """Mark message as read by a user"""
        if not self.read_at:
            self.read_at = timezone.now()
            self.read_by = user
            self.save(update_fields=['read_at', 'read_by'])
    
    @property
    def is_read(self):
        """Check if message has been read"""
        return self.read_at is not None


class CodeSnippet(models.Model):
    """
    Code snippets saved by students
    Can be shared via unique link and submitted for assignments/tests/exams
    Used by both students (to save/submit) and teachers (to view/grade)
    """
    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('javascript', 'JavaScript'),
        ('html', 'HTML'),
        ('css', 'CSS'),
        ('json', 'JSON'),
        ('java', 'Java'),
        ('cpp', 'C++'),
        ('c', 'C'),
        ('other', 'Other'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='code_snippets',
        limit_choices_to={'role': 'student'},
        null=True,
        blank=True,
        help_text="Student who created this code snippet (null for teacher snippets)"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_code_snippets',
        limit_choices_to={'role': 'teacher'},
        null=True,
        blank=True,
        help_text="Teacher who created this code snippet (for lesson examples)"
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='code_snippets',
        null=True,
        blank=True,
        help_text="Lesson this snippet is associated with (for teacher snippets)"
    )
    class_instance = models.ForeignKey(
        'courses.Class',
        on_delete=models.CASCADE,
        related_name='code_snippets',
        null=True,
        blank=True,
        help_text="Class this snippet is associated with (optional)"
    )
    is_teacher_snippet = models.BooleanField(
        default=False,
        help_text="Whether this is a teacher-created snippet (visible to all students in the lesson)"
    )
    
    # Code Content
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional title for the code snippet"
    )
    code = models.TextField(help_text="The actual code content")
    language = models.CharField(
        max_length=50,
        choices=LANGUAGE_CHOICES,
        default='python',
        help_text="Programming language"
    )
    
    # CSS-specific: GCP URL for CSS files (only populated when language is 'css')
    css_file_url = models.URLField(
        null=True,
        blank=True,
        max_length=500,
        help_text="GCP URL for CSS files. Only populated when language is 'css'. Allows CSS to be referenced in HTML via <link> tags."
    )
    
    # Sharing (default to True as requested)
    is_shared = models.BooleanField(
        default=True,
        help_text="Whether this code snippet is shareable (default: True)"
    )
    share_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique token for sharing (auto-generated)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'code_snippets'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['student', '-updated_at']),
            models.Index(fields=['share_token']),
            models.Index(fields=['language']),
            models.Index(fields=['is_shared']),
            models.Index(fields=['css_file_url']),  # Index for CSS file lookups
        ]
        verbose_name = "Code Snippet"
        verbose_name_plural = "Code Snippets"
    
    def __str__(self):
        title = self.title or f"Untitled {self.get_language_display()} Code"
        return f"{self.student.get_full_name()} - {title}"
    
    def save(self, *args, **kwargs):
        # Set is_teacher_snippet based on teacher field
        if self.teacher and not self.student:
            self.is_teacher_snippet = True
        elif self.student and not self.teacher:
            self.is_teacher_snippet = False
        
        # Generate share_token if not set and is_shared is True
        if self.is_shared and not self.share_token:
            self.share_token = secrets.token_urlsafe(32)
        # Remove share_token if is_shared is False
        elif not self.is_shared and self.share_token:
            self.share_token = None
        super().save(*args, **kwargs)
    
    @property
    def share_url(self):
        """Get the shareable URL for this code snippet"""
        if self.is_shared and self.share_token:
            return f"/code/{self.share_token}"
        return None
    
    def get_share_link(self, base_url=""):
        """Get full shareable link with base URL"""
        if self.share_url:
            return f"{base_url}{self.share_url}"
        return None

