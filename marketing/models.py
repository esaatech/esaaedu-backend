from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.conf import settings
from django.core.files.storage import default_storage
import uuid
import logging

logger = logging.getLogger(__name__)


class Program(models.Model):
    """
    Marketing Program model for category/program landing pages.
    Programs can include specific courses or all courses from a category.
    """
    
    HERO_MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200,
        help_text="Program name (e.g., 'Math Program', 'Coding Program')"
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        help_text="SEO-friendly URL slug (auto-generated from name if not provided). This becomes the marketing URL path (e.g., 'math' → https://www.sbtyacedemy.com/math)"
    )
    description = models.TextField(
        help_text="Program description displayed on landing page"
    )
    
    # Hero Media
    hero_media = models.FileField(
        upload_to='marketing/programs/hero_media/',
        blank=True,
        null=True,
        help_text="Hero image or video file (uploaded to GCS automatically). Supports images (jpg, png, gif, webp) and videos (mp4, webm)."
    )
    hero_media_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        editable=False,
        help_text="GCS URL for hero media (auto-generated from hero_media file)"
    )
    hero_media_type = models.CharField(
        max_length=10,
        choices=HERO_MEDIA_TYPE_CHOICES,
        default='image',
        help_text="Type of hero media (image or video)"
    )
    
    # Hero Section Text Overlay
    hero_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Main headline displayed over hero media (e.g., 'LIVE ONLINE MATH PROGRAMS')"
    )
    hero_subtitle = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional subtitle or tagline displayed below hero title"
    )
    hero_features = models.JSONField(
        default=list,
        blank=True,
        help_text="List of features displayed in hero section (e.g., ['Canadian Curriculum', 'Small Groups', 'Real Results'])"
    )
    hero_value_propositions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of value propositions/marketing slogans (e.g., ['Build confidence. Improve results.', 'Track progress. Support your child's success.'])"
    )
    
    # Program Overview Section
    program_overview_features = models.JSONField(
        default=list,
        blank=True,
        help_text="List of program features with checkmarks for Program Overview section (e.g., ['Live Classes', 'Small Groups', 'Tests & Exams', 'Parent Reports', 'Canadian Curriculum'])"
    )
    
    # Trust Strip Section
    trust_strip_features = models.JSONField(
        default=list,
        blank=True,
        help_text="List of trust indicators for Trust Strip section (e.g., ['Live Classes', 'Small Groups', 'Tests & Exams', 'Parent Reports', 'Canadian Curriculum'])"
    )
    
    # Call to Action
    cta_text = models.CharField(
        max_length=200,
        default="Start Learning Today",
        help_text="Call-to-action button text"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this program is active and visible"
    )
    
    # Discount & Promotion
    discount_enabled = models.BooleanField(
        default=False,
        help_text="If True, users can enter a discount code (works with Stripe)"
    )
    promotion_message = models.TextField(
        blank=True,
        null=True,
        help_text="Promotion message to display on landing page"
    )
    promo_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Stripe promotion code"
    )
    
    # Course Selection (Mutually Exclusive)
    category = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="If set, loads all courses with this category (mutually exclusive with courses field)"
    )
    courses = models.ManyToManyField(
        'courses.Course',
        blank=True,
        related_name='programs',
        help_text="Specific courses to include (mutually exclusive with category field)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Program"
        verbose_name_plural = "Programs"
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """
        Validate that either category OR courses is set, but not both.
        Also validate hero_media file type if provided.
        Note: For ManyToMany fields, this validation should primarily happen in the form's clean() method
        since ManyToMany relationships aren't saved until after the model instance is saved.
        This method serves as a backup validation for existing instances.
        """
        super().clean()
        
        # Validate hero_media file type
        if self.hero_media:
            import os
            file_ext = os.path.splitext(self.hero_media.name)[1].lower()
            allowed_image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            allowed_video_exts = ['.mp4', '.webm', '.mov']
            allowed_exts = allowed_image_exts + allowed_video_exts
            
            if file_ext not in allowed_exts:
                raise ValidationError({
                    'hero_media': f'Invalid file type. Allowed types: {", ".join(allowed_exts)}'
                })
            
            # Auto-detect media type based on extension
            if file_ext in allowed_image_exts:
                self.hero_media_type = 'image'
            elif file_ext in allowed_video_exts:
                self.hero_media_type = 'video'
        
        has_category = bool(self.category and self.category.strip())
        
        # Check if courses are saved
        # IMPORTANT: For instances being created/edited in admin, the ManyToMany
        # courses aren't saved until save_related() is called. So if we have a PK
        # but no courses saved yet, we're likely in the middle of a form submission.
        # In that case, validation is handled by the form's clean() method.
        has_courses = False
        if self.pk:
            has_courses = self.courses.exists()
            
            # If instance has PK but no courses saved, we're likely in the middle
            # of a form submission where courses will be saved in save_related().
            # Skip validation here - it's handled by form.clean()
            if not has_courses and not has_category:
                return
        else:
            # New instance - validation handled by form
            return
        
        # Only validate if this is a fully saved instance with data
        # (not in the middle of a form submission)
        if has_category and has_courses:
            raise ValidationError({
                'category': 'Cannot set both category and courses. Choose one.',
                'courses': 'Cannot set both category and courses. Choose one.'
            })
        
        if not has_category and not has_courses:
            raise ValidationError({
                'category': 'Either category or courses must be set.',
                'courses': 'Either category or courses must be set.'
            })
    
    def save(self, *args, **kwargs):
        """
        Auto-generate slug from name if not provided.
        """
        
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Program.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        # Don't call full_clean() here - validation happens in form.clean()
        # Calling full_clean() would trigger model.clean() which can't access ManyToMany
        # for new instances. Validation is handled in the form.
        super().save(*args, **kwargs)
        
        # Auto-generate hero_media_url from hero_media file if it exists
        # Note: This is also handled in admin.save_model(), but we do it here
        # as a fallback for programmatic saves
        if self.hero_media and not self.hero_media_url:
            try:
                # Get the public URL from GCS
                self.hero_media_url = default_storage.url(self.hero_media.name)
                # Update without triggering save() again to avoid recursion
                Program.objects.filter(pk=self.pk).update(hero_media_url=self.hero_media_url)
            except Exception as e:
                logger.error(f"Error generating hero_media_url: {e}")
    
    def get_courses(self):
        """
        Returns courses for this program.
        - If category is set: Returns all published courses with that category (alphabetically ordered)
        - If courses ManyToMany is set: Returns those specific courses (alphabetically ordered)
        """
        from courses.models import Course
        
        if self.category:
            # Return all published courses with this category
            return Course.objects.filter(
                category=self.category,
                status='published'
            ).order_by('title')
        elif self.courses.exists():
            # Return specific courses from ManyToMany
            return self.courses.filter(status='published').order_by('title')
        else:
            # Fallback: return empty queryset
            return Course.objects.none()
    
    def get_seo_url(self, request=None):
        """
        Returns full SEO URL for this program.
        Example: https://www.sbtyacedemy.com/programs/math-program
        """
        if request:
            domain = request.build_absolute_uri('/').rstrip('/')
        else:
            # Default domain (can be configured in settings)
            domain = getattr(settings, 'FRONTEND_URL', 'https://www.sbtyacedemy.com')
        
        return f"{domain}/programs/{self.slug}"
    
    @property
    def course_count(self):
        """Returns the number of courses in this program."""
        from courses.models import Course
        
        # Count all courses assigned to this program (not just published ones)
        # This matches what the admin shows in the filter_horizontal widget
        if self.category:
            # If category is set, count all published courses in that category
            return Course.objects.filter(
                category=self.category,
                status='published'
            ).count()
        elif self.courses.exists():
            # If specific courses are set, count all of them (regardless of status)
            # This matches what you see in the admin filter_horizontal widget
            return self.courses.count()
        else:
            return 0

