from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model that integrates with Firebase Authentication
    """
    
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        TEACHER = 'teacher', 'Teacher'
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
    linkedin_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    
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