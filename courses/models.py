from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
import logging
import secrets

User = get_user_model()
logger = logging.getLogger(__name__)

class CourseCategory(models.Model):
    """
    Course category model
    """
    name = models.CharField(max_length=200, help_text="Course category name")
    description = models.TextField(help_text="Course category description")
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Course Category"
        verbose_name_plural = "Course Categories"
        ordering = ['name']


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
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    
    # Computer Skills Requirement (for course recommendations)
    REQUIRED_COMPUTER_SKILLS_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('any', 'Any Level'),
    ]
    required_computer_skills_level = models.CharField(
        max_length=20,
        choices=REQUIRED_COMPUTER_SKILLS_CHOICES,
        default='any',
        blank=True,
        help_text="Required computer/technology experience level for this course. Used for assessment-based recommendations."
    )
    
    # Pricing & Features
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        help_text="Course price in USD"
    )
    is_free = models.BooleanField(
        default=False,
        help_text="Whether this course is free to access"
    )
    features = models.JSONField(
        default=list, 
        help_text="List of course features/highlights"
    )
    
    # Introduction/Detailed Information (filled in later)
    overview = models.TextField(
        blank=True, 
        help_text="Detailed course overview (extended description)"
    )
    learning_objectives = models.JSONField(
        default=list, 
        help_text="Detailed learning objectives"
    )
    prerequisites_text = models.JSONField(
        default=list,
        blank=True,
        help_text="List of prerequisites as JSON array"
    )
    duration_weeks = models.PositiveIntegerField(
        default=8, 
        help_text="Course duration in weeks"
    )
    sessions_per_week = models.PositiveIntegerField(
        default=2, 
        help_text="Number of sessions per week"
    )
    total_projects = models.PositiveIntegerField(
        default=5, 
        help_text="Number of projects students will create"
    )
    value_propositions = models.JSONField(
        default=list, 
        help_text="List of course benefits and value propositions"
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
    image = models.ImageField(
        upload_to='course_images/',
        blank=True,
        null=True,
        help_text="Course cover image (optional)"
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
        return self.enrolled_students.through.objects.filter(course=self).count()
    
    @property
    def is_featured_eligible(self):
        return (
            self.status == 'published' and 
            self.featured == True
        )
    
    @property
    def has_introduction(self):
        """Check if introduction fields are filled"""
        return bool(self.overview or self.learning_objectives or self.value_propositions)
    
    @property
    def duration(self):
        """Generate user-friendly duration string from duration_weeks"""
        if self.duration_weeks == 1:
            return "1 week"
        return f"{self.duration_weeks} weeks"
    
    @property
    def image_url(self):
        """Get course image URL or fallback to placeholder"""
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return '/static/images/course-placeholder.jpg'  # Fallback placeholder
    
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
    
# No need for custom save method - single table approach


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
    
    # Materials & Resources
    materials = models.JSONField(
        default=list,
        blank=True,
        help_text="List of lesson materials, resources, and attachments"
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


class LessonMaterial(models.Model):
    """
    Pre-class materials and resources for lessons
    """
    MATERIAL_TYPES = [
        ('document', 'Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('link', 'External Link'),
        ('image', 'Image'),
        ('pdf', 'PDF'),
        ('presentation', 'Presentation'),
        ('worksheet', 'Worksheet'),
        ('book', 'Book'),
        ('note', 'Note'),
        ('other', 'Other'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lessons = models.ManyToManyField(Lesson, related_name='lesson_materials', blank=True)
    title = models.CharField(max_length=200, help_text="Material title")
    description = models.TextField(blank=True, help_text="Material description")
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES)
    
    # File/Resource Information
    file_url = models.URLField(blank=True, null=True, help_text="URL to the material file")
    file_size = models.PositiveIntegerField(blank=True, null=True, help_text="File size in bytes")
    file_extension = models.CharField(max_length=10, blank=True, help_text="File extension (e.g., pdf, docx)")
    
    # Material Settings
    is_required = models.BooleanField(default=False, help_text="Whether this material is required before class")
    is_downloadable = models.BooleanField(default=True, help_text="Whether students can download this material")
    order = models.PositiveIntegerField(default=0, help_text="Display order of materials")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['material_type']),
            models.Index(fields=['is_required']),
        ]
    
    def __str__(self):
        lesson_names = ", ".join([lesson.title for lesson in self.lessons.all()])
        return f"{lesson_names} - {self.title}" if lesson_names else self.title
    
    @property
    def file_size_mb(self):
        """Convert file size to MB for display"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None


class BookPage(models.Model):
    """
    Individual pages for book materials
    Allows pagination through book content
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book_material = models.ForeignKey(
        LessonMaterial, 
        on_delete=models.CASCADE, 
        related_name='book_pages',
        limit_choices_to={'material_type': 'book'}
    )
    page_number = models.PositiveIntegerField(help_text="Page number within the book")
    title = models.CharField(max_length=200, blank=True, help_text="Page title (optional)")
    content = models.TextField(help_text="Page content")
    
    # Page Resources
    image_url = models.URLField(blank=True, null=True, help_text="Page image URL")
    audio_url = models.URLField(blank=True, null=True, help_text="Page audio URL")
    
    # Page Settings
    is_required = models.BooleanField(default=True, help_text="Is this page required reading?")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['book_material', 'page_number']
        unique_together = ['book_material', 'page_number']
        indexes = [
            models.Index(fields=['book_material', 'page_number']),
            models.Index(fields=['is_required']),
        ]
    
    def __str__(self):
        return f"{self.book_material.title} - Page {self.page_number}"
    
    @property
    def next_page_number(self):
        """Get the next page number"""
        return self.page_number + 1
    
    @property
    def previous_page_number(self):
        """Get the previous page number"""
        return self.page_number - 1 if self.page_number > 1 else None


class VideoMaterial(models.Model):
    """
    Video-specific data for video materials.
    Similar to BookPage for books, this extends LessonMaterial with video-specific fields.
    Also caches transcriptions to avoid re-transcribing the same video URL.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to LessonMaterial (optional - can exist independently for caching)
    lesson_material = models.OneToOneField(
        LessonMaterial,
        on_delete=models.CASCADE,
        related_name='video_data',
        blank=True,
        null=True,
        limit_choices_to={'material_type': 'video'},
        help_text="Link to LessonMaterial if this is part of a lesson"
    )
    
    # Video Information
    video_url = models.URLField(help_text="URL of the video (YouTube or other)")
    video_id = models.CharField(max_length=100, blank=True, null=True, help_text="Video ID (e.g., YouTube video ID)")
    is_youtube = models.BooleanField(default=False, help_text="Whether this is a YouTube video")
    
    # Transcript Data (optional - only if transcribed)
    transcript = models.TextField(blank=True, null=True, help_text="Full transcript text (if transcribed)")
    language = models.CharField(max_length=10, blank=True, null=True, help_text="Language code of transcript (e.g., 'en', 'es')")
    language_name = models.CharField(max_length=50, blank=True, null=True, help_text="Language name (e.g., 'English')")
    transcript_available_to_students = models.BooleanField(
        default=False,
        help_text="Whether transcript is visible to students"
    )
    
    # Transcription Metadata
    method_used = models.CharField(
        max_length=20,
        choices=[
            ('youtube_api', 'YouTube Transcript API'),
            ('vertex_ai', 'Vertex AI'),
        ],
        blank=True,
        null=True,
        help_text="Method used to transcribe the video (if transcribed)"
    )
    transcript_length = models.PositiveIntegerField(blank=True, null=True, help_text="Length of transcript in characters")
    word_count = models.PositiveIntegerField(blank=True, null=True, help_text="Word count of transcript")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    transcribed_at = models.DateTimeField(blank=True, null=True, help_text="When the transcription was created (if transcribed)")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['video_url']),
            models.Index(fields=['video_id']),
            models.Index(fields=['is_youtube']),
            models.Index(fields=['method_used']),
            models.Index(fields=['lesson_material']),
        ]
        verbose_name = "Video Material"
        verbose_name_plural = "Video Materials"
    
    def __str__(self):
        if self.lesson_material:
            return f"Video Material: {self.lesson_material.title}"
        video_id_display = self.video_id or self.video_url[:50]
        return f"Video Material: {video_id_display}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate transcript length and word count if transcript exists
        if self.transcript:
            self.transcript_length = len(self.transcript)
            self.word_count = len(self.transcript.split())
            # Set transcribed_at if not already set
            if not self.transcribed_at:
                from django.utils import timezone
                self.transcribed_at = timezone.now()
        super().save(*args, **kwargs)
    
    @property
    def has_transcript(self):
        """Check if this video material has a transcript"""
        return bool(self.transcript and self.transcript.strip())


class DocumentMaterial(models.Model):
    """
    Document-specific data for document materials.
    Similar to VideoMaterial for videos, this extends LessonMaterial with document-specific fields.
    Stores metadata about uploaded documents (PDF, DOCX, DOC, TXT, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to LessonMaterial (optional - can exist independently for caching)
    lesson_material = models.OneToOneField(
        LessonMaterial,
        on_delete=models.CASCADE,
        related_name='document_data',
        blank=True,
        null=True,
        limit_choices_to={'material_type': 'document'},
        help_text="Link to LessonMaterial if this is part of a lesson"
    )
    
    # File Information
    file_name = models.CharField(
        max_length=255,
        help_text="Stored filename in GCS (e.g., 'documents/uuid-filename.pdf')"
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename from user upload (e.g., 'My Lesson Notes.pdf')"
    )
    file_url = models.URLField(
        help_text="Full GCS URL to the document"
    )
    
    # File Metadata
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes"
    )
    file_extension = models.CharField(
        max_length=10,
        help_text="File extension (e.g., 'pdf', 'docx', 'doc', 'txt')"
    )
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type (e.g., 'application/pdf', 'application/msword')"
    )
    
    # Upload Information
    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents',
        help_text="Teacher who uploaded this document"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['file_url']),
            models.Index(fields=['file_extension']),
            models.Index(fields=['mime_type']),
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['lesson_material']),
        ]
        verbose_name = "Document Material"
        verbose_name_plural = "Document Materials"
    
    def __str__(self):
        if self.lesson_material:
            return f"Document Material: {self.lesson_material.title}"
        return f"Document Material: {self.original_filename}"
    
    @property
    def file_size_mb(self):
        """Convert file size to MB for display"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None
    
    @property
    def is_pdf(self):
        """Check if this is a PDF document"""
        return self.file_extension.lower() == 'pdf' or self.mime_type == 'application/pdf'
    
    def delete(self, *args, **kwargs):
        """
        Override delete to also delete the file from Google Cloud Storage.
        This ensures that when a DocumentMaterial is deleted (either directly or via CASCADE
        when LessonMaterial is deleted), the associated file is also removed from GCS.
        """
        # Delete file from GCS before deleting the model
        if self.file_name:
            try:
                from django.core.files.storage import default_storage
                from django.conf import settings
                
                # Only delete from GCS if GCS is configured
                if hasattr(settings, 'GS_BUCKET_NAME') and settings.GS_BUCKET_NAME:
                    try:
                        # Delete the file from GCS
                        default_storage.delete(self.file_name)
                        logger.info(f"Deleted file from GCS: {self.file_name}")
                    except Exception as e:
                        # Log error but don't fail the deletion
                        logger.error(f"Failed to delete file from GCS ({self.file_name}): {e}")
                        # Continue with model deletion even if file deletion fails
                else:
                    # If GCS is not configured, try local storage
                    try:
                        from django.core.files.storage import default_storage
                        default_storage.delete(self.file_name)
                        logger.info(f"Deleted file from local storage: {self.file_name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete file from storage ({self.file_name}): {e}")
            except Exception as e:
                # Log error but don't fail the deletion
                logger.error(f"Error during file deletion ({self.file_name}): {e}")
        
        # Call parent delete to remove the model instance
        super().delete(*args, **kwargs)


class AudioVideoMaterial(models.Model):
    """
    Audio/Video-specific data for audio/video materials.
    Similar to DocumentMaterial for documents, this extends LessonMaterial with audio/video-specific fields.
    Stores metadata about uploaded audio/video files (MP3, MP4, WAV, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to LessonMaterial (optional - can exist independently for caching)
    lesson_material = models.OneToOneField(
        LessonMaterial,
        on_delete=models.CASCADE,
        related_name='audio_video_data',
        blank=True,
        null=True,
        limit_choices_to={'material_type': 'audio'},
        help_text="Link to LessonMaterial if this is part of a lesson"
    )
    
    # File Information
    file_name = models.CharField(
        max_length=255,
        help_text="Stored filename in GCS (e.g., 'audio-video/uuid-filename.mp4')"
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename from user upload (e.g., 'My Lesson Video.mp4')"
    )
    file_url = models.URLField(
        help_text="Full GCS URL to the audio/video file"
    )
    
    # File Metadata
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes"
    )
    file_extension = models.CharField(
        max_length=10,
        help_text="File extension (e.g., 'mp3', 'mp4', 'wav', 'ogg')"
    )
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type (e.g., 'audio/mpeg', 'video/mp4', 'audio/wav')"
    )
    
    # Upload Information
    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_audio_videos',
        help_text="Teacher who uploaded this audio/video"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['file_url']),
            models.Index(fields=['file_extension']),
            models.Index(fields=['mime_type']),
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['lesson_material']),
        ]
        verbose_name = "Audio/Video Material"
        verbose_name_plural = "Audio/Video Materials"
    
    def __str__(self):
        if self.lesson_material:
            return f"Audio/Video Material: {self.lesson_material.title}"
        return f"Audio/Video Material: {self.original_filename}"
    
    @property
    def file_size_mb(self):
        """Convert file size to MB for display"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None
    
    @property
    def is_audio(self):
        """Check if this is an audio file"""
        return self.mime_type.startswith('audio/')
    
    @property
    def is_video(self):
        """Check if this is a video file"""
        return self.mime_type.startswith('video/')
    
    def delete(self, *args, **kwargs):
        """
        Override delete to also delete the file from Google Cloud Storage.
        This ensures that when an AudioVideoMaterial is deleted (either directly or via CASCADE
        when LessonMaterial is deleted), the associated file is also removed from GCS.
        Follows the same pattern as DocumentMaterial.
        """
        # Delete file from GCS before deleting the model
        if self.file_name:
            try:
                from django.core.files.storage import default_storage
                from django.conf import settings
                
                # Only delete from GCS if GCS is configured
                if hasattr(settings, 'GS_BUCKET_NAME') and settings.GS_BUCKET_NAME:
                    try:
                        # Delete the file from GCS
                        default_storage.delete(self.file_name)
                        logger.info(f"Deleted audio/video file from GCS: {self.file_name}")
                    except Exception as e:
                        # Log error but don't fail the deletion
                        logger.error(f"Failed to delete audio/video file from GCS ({self.file_name}): {e}")
                        # Continue with model deletion even if file deletion fails
                else:
                    # If GCS is not configured, try local storage
                    try:
                        import os
                        if os.path.exists(self.file_name):
                            os.remove(self.file_name)
                            logger.info(f"Deleted audio/video file from local storage: {self.file_name}")
                    except Exception as e:
                        logger.error(f"Failed to delete audio/video file from local storage ({self.file_name}): {e}")
            except Exception as e:
                logger.error(f"Error deleting audio/video file ({self.file_name}): {e}")
                # Continue with model deletion even if file deletion fails
        
        # Call parent delete to actually delete the model
        super().delete(*args, **kwargs)


class Project(models.Model):
    SUBMISSION_TYPES = [
        ('link', 'Link/URL'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('file', 'File Upload'),
        ('note', 'Text Note'),
        ('code', 'Code'),
        ('presentation', 'Presentation'),
    ]
    
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    
    # Submission type and requirements
    submission_type = models.CharField(
        max_length=20, 
        choices=SUBMISSION_TYPES,
        help_text="Type of submission expected from students"
    )
    
    # File upload constraints (if applicable)
    allowed_file_types = models.JSONField(default=list, blank=True, help_text="Allowed file extensions")
    
    points = models.PositiveIntegerField(default=100)   # max points for this project
    due_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.course} · {self.title}"
    
    @property
    def submission_type_display(self):
        """Get the display name for the submission type"""
        return dict(self.SUBMISSION_TYPES).get(self.submission_type, "Unknown")
    
    @property
    def requires_file_upload(self):
        """Check if this project type requires file upload"""
        return self.submission_type in ['image', 'video', 'audio', 'file', 'code', 'presentation']
    
    @property
    def requires_text_input(self):
        """Check if this project type requires text input"""
        return self.submission_type in ['note', 'code']
    
    @property
    def requires_url_input(self):
        """Check if this project type requires URL input"""
        return self.submission_type in ['link', 'presentation']        





class Quiz(models.Model):
    """
    Quiz associated with lessons (can be used by multiple lessons)
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lessons = models.ManyToManyField(Lesson, related_name='quizzes', blank=True)
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
        ordering = ['title', 'created_at']
    
    def __str__(self):
        lesson_names = ', '.join([lesson.title for lesson in self.lessons.all()[:3]])
        if self.lessons.count() > 3:
            lesson_names += '...'
        return f"Quiz: {self.title} ({lesson_names or 'No lessons'})"


class Assignment(models.Model):
    """
    Assignment associated with lessons (can be used by multiple lessons)
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lessons = models.ManyToManyField(Lesson, related_name='assignments', blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Assignment Configuration
    due_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Assignment due date"
    )
    passing_score = models.IntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum percentage to pass"
    )
    max_attempts = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of attempts allowed"
    )
    show_correct_answers = models.BooleanField(
        default=False,
        help_text="Show correct answers after completion"
    )
    randomize_questions = models.BooleanField(
        default=False,
        help_text="Randomize question order for each attempt"
    )
    
    # Assignment Type
    ASSIGNMENT_TYPES = [
        ('homework', 'Homework'),
        ('project', 'Project'),
        ('exam', 'Exam'),
        ('quiz', 'Quiz-style Assignment'),
        ('essay', 'Essay Assignment'),
        ('practical', 'Practical Assignment'),
    ]
    
    assignment_type = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_TYPES,
        default='homework',
        help_text="Type of assignment"
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
        ordering = ['title', 'created_at']
        indexes = [
            models.Index(fields=['assignment_type']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        lesson_names = ', '.join([lesson.title for lesson in self.lessons.all()[:3]])
        if self.lessons.count() > 3:
            lesson_names += '...'
        return f"Assignment: {self.title} ({lesson_names or 'No lessons'})"


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
        ('flashcard', 'Flashcard'),
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






class AssignmentQuestion(models.Model):
    """
    Individual question within an assignment
    Separate from Question model to avoid breaking existing quizzes
    """
    QUESTION_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('fill_blank', 'Fill in the Blank'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
        ('matching', 'Matching'),
        ('ordering', 'Ordering/Ranking'),
        ('flashcard', 'Flashcard'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField(help_text="The question text")
    order = models.IntegerField(help_text="Question order within the assignment")
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
        ordering = ['assignment', 'order']
        unique_together = ['assignment', 'order']
        indexes = [
            models.Index(fields=['assignment', 'order']),
            models.Index(fields=['type']),
        ]
    
    def __str__(self):
        return f"AQ{self.order}: {self.question_text[:50]}..."


class QuizAttempt(models.Model):
    """
    Student attempts at quizzes
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    enrollment = models.ForeignKey('student.EnrolledCourse', on_delete=models.CASCADE)
    
    # Attempt Details
    attempt_number = models.IntegerField(validators=[MinValueValidator(1)])
    started_at = models.DateTimeField(auto_now_add=False)
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
    
    # NEW: Teacher grading fields
    is_teacher_graded = models.BooleanField(
        default=False, 
        help_text="Has teacher manually graded or enhanced this quiz?"
    )
    teacher_grade_data = models.JSONField(
        default=dict,
        help_text="Teacher's manual grading data (overrides auto-calculated if present)"
    )
    grading_history = models.JSONField(
        default=list,
        help_text="Audit trail of grading changes and enhancements"
    )
    
    class Meta:
        unique_together = ['student', 'quiz', 'attempt_number']
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'quiz']),
            models.Index(fields=['enrollment', 'completed_at']),
            models.Index(fields=['is_teacher_graded']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.quiz.title} (Attempt {self.attempt_number})"
    
    # NEW: Computed properties for consistent data access
    @property
    def final_score(self):
        """Return teacher grade if available, otherwise auto-calculated"""
        if self.is_teacher_graded and self.teacher_grade_data.get('percentage'):
            return self.teacher_grade_data['percentage']
        return self.score
    
    @property
    def final_points_earned(self):
        """Return teacher points if available, otherwise auto-calculated"""
        if self.is_teacher_graded and self.teacher_grade_data.get('points_earned'):
            return self.teacher_grade_data['points_earned']
        return self.points_earned
    
    @property
    def final_points_possible(self):
        """Return teacher points if available, otherwise quiz total"""
        if self.is_teacher_graded and self.teacher_grade_data.get('points_possible'):
            return self.teacher_grade_data['points_possible']
        return self.quiz.total_points
    
    @property
    def teacher_comments(self):
        """Get teacher comments if available"""
        return self.teacher_grade_data.get('teacher_comments', '')
    
    @property
    def graded_questions(self):
        """Get teacher question-level feedback if available"""
        return self.teacher_grade_data.get('graded_questions', [])
    
    @property
    def display_status(self):
        """Return status for frontend display"""
        if self.is_teacher_graded:
            return "teacher_enhanced"
        elif self.score is not None:
            return "auto_graded"
        else:
            return "ungraded"


class AssignmentSubmission(models.Model):
    """
    Student submissions for assignments with grading and feedback
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    enrollment = models.ForeignKey('student.EnrolledCourse', on_delete=models.CASCADE)
    
    # Submission Details
    attempt_number = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Submission status: draft, submitted, or graded"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Student Answers
    answers = models.JSONField(
        default=dict,
        help_text="Student answers for each question"
    )
    
    # Teacher Grading
    is_graded = models.BooleanField(default=False, help_text="Has teacher graded this submission?")
    is_teacher_draft = models.BooleanField(default=False, help_text="Is teacher currently working on grading this submission?")
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='graded_assignments',
        limit_choices_to={'role': 'teacher'}
    )
    
    # Scoring
    points_earned = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Points earned by student"
    )
    points_possible = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Total points possible"
    )
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Percentage score"
    )
    passed = models.BooleanField(default=False, help_text="Did student pass the assignment?")
    
    # Feedback System
    instructor_feedback = models.TextField(
        blank=True,
        help_text="Teacher's feedback on the submission"
    )
    feedback_checked = models.BooleanField(
        default=False,
        help_text="Has student seen the feedback?"
    )
    feedback_checked_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When student last checked feedback"
    )
    feedback_response = models.TextField(
        blank=True,
        help_text="Student's response to teacher feedback"
    )
    
    # Question-level grading
    graded_questions = models.JSONField(
        default=list,
        help_text="Individual question grades and feedback - list of {question_id, points_earned, points_possible, teacher_feedback/feedback, correct_answer (optional), is_correct (optional)}"
    )
    
    # Grading History
    grading_history = models.JSONField(
        default=list,
        help_text="Audit trail of grading changes"
    )
    
    class Meta:
        unique_together = ['student', 'assignment', 'attempt_number']
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['student', 'assignment']),
            models.Index(fields=['enrollment', 'submitted_at']),
            models.Index(fields=['is_graded']),
            models.Index(fields=['feedback_checked']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.assignment.title} (Attempt {self.attempt_number})"
    
    def save(self, *args, **kwargs):
        # Track if this is a new submission or status change
        is_new_submission = self.pk is None
        was_submitted = False
        
        if not is_new_submission:
            # Check if status changed to 'submitted'
            try:
                old_submission = AssignmentSubmission.objects.get(pk=self.pk)
                was_submitted = (old_submission.status != 'submitted' and self.status == 'submitted')
            except AssignmentSubmission.DoesNotExist:
                was_submitted = (self.status == 'submitted')
        else:
            was_submitted = (self.status == 'submitted')
        
        # Auto-calculate percentage if points are provided
        if self.points_earned is not None and self.points_possible is not None and self.points_possible > 0:
            self.percentage = (self.points_earned / self.points_possible) * 100
            
            # Check if passed based on assignment passing score
            if self.assignment and self.percentage >= self.assignment.passing_score:
                self.passed = True
            else:
                self.passed = False
        
        # Backward compatibility: auto-set status based on is_graded
        # Only auto-set status if it's not explicitly provided or is invalid
        if hasattr(self, 'status'):
            if self.is_graded and self.status not in ['graded', 'draft', 'submitted']:
                # Only auto-set to 'graded' if status is not explicitly set
                self.status = 'graded'
            elif not self.is_graded and self.status not in ['draft', 'submitted']:
                # If no status is set, default to 'submitted' for existing records
                self.status = 'submitted'
        
        super().save(*args, **kwargs)
        
        # Update assignment completion metrics
        if was_submitted and self.enrollment:
            try:
                # Increment completed assignments count
                self.enrollment.total_assignments_completed += 1
                self.enrollment.save()
            except Exception as e:
                print(f"Error updating assignment completion metrics: {e}")
    
    @property
    def display_status(self):
        """Return status for frontend display"""
        # Use new status field if available, otherwise fall back to old logic
        if hasattr(self, 'status') and self.status:
            return self.status
        # Backward compatibility: use is_graded field
        elif self.is_graded:
            return "graded"
        else:
            return "submitted"
    
    @property
    def grader_name(self):
        """Get grader's name if available"""
        if self.graded_by:
            return self.graded_by.get_full_name()
        return "Unknown"
    
    def mark_feedback_checked(self):
        """Mark feedback as checked by student"""
        from django.utils import timezone
        self.feedback_checked = True
        self.feedback_checked_at = timezone.now()
        self.save(update_fields=['feedback_checked', 'feedback_checked_at'])


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


# CourseIntroduction model removed - all fields moved to Course model
    



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
    
    @property
    def formatted_schedule(self):
        """Get formatted schedule string from sessions"""
        active_sessions = self.sessions.filter(is_active=True).order_by('session_number')
        if not active_sessions.exists():
            return "No schedule set"
        
        schedule_parts = []
        for session in active_sessions:
            schedule_parts.append(session.formatted_schedule)
        
        return " • ".join(schedule_parts)
    
    @property
    def session_count(self):
        """Get number of active sessions"""
        return self.sessions.filter(is_active=True).count()
    
    def can_enroll_student(self, student):
        """Check if a student can be enrolled in this class"""
        if self.is_full:
            return False, "Class is at maximum capacity"
        
        if student in self.students.all():
            return False, "Student is already enrolled in this class"
        
            # Check if student is enrolled in the course
        from student.models import EnrolledCourse
        try:
            enrollment = EnrolledCourse.objects.get(
                student_profile__user=student, 
                course=self.course,
                status='active'
            )
            return True, "Student can be enrolled"
        except EnrolledCourse.DoesNotExist:
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
    
    def get_or_create_classroom(self):
        """
        Get or create a Classroom for this Class instance
        Returns (classroom, created) tuple
        """
        classroom, created = Classroom.objects.get_or_create(
            class_instance=self,
            defaults={
                'is_active': True,
                'chat_enabled': True,
                'board_enabled': True,
                'video_enabled': True,
            }
        )
        return classroom, created


class Classroom(models.Model):
    """
    Virtual classroom for a Class instance
    Links to Class (one-to-one relationship)
    Active during scheduled ClassEvent sessions
    Provides persistent chat, virtual board, and video capabilities
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # One-to-one relationship with Class
    class_instance = models.OneToOneField(
        Class,
        on_delete=models.CASCADE,
        related_name='classroom',
        help_text="The class this classroom belongs to"
    )
    
    # Room configuration
    room_code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Unique room code for students to join (e.g., 'MATH-AM-A')"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the classroom is currently active"
    )
    
    # Feature settings (for future features)
    chat_enabled = models.BooleanField(
        default=True,
        help_text="Whether chat is enabled in this classroom"
    )
    board_enabled = models.BooleanField(
        default=True,
        help_text="Whether virtual board is enabled in this classroom"
    )
    video_enabled = models.BooleanField(
        default=True,
        help_text="Whether video cam is enabled in this classroom"
    )
    ide_enabled = models.BooleanField(
        default=False,
        help_text="Whether IDE is enabled in this classroom"
    )
    virtual_lab_enabled = models.BooleanField(
        default=False,
        help_text="Whether virtual lab is enabled in this classroom"
    )
    
    # tldraw board integration
    tldraw_board_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique tldraw board room ID for this classroom (generated on-demand)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'classrooms'
        verbose_name = "Classroom"
        verbose_name_plural = "Classrooms"
        ordering = ['class_instance__course__title', 'class_instance__name']
    
    def __str__(self):
        return f"Classroom: {self.class_instance.name} ({self.room_code})"
    
    def save(self, *args, **kwargs):
        """Auto-generate room_code if not provided"""
        if not self.room_code:
            # Generate a unique room code based on class name and UUID prefix
            class_name_clean = ''.join(c for c in self.class_instance.name if c.isalnum())[:8].upper()
            uuid_prefix = str(self.id)[:8].upper()
            self.room_code = f"{class_name_clean}-{uuid_prefix}"
            
            # Ensure uniqueness
            while Classroom.objects.filter(room_code=self.room_code).exists():
                uuid_prefix = str(uuid.uuid4())[:8].upper()
                self.room_code = f"{class_name_clean}-{uuid_prefix}"
        
        super().save(*args, **kwargs)
    
    def is_session_active(self):
        """
        Check if there's an active ClassEvent session right now
        Returns True if there's a lesson event currently ongoing
        """
        now = timezone.now()
        return self.class_instance.events.filter(
            start_time__lte=now,
            end_time__gte=now,
            event_type='lesson'
        ).exists()
    
    def get_active_session(self):
        """
        Get the currently active ClassEvent session
        Returns the active ClassEvent or None
        """
        now = timezone.now()
        return self.class_instance.events.filter(
            start_time__lte=now,
            end_time__gte=now,
            event_type='lesson'
        ).first()
    
    def can_student_join(self, student):
        """
        Check if a student can join this classroom
        Returns (can_join: bool, message: str)
        """
        # Student must be enrolled in the class
        if student not in self.class_instance.students.all():
            return False, "Student not enrolled in this class"
        
        # Classroom must be active
        if not self.is_active:
            return False, "Classroom is not active"
        
        # Student can join (optional: check for active session)
        # For now, we allow joining anytime if enrolled
        # You can add session check later: has_active_session = self.is_session_active()
        return True, "Student can join"
    
    def get_or_create_tldraw_board_id(self):
        """
        Get or create tldraw board ID for this classroom (on-demand generation)
        Returns the board ID string
        """
        if not self.tldraw_board_id:
            # Generate a unique board ID using UUID
            # tldraw uses URL-safe IDs, so we'll use a UUID hex string
            board_id = uuid.uuid4().hex[:32]  # 32 character hex string
            
            # Ensure uniqueness (very unlikely but check anyway)
            while Classroom.objects.filter(tldraw_board_id=board_id).exists():
                board_id = uuid.uuid4().hex[:32]
            
            self.tldraw_board_id = board_id
            self.save(update_fields=['tldraw_board_id', 'updated_at'])
        
        return self.tldraw_board_id
    
    def get_tldraw_board_url(self):
        """
        Get the tldraw.com board URL for this classroom
        Generates board ID on-demand if it doesn't exist
        Returns the full URL or None if board is disabled
        """
        if not self.board_enabled:
            return None
        
        board_id = self.get_or_create_tldraw_board_id()
        # tldraw.com hosted version URL format: https://www.tldraw.com/r/{roomId}
        return f"https://www.tldraw.com/r/{board_id}"
    
    def get_enrolled_students(self):
        """Get all students enrolled in this classroom's class"""
        return self.class_instance.students.all()
    
    @property
    def student_count(self):
        """Get number of enrolled students"""
        return self.class_instance.student_count


class Board(models.Model):
    """
    Interactive whiteboard for a Classroom
    Supports multiple pages, permissions, and settings
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # One-to-one relationship with Classroom
    classroom = models.OneToOneField(
        Classroom,
        on_delete=models.CASCADE,
        related_name='board',
        help_text="The classroom this board belongs to"
    )
    
    # Board metadata
    title = models.CharField(
        max_length=200,
        default="Classroom Board",
        help_text="Board title/name"
    )
    description = models.TextField(
        blank=True,
        help_text="Board description"
    )
    
    # Permissions & Settings
    allow_student_edit = models.BooleanField(
        default=False,
        help_text="Whether students can draw/edit on the board"
    )
    allow_student_create_pages = models.BooleanField(
        default=False,
        help_text="Whether students can create new pages"
    )
    view_only_mode = models.BooleanField(
        default=False,
        help_text="If True, students can only view (read-only mode)"
    )
    
    # Board state
    current_page_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the currently active page"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_boards',
        help_text="User who created this board"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'boards'
        verbose_name = "Board"
        verbose_name_plural = "Boards"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Board: {self.title} ({self.classroom.room_code})"
    
    def get_current_page(self):
        """Get the currently active page"""
        if self.current_page_id:
            try:
                return self.pages.get(id=self.current_page_id)
            except BoardPage.DoesNotExist:
                return None
        # Return first page if no current page set
        return self.pages.first()
    
    def get_or_create_default_page(self):
        """Get or create the default page (first page)"""
        page = self.pages.first()
        if not page:
            page = BoardPage.objects.create(
                board=self,
                page_name="Page 1",
                page_order=0,
                created_by=self.created_by,
                state={}  # Empty initial state
            )
            self.current_page_id = page.id
            self.save(update_fields=['current_page_id', 'updated_at'])
        return page
    
    def can_user_edit(self, user):
        """Check if user can edit the board"""
        # Teachers can always edit
        if user.role == 'teacher':
            return True
        
        # Students can edit if allowed and not in view-only mode
        if user.role == 'student':
            return self.allow_student_edit and not self.view_only_mode
        
        return False
    
    def can_user_create_pages(self, user):
        """Check if user can create pages"""
        # Teachers can always create pages
        if user.role == 'teacher':
            return True
        
        # Students can create pages if allowed
        if user.role == 'student':
            return self.allow_student_create_pages
        
        return False


class BoardPage(models.Model):
    """
    Individual page within a Board
    Each page stores its own tldraw document state
    """
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationship to Board
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='pages',
        help_text="The board this page belongs to"
    )
    
    # Page metadata
    page_name = models.CharField(
        max_length=200,
        default="Page 1",
        help_text="Page name/title"
    )
    page_order = models.IntegerField(
        default=0,
        help_text="Order of this page within the board (for sorting)"
    )
    
    # Page state (tldraw document snapshot)
    state = models.JSONField(
        default=dict,
        help_text="Full tldraw store snapshot (document state)"
    )
    version = models.IntegerField(
        default=1,
        help_text="Version number for conflict resolution"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_board_pages',
        help_text="User who created this page"
    )
    last_updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_board_pages',
        help_text="User who last updated this page"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'board_pages'
        verbose_name = "Board Page"
        verbose_name_plural = "Board Pages"
        ordering = ['board', 'page_order', 'created_at']
        unique_together = [['board', 'page_order']]  # Ensure unique order per board
    
    def __str__(self):
        return f"{self.page_name} (Board: {self.board.title})"
    
    def increment_version(self):
        """Increment version number"""
        self.version += 1
        self.save(update_fields=['version', 'updated_at'])


class ClassSession(models.Model):
    """
    Recurring weekly session schedule for a class
    Defines the days and times when the class meets each week
    """
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Session name (e.g., 'Session 1', 'Morning Session')"
    )
    
    # Relationships
    class_instance = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='sessions',
        help_text="The class this session belongs to"
    )
    
    # Schedule Details
    day_of_week = models.IntegerField(
        choices=DAY_CHOICES,
        help_text="Day of the week (0=Monday, 6=Sunday)"
    )
    start_time = models.TimeField(help_text="Session start time")
    end_time = models.TimeField(help_text="Session end time")
    session_number = models.PositiveIntegerField(
        help_text="Order of this session (1, 2, 3...)"
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Whether this session is active")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'class_sessions'
        verbose_name = "Class Session"
        verbose_name_plural = "Class Sessions"
        ordering = ['class_instance', 'session_number', 'day_of_week']
        unique_together = ['class_instance', 'session_number']
    
    def __str__(self):
        day_name = dict(self.DAY_CHOICES)[self.day_of_week]
        return f"{self.class_instance.name} - {day_name} {self.start_time.strftime('%I:%M %p')}"
    
    @property
    def duration_minutes(self):
        """Calculate session duration in minutes"""
        start = self.start_time
        end = self.end_time
        
        # Handle time calculation
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        
        if end_minutes < start_minutes:
            # Session spans midnight
            end_minutes += 24 * 60
        
        return end_minutes - start_minutes
    
    @property
    def formatted_schedule(self):
        """Get formatted schedule string"""
        day_name = dict(self.DAY_CHOICES)[self.day_of_week]
        start_str = self.start_time.strftime('%I:%M %p')
        end_str = self.end_time.strftime('%I:%M %p')
        return f"{day_name} {start_str} - {end_str}"




class ProjectPlatform(models.Model):
    """
    Defines different platforms where projects can be executed
    Each platform represents a specific development environment or tool
    """
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Internal name (e.g., 'scratch', 'replit')"
    )
    display_name = models.CharField(
        max_length=150,
        help_text="User-friendly display name (e.g., 'Scratch Programming Platform')"
    )
    description = models.TextField(
        help_text="Detailed description of the platform and its capabilities"
    )
    
    # Platform Type
    platform_type = models.CharField(
        max_length=50,
        help_text="Category of the platform (e.g., 'Visual Programming', 'Online IDE', 'Design Tool')"
    )
    
    # Technical Details
    base_url = models.URLField(
        help_text="Base URL of the platform (e.g., https://scratch.mit.edu)"
    )
    api_endpoint = models.URLField(
        blank=True,
        help_text="API endpoint for integration (if available)"
    )
    supported_languages = models.JSONField(
        default=list, 
        help_text="List of supported programming languages"
    )
    
    # Platform Capabilities
    requires_authentication = models.BooleanField(
        default=True,
        help_text="Does this platform require user authentication?"
    )
    supports_collaboration = models.BooleanField(
        default=False,
        help_text="Does this platform support real-time collaboration?"
    )
    supports_file_upload = models.BooleanField(
        default=True,
        help_text="Can users upload files to this platform?"
    )
    supports_live_preview = models.BooleanField(
        default=True,
        help_text="Does this platform support live preview of work?"
    )
    supports_version_control = models.BooleanField(
        default=False,
        help_text="Does this platform support version control/git?"
    )
    
    # Platform-specific settings
    platform_config = models.JSONField(
        default=dict,
        help_text="Platform-specific configuration and settings"
    )
    
    # Visual/UI
    icon = models.CharField(
        max_length=50,
        help_text="Icon identifier for UI display"
    )
    color = models.CharField(
        max_length=7,
        help_text="Hex color code for branding"
    )
    logo_url = models.URLField(
        blank=True,
        help_text="URL to platform logo image"
    )
    
    # Age and Skill Level
    min_age = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Minimum recommended age for this platform"
    )
    max_age = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum recommended age for this platform"
    )
    skill_levels = models.JSONField(
        default=list,
        help_text="Supported skill levels (e.g., ['beginner', 'intermediate', 'advanced'])"
    )
    
    # Status and Features
    is_active = models.BooleanField(
        default=True,
        help_text="Is this platform currently available?"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Should this platform be featured prominently?"
    )
    is_free = models.BooleanField(
        default=True,
        help_text="Is this platform free to use?"
    )
    
    # Usage Statistics
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this platform has been used"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_featured', 'display_name']
        indexes = [
            models.Index(fields=['platform_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return self.display_name
    
    @property
    def age_range_display(self):
        """Return formatted age range"""
        if self.min_age and self.max_age:
            return f"{self.min_age}-{self.max_age} years"
        elif self.min_age:
            return f"{self.min_age}+ years"
        elif self.max_age:
            return f"Up to {self.max_age} years"
        return "All ages"
    
    @property
    def capabilities_display(self):
        """Return list of platform capabilities"""
        capabilities = []
        if self.supports_collaboration:
            capabilities.append("Collaboration")
        if self.supports_file_upload:
            capabilities.append("File Upload")
        if self.supports_live_preview:
            capabilities.append("Live Preview")
        if self.supports_version_control:
            capabilities.append("Version Control")
        return capabilities
    
    def clean(self):
        """Validate platform data"""
        from django.core.exceptions import ValidationError
        
        # Validate age range
        if self.min_age and self.max_age and self.min_age > self.max_age:
            raise ValidationError("Minimum age cannot be greater than maximum age")
        
        # Validate color format
        if self.color and not self.color.startswith('#'):
            self.color = f"#{self.color}"
        
        # Validate platform config is a dict
        if not isinstance(self.platform_config, dict):
            raise ValidationError("Platform config must be a dictionary")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)





class ClassEvent(models.Model):
    """
    Individual events/sessions scheduled for a class
    """
    EVENT_TYPES = [
        ('lesson', 'Lesson'),
        ('meeting', 'Meeting'),
        ('project', 'Project'),
        ('break', 'Break'),
        ('test', 'Test'),
        ('exam', 'Exam'),
    ]
    
    MEETING_PLATFORMS = [
        ('jitsi', 'Jitsi Meet'),
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
    
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Associated project (if event type is project)"
    )
    project_platform = models.ForeignKey(
        ProjectPlatform,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Platform for project events"
    )
    
    assessment = models.ForeignKey(
        'CourseAssessment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Associated assessment (if event type is test or exam)"
    )
    
    # Project-specific fields (for project events)
    project_title = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Project title (cached for display purposes)"
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Project due date (for project events)"
    )
    submission_type = models.CharField(
        max_length=20,
        choices=[
            ('link', 'Link/URL'),
            ('image', 'Image'),
            ('video', 'Video'),
            ('audio', 'Audio'),
            ('file', 'File Upload'),
            ('note', 'Text Note'),
            ('code', 'Code'),
            ('presentation', 'Presentation'),
        ],
        blank=True,
        null=True,
        help_text="Expected submission type for project events"
    )

    # Event Details
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        default='lesson',
        help_text="Type of event"
    )
    start_time = models.DateTimeField(null=True, blank=True, help_text="Event start time")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Event end time")
    
    # Lesson Type (for lesson events)
    lesson_type = models.CharField(
        max_length=20,
        choices=[
            ('live', 'Live Lesson'),
            ('text', 'Text Lesson'),
            ('video', 'Video Lesson'),
            ('audio', 'Audio Lesson'),
            ('interactive', 'Interactive Lesson'),
        ],
        default='text',
        blank=True,
        null=True,
        help_text="Type of lesson (live, text, video, audio, interactive)"
    )
    
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
        
        # For non-project events (lesson, meeting, break, test, exam), validate start_time and end_time
        if self.event_type != 'project':
            if self.start_time and self.end_time:
                if self.end_time <= self.start_time:
                    raise ValidationError("End time must be after start time")
        
        if self.event_type == 'lesson' and not self.lesson:
            raise ValidationError("Lesson events must have an associated lesson")
        
        if self.event_type == 'project' and not self.project:
            raise ValidationError("Project events must have an associated project")
        
        if self.event_type == 'project' and not self.project_platform:
            raise ValidationError("Project events must specify a platform")
        
        # Validate assessment events (test and exam)
        if self.event_type in ['test', 'exam']:
            if not self.assessment:
                raise ValidationError("Assessment events must have an associated assessment")
            
            # Validate assessment belongs to same course as class
            if self.assessment and self.class_instance:
                if self.assessment.course != self.class_instance.course:
                    raise ValidationError("Assessment must belong to the same course as the class")
        
        # For project events, due_date is required
        if self.event_type == 'project' and not self.due_date:
            raise ValidationError("Due date is required for project events")
        
        # Validate project belongs to same course as class
        if self.event_type == 'project' and self.project and self.class_instance:
            if self.project.course != self.class_instance.course:
                raise ValidationError("Project must belong to the same course as the class")
        
        # Validate project-specific fields
        if self.event_type == 'project':
            if self.due_date and self.start_time and self.due_date < self.start_time:
                raise ValidationError("Due date cannot be before event start time")
            
            # If project_title is provided, it should not be empty
            if self.project_title is not None and not self.project_title.strip():
                raise ValidationError("Project title cannot be empty if provided")
        
        # Validate meeting details for live classes
        if self.event_type == 'lesson' and self.lesson and self.lesson.type == 'live_class':
            if self.meeting_link and not self.meeting_platform:
                raise ValidationError("Meeting platform is required when meeting link is provided")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# CourseIntroduction model completely removed - all fields are now in Course model
    



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
    parent_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Parent's name for testimonials (e.g., 'Sarah M.', 'Emily Chen')"
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





class ProjectSubmission(models.Model):
    STATUS = [
        ("ASSIGNED", "Assigned"),
        ("SUBMITTED", "Submitted"),
        ("RETURNED", "Returned"),
        ("GRADED", "Graded"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_submissions")

    status = models.CharField(max_length=20, choices=STATUS, default="ASSIGNED")
    content = models.TextField(blank=True, help_text="Submission content (text, notes, code)")
    file_url = models.URLField(blank=True, help_text="URL to uploaded file in cloud storage")
    reflection = models.TextField(blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    grader = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="graded_projects"
    )

    points_earned = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    feedback_response = models.TextField(blank=True, help_text="Student's response to teacher feedback")
    feedback_checked = models.BooleanField(default=False, help_text="Whether student has seen the feedback")
    feedback_checked_at = models.DateTimeField(null=True, blank=True, help_text="When student last checked feedback")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "student")
        ordering = ['-submitted_at', '-created_at']
    
    def __str__(self):
        return f"{self.student} - {self.project.title} ({self.status})"


class CourseAssessment(models.Model):
    """
    Course-level assessments (Tests and Exams)
    Both follow the same structure, differentiated by assessment_type
    """
    ASSESSMENT_TYPES = [
        ('test', 'Test'),
        ('exam', 'Exam'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assessments')
    assessment_type = models.CharField(max_length=10, choices=ASSESSMENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text="Instructions shown to students")
    
    # Assessment Configuration
    time_limit_minutes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Time limit in minutes (null = no limit)"
    )
    passing_score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum percentage to pass"
    )
    max_attempts = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of attempts allowed"
    )
    
    # Metadata
    order = models.IntegerField(default=0, help_text="Order within course")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_assessments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def total_points(self):
        return sum(question.points for question in self.questions.all())
    
    @property
    def question_count(self):
        return self.questions.count()
    
    class Meta:
        ordering = ['course', 'order', 'created_at']
        indexes = [
            models.Index(fields=['course', 'assessment_type']),
            models.Index(fields=['course', 'order']),
        ]
        verbose_name = "Course Assessment"
        verbose_name_plural = "Course Assessments"
    
    def __str__(self):
        return f"{self.get_assessment_type_display()}: {self.title} ({self.course.title})"


class CourseAssessmentQuestion(models.Model):
    """
    Questions within a course assessment (test/exam)
    Reuses question types from existing Question model
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
    assessment = models.ForeignKey(
        CourseAssessment,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    question_text = models.TextField(help_text="The question text")
    order = models.IntegerField(help_text="Question order within assessment")
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
        ordering = ['assessment', 'order']
        unique_together = ['assessment', 'order']
        indexes = [
            models.Index(fields=['assessment', 'order']),
        ]
        verbose_name = "Assessment Question"
        verbose_name_plural = "Assessment Questions"
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."
