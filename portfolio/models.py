from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import RegexValidator
from courses.models import ProjectSubmission

User = get_user_model()


class Portfolio(models.Model):
    """
    Student portfolio - one per student
    """
    student = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='portfolio',
        help_text="The student who owns this portfolio"
    )
    title = models.CharField(
        max_length=200,
        default="My Portfolio",
        help_text="Portfolio title"
    )
    bio = models.TextField(
        blank=True,
        help_text="Student's bio/about section"
    )
    profile_image = models.ImageField(
        null=True,
        blank=True,
        upload_to='portfolio/profiles/',
        help_text="Student's profile image"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Whether the portfolio is publicly accessible"
    )
    custom_url = models.SlugField(
        unique=True,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message='Custom URL can only contain lowercase letters, numbers, and hyphens'
            )
        ],
        help_text="Custom URL slug (e.g., 'john-doe')"
    )
    theme = models.CharField(
        max_length=50,
        default="default",
        help_text="Portfolio theme/style"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = "Portfolios"

    def __str__(self):
        return f"{self.student.get_full_name() or self.student.email}'s Portfolio"

    @property
    def public_url(self):
        """Get the public URL for this portfolio"""
        if self.custom_url:
            return f"/portfolio/{self.custom_url}"
        return f"/portfolio/{self.student.username or self.student.id}"

    def save(self, *args, **kwargs):
        # Auto-generate custom_url from username if not provided
        if not self.custom_url and self.student.username:
            base_url = self.student.username.lower().replace(' ', '-')
            # Ensure uniqueness
            counter = 1
            custom_url = base_url
            while Portfolio.objects.filter(custom_url=custom_url).exclude(pk=self.pk).exists():
                custom_url = f"{base_url}-{counter}"
                counter += 1
            self.custom_url = custom_url
        super().save(*args, **kwargs)


class PortfolioItem(models.Model):
    """
    Individual project in a student's portfolio
    Links to a ProjectSubmission but adds portfolio-specific metadata
    """
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="The portfolio this item belongs to"
    )
    project_submission = models.ForeignKey(
        ProjectSubmission,
        on_delete=models.CASCADE,
        related_name='portfolio_items',
        help_text="The project submission this portfolio item represents"
    )

    # Portfolio-specific fields
    title = models.CharField(
        max_length=200,
        help_text="Portfolio title (can override project title)"
    )
    description = models.TextField(
        help_text="Student-written portfolio description"
    )
    featured = models.BooleanField(
        default=False,
        help_text="Whether this item is featured (pinned to top)"
    )
    order = models.IntegerField(
        default=0,
        help_text="Custom ordering (lower numbers appear first)"
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Project category (e.g., 'Python', 'Web Development')"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of tags (e.g., ['OOP', 'APIs', 'React'])"
    )
    skills_demonstrated = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of skills (e.g., ['Problem Solving', 'UI/UX'])"
    )

    # Media
    thumbnail_image = models.ImageField(
        null=True,
        blank=True,
        upload_to='portfolio/thumbnails/',
        help_text="Custom thumbnail image for this portfolio item"
    )
    screenshots = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of screenshot URLs"
    )

    # Visibility
    is_visible = models.BooleanField(
        default=True,
        help_text="Whether this item is visible in the portfolio"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-featured', 'order', '-created_at']
        verbose_name_plural = "Portfolio Items"
        unique_together = ['portfolio', 'project_submission']  # Prevent duplicates

    def __str__(self):
        return f"{self.portfolio.student.get_full_name() or self.portfolio.student.email} - {self.title}"

    def clean(self):
        """Validate portfolio item data"""
        from django.core.exceptions import ValidationError

        # Ensure project submission belongs to the portfolio's student
        if self.project_submission.student != self.portfolio.student:
            raise ValidationError("Project submission must belong to the portfolio owner")

        # Ensure project submission is graded
        if self.project_submission.status != 'GRADED':
            raise ValidationError("Only graded project submissions can be added to portfolio")

    def save(self, *args, **kwargs):
        self.full_clean()  # Run validation
        super().save(*args, **kwargs)
