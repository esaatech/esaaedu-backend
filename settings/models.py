from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class CourseSettings(models.Model):
    """
    Global course-related settings including pricing and billing configurations
    Singleton model - only one instance should exist
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Billing Settings
    monthly_price_markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00,  # Default 15%
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ],
        help_text="Percentage markup for monthly payments compared to one-time payment"
    )
    
    # Trial Period Settings
    enable_trial_period = models.BooleanField(
        default=True,
        help_text="Enable trial period for courses"
    )
    
    trial_period_days = models.PositiveIntegerField(
        default=14,
        help_text="Trial period duration in days"
    )
    
    # Price Control Settings
    PRICE_CONTROL_CHOICES = [
        ('admin', 'Admin Only'),
        ('teacher', 'Teachers Only'),
        ('both', 'Both Admin and Teachers'),
    ]
    
    who_sets_price = models.CharField(
        max_length=10,
        choices=PRICE_CONTROL_CHOICES,
        default='admin',
        help_text="Who can set course prices - Admin, Teachers, or Both"
    )
    
    # Other Course Settings
    max_students_per_course = models.PositiveIntegerField(
        default=30,
        help_text="Default maximum students allowed per course"
    )
    
    default_course_duration_weeks = models.PositiveIntegerField(
        default=8,
        help_text="Default course duration in weeks"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Course Settings"
        verbose_name_plural = "Course Settings"
    
    def __str__(self):
        return f"Course Settings (Updated: {self.updated_at})"
    
    @classmethod
    def get_settings(cls):
        """
        Get the course settings instance, creating it if it doesn't exist
        Returns the settings object
        """
        settings, created = cls.objects.get_or_create(
            pk=cls.objects.first().pk if cls.objects.exists() else None,
            defaults={
                'monthly_price_markup_percentage': 15.00,
                'max_students_per_course': 30,
                'default_course_duration_weeks': 8,
                'enable_trial_period': True,
                'trial_period_days': 14,
                'who_sets_price': 'admin',
            }
        )
        return settings
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists"""
        if not self.pk and CourseSettings.objects.exists():
            return CourseSettings.objects.first()
        return super().save(*args, **kwargs)


class UserDashboardSettings(models.Model):
    """
    User-specific dashboard configuration settings
    Allows both students and teachers to customize their dashboard experience
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_settings'
    )
    
    # User Type - determines which settings are applicable
    USER_TYPE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]
    
    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default='student',
        help_text="Type of user - determines which settings are applicable"
    )
    
    # Dashboard Display Settings
    live_lessons_limit = models.PositiveIntegerField(
        default=3,
        help_text="Number of live lessons to show in upcoming events section"
    )
    
    continue_learning_limit = models.PositiveIntegerField(
        default=25,
        help_text="Number of lessons to show in continue learning section"
    )
    
    show_today_only = models.BooleanField(
        default=True,
        help_text="If True: show only today's events, If False: show all upcoming events"
    )
    
    # Additional Settings (for future expansion)
    theme_preference = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light Theme'),
            ('dark', 'Dark Theme'),
            ('system', 'System'),
        ],
        default='system',
        help_text="Dashboard theme preference"
    )
    
    notifications_enabled = models.BooleanField(
        default=True,
        help_text="Enable dashboard notifications"
    )
    
    # Teacher-specific Settings
    default_quiz_points = models.PositiveIntegerField(
        default=1,
        help_text="Default points for new quiz questions (teachers only)"
    )
    
    default_assignment_points = models.PositiveIntegerField(
        default=5,
        help_text="Default points for new assignment questions (teachers only)"
    )
    
    default_course_passing_score = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Default passing score percentage for courses and quizzes (teachers only)"
    )
    
    default_quiz_time_limit = models.PositiveIntegerField(
        default=10,
        help_text="Default time limit in minutes for new quizzes (teachers only)"
    )
    
    auto_grade_multiple_choice = models.BooleanField(
        default=False,
        help_text="Automatically grade multiple choice questions when students submit (teachers only)"
    )
    
    show_correct_answers_by_default = models.BooleanField(
        default=True,
        help_text="Show correct answers to students after quiz completion by default (teachers only)"
    )
    
    # Classroom Tool URLs (teachers only)
    whiteboard_url = models.URLField(
        max_length=500,
        blank=True,
        default='https://www.tldraw.com',
        help_text="Default URL for interactive whiteboard (teachers only)"
    )
    
    ide_url = models.URLField(
        max_length=500,
        blank=True,
        default='https://trinket.io',
        help_text="Default URL for IDE (teachers only)"
    )
    
    virtual_lab_url = models.URLField(
        max_length=500,
        blank=True,
        default='https://phet.colorado.edu',
        help_text="Default URL for virtual lab (teachers only)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Dashboard Settings"
        verbose_name_plural = "User Dashboard Settings"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Dashboard Settings for {self.user.email}"
    
    @classmethod
    def get_or_create_settings(cls, user):
        """
        Get or create dashboard settings for a user
        Returns the settings object
        """
        # Determine user type based on user role
        user_type = 'teacher' if hasattr(user, 'role') and user.role == 'teacher' else 'student'
        
        # Set defaults based on user type
        defaults = {
            'live_lessons_limit': 3,
            'continue_learning_limit': 25,
            'show_today_only': True,
            'theme_preference': 'system',
            'notifications_enabled': True,
            'user_type': user_type,
        }
        
        # Add teacher-specific defaults
        if user_type == 'teacher':
            defaults.update({
                'default_quiz_points': 1,
                'default_assignment_points': 5,
                'default_course_passing_score': 70,
                'default_quiz_time_limit': 10,
                'auto_grade_multiple_choice': False,
                'show_correct_answers_by_default': True,
                'whiteboard_url': 'https://www.tldraw.com',
                'ide_url': 'https://trinket.io',
                'virtual_lab_url': 'https://phet.colorado.edu',
            })
        
        settings, created = cls.objects.get_or_create(
            user=user,
            defaults=defaults
        )
        
        # Update user_type if it was changed
        if settings.user_type != user_type:
            settings.user_type = user_type
            settings.save()
        
        return settings
    
    def get_dashboard_config(self):
        """
        Return dashboard configuration as a dictionary
        """
        config = {
            'live_lessons_limit': self.live_lessons_limit,
            'continue_learning_limit': self.continue_learning_limit,
            'show_today_only': self.show_today_only,
            'theme_preference': self.theme_preference,
            'notifications_enabled': self.notifications_enabled,
        }
        
        # Add teacher-specific config if user is a teacher
        if self.user_type == 'teacher':
            # Get app-wide defaults for classroom tools
            app_defaults = ClassroomToolDefaults.get_or_create_defaults()
            
            config.update({
                'default_quiz_points': self.default_quiz_points,
                'default_assignment_points': self.default_assignment_points,
                'default_course_passing_score': self.default_course_passing_score,
                'default_quiz_time_limit': self.default_quiz_time_limit,
                'auto_grade_multiple_choice': self.auto_grade_multiple_choice,
                'show_correct_answers_by_default': self.show_correct_answers_by_default,
                # Use teacher's custom URLs or fall back to app-wide defaults
                'whiteboard_url': self.whiteboard_url or app_defaults.whiteboard_url,
                'ide_url': self.ide_url or app_defaults.ide_url,
                'virtual_lab_url': self.virtual_lab_url or app_defaults.virtual_lab_url,
            })
        
        return config


class ClassroomToolDefaults(models.Model):
    """
    App-wide default URLs for classroom tools (whiteboard, IDE, virtual lab)
    Singleton model - only one instance should exist
    These defaults are used when teachers haven't set custom URLs in their settings
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    whiteboard_url = models.URLField(
        max_length=500,
        default='https://www.tldraw.com',
        help_text="Default URL for interactive whiteboard"
    )
    
    ide_url = models.URLField(
        max_length=500,
        default='https://trinket.io',
        help_text="Default URL for IDE"
    )
    
    virtual_lab_url = models.URLField(
        max_length=500,
        default='https://phet.colorado.edu',
        help_text="Default URL for virtual lab"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Classroom Tool Defaults"
        verbose_name_plural = "Classroom Tool Defaults"
        ordering = ['-updated_at']
    
    def __str__(self):
        return "Classroom Tool Defaults"
    
    @classmethod
    def get_or_create_defaults(cls):
        """
        Get the singleton instance, creating it if it doesn't exist
        Returns the defaults object with app-wide default URLs
        """
        if cls.objects.exists():
            return cls.objects.first()
        return cls.objects.create(
            whiteboard_url='https://www.tldraw.com',
            ide_url='https://trinket.io',
            virtual_lab_url='https://phet.colorado.edu',
        )


class UserTutorXInstruction(models.Model):
    """
    User-specific TutorX instructions for block actions.
    
    Each user can customize their instructions for each action type (explain_more, 
    give_examples, etc.). When a user instruction doesn't exist, it defaults to 
    TutorXUserInstructionsDefaults from the tutorx app.
    
    Users can:
    - View their current instruction (or default if not customized)
    - Update their instruction (when editing is enabled)
    - Reset to default
    """
    ACTION_TYPES = [
        ('explain_more', 'Explain More'),
        ('give_examples', 'Give Examples'),
        ('simplify', 'Simplify'),
        ('summarize', 'Summarize'),
        ('generate_questions', 'Generate Questions'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tutorx_instructions',
        help_text="User who owns this instruction"
    )
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_TYPES,
        help_text="Type of block action this instruction is for"
    )
    
    # User's custom instruction
    user_instruction = models.TextField(
        help_text="User's custom instruction. Use placeholders: {block_content}, {context}, etc."
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User TutorX Instruction"
        verbose_name_plural = "User TutorX Instructions"
        unique_together = [['user', 'action_type']]
        ordering = ['user', 'action_type']
        indexes = [
            models.Index(fields=['user', 'action_type']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_action_type_display()}"
    
    @classmethod
    def get_or_create_settings(cls, user, action_type):
        """
        Get or create user instruction for a specific action type.
        
        If the instruction doesn't exist, it will be created with the default
        instruction from TutorXUserInstructionsDefaults.
        
        Args:
            user: User instance
            action_type: One of the ACTION_TYPES choices
            
        Returns:
            UserTutorXInstruction instance
        """
        # Try to get existing instruction
        try:
            return cls.objects.get(user=user, action_type=action_type)
        except cls.DoesNotExist:
            # Load default from TutorXUserInstructionsDefaults
            try:
                from tutorx.models import TutorXUserInstructionsDefaults
                default_config = TutorXUserInstructionsDefaults.objects.get(
                    action_type=action_type,
                    is_active=True
                )
                default_instruction = default_config.default_user_instruction
            except Exception:
                # Fallback if default doesn't exist
                default_instruction = f"Please provide additional information for: {action_type}"
            
            # Create new instruction with default
            return cls.objects.create(
                user=user,
                action_type=action_type,
                user_instruction=default_instruction
            )
    
    def reset_to_default(self):
        """
        Reset this instruction to the default from TutorXUserInstructionsDefaults.
        
        Returns:
            bool: True if reset was successful, False otherwise
        """
        try:
            from tutorx.models import TutorXUserInstructionsDefaults
            default_config = TutorXUserInstructionsDefaults.objects.get(
                action_type=self.action_type,
                is_active=True
            )
            self.user_instruction = default_config.default_user_instruction
            self.save()
            return True
        except Exception:
            return False
    
    def is_customized(self):
        """
        Check if this instruction has been customized (differs from default).
        
        Returns:
            bool: True if customized, False if still using default
        """
        try:
            from tutorx.models import TutorXUserInstructionsDefaults
            default_config = TutorXUserInstructionsDefaults.objects.get(
                action_type=self.action_type,
                is_active=True
            )
            return self.user_instruction != default_config.default_user_instruction
        except Exception:
            return True  # If we can't find default, assume it's customized