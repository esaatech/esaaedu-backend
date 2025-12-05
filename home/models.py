from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class ContactMethod(models.Model):
    """
    Different contact methods available (Live Chat, Email, Phone, WhatsApp)
    """
    CONTACT_TYPE_CHOICES = [
        ('live_chat', 'Live Chat'),
        ('email', 'Email Support'),
        ('phone', 'Phone Support'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES, unique=True)
    title = models.CharField(max_length=100, help_text="Display title for the contact method")
    description = models.TextField(help_text="Description of the contact method")
    availability = models.CharField(max_length=100, help_text="When this method is available")
    response_time = models.CharField(max_length=50, help_text="Expected response time")
    action_text = models.CharField(max_length=100, help_text="Button or action text")
    action_value = models.CharField(max_length=200, help_text="Email, phone number, or URL")
    icon = models.CharField(max_length=50, help_text="Icon class or identifier")
    color = models.CharField(max_length=20, default='purple', help_text="Color theme for the method")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Contact Method"
        verbose_name_plural = "Contact Methods"
        ordering = ['order', 'type']
    
    def __str__(self):
        return self.title


class SupportTeamMember(models.Model):
    """
    Support team members for the Meet Our Support Team section
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=100, help_text="Job title")
    responsibilities = models.TextField(help_text="What they help with")
    email = models.EmailField(help_text="Contact email")
    avatar_initials = models.CharField(max_length=10, help_text="Initials for avatar display")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Support Team Member"
        verbose_name_plural = "Support Team Members"
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.title}"


class FAQ(models.Model):
    """
    Frequently Asked Questions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=100, blank=True, help_text="Optional category grouping")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ['order', 'question']
    
    def __str__(self):
        return self.question[:50] + "..." if len(self.question) > 50 else self.question


class SupportHours(models.Model):
    """
    Support hours information
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.CharField(max_length=50, help_text="e.g., Mon-Fri, Weekends, Emergency")
    hours = models.CharField(max_length=50, help_text="e.g., 9AM-6PM EST, 24/7")
    is_emergency = models.BooleanField(default=False, help_text="Mark as emergency/24-7 service")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Support Hours"
        verbose_name_plural = "Support Hours"
        ordering = ['order', 'period']
    
    def __str__(self):
        return f"{self.period}: {self.hours}"


class ContactSubmission(models.Model):
    """
    Contact form submissions
    """
    SUBJECT_CHOICES = [
        ('general', 'General Inquiry'),
        ('technical', 'Technical Support'),
        ('billing', 'Billing Question'),
        ('course_guidance', 'Course Guidance'),
        ('enrollment', 'Enrollment Help'),
        ('other', 'Other'),
    ]
    
    AGE_RANGE_CHOICES = [
        ('3-5', '3-5 years'),
        ('6-8', '6-8 years'),
        ('9-12', '9-12 years'),
        ('13-15', '13-15 years'),
        ('16-18', '16-18 years'),
        ('adult', 'Adult'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Inquiry Details
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    child_age = models.CharField(max_length=10, choices=AGE_RANGE_CHOICES, blank=True)
    message = models.TextField()
    
    # Preferences
    wants_updates = models.BooleanField(default=False, help_text="Wants to receive updates about new courses")
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
        ],
        default='new'
    )
    
    # Response tracking
    response_notes = models.TextField(blank=True, help_text="Internal notes about the response")
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who responded to this inquiry"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Contact Submission"
        verbose_name_plural = "Contact Submissions"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_subject_display()}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class AssessmentSubmission(models.Model):
    """
    STEM Assessment form submissions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Parent/Guardian Information
    parent_name = models.CharField(max_length=100)
    parent_contact = models.CharField(max_length=20)
    email = models.EmailField()
    
    # Student Information
    student_name = models.CharField(max_length=100)
    student_age = models.PositiveIntegerField(
        validators=[MinValueValidator(3), MaxValueValidator(18)]
    )
    school_level = models.CharField(max_length=50, blank=True)
    city_country = models.CharField(max_length=100, blank=True)
    
    # STEM Interest Areas (stored as JSON)
    interest_areas = models.JSONField(
        default=list,
        help_text="List of selected STEM interest areas"
    )
    
    # Coding Experience
    has_coding_experience = models.BooleanField(default=False)
    coding_tools = models.TextField(blank=True, help_text="Tools/languages used if has experience")
    
    # Computer Skills Level
    COMPUTER_SKILLS_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    computer_skills_level = models.CharField(
        max_length=20,
        choices=COMPUTER_SKILLS_CHOICES,
        blank=True,
        help_text="Computer/technology experience level"
    )
    
    # Device Access (stored as JSON)
    device_access = models.JSONField(
        default=list,
        help_text="List of available devices"
    )
    
    # Availability
    availability_days = models.JSONField(
        default=list,
        help_text="List of available days of the week"
    )
    preferred_time_slots = models.CharField(max_length=100, blank=True)
    
    # Goals
    goals = models.TextField(blank=True, help_text="What parent wants child to gain from program")
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New'),
            ('contacted', 'Contacted'),
            ('enrolled', 'Enrolled'),
            ('not_interested', 'Not Interested'),
            ('closed', 'Closed'),
        ],
        default='new'
    )
    
    # Response tracking
    response_notes = models.TextField(blank=True, help_text="Internal notes about follow-up")
    contacted_at = models.DateTimeField(null=True, blank=True)
    contacted_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who contacted this submission"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Assessment Submission"
        verbose_name_plural = "Assessment Submissions"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.parent_name} - {self.student_name} ({self.student_age} years)"