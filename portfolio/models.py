from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
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
    theme = models.CharField(
        max_length=50,
        default="default",
        help_text="Portfolio theme/style"
    )

    # Sections: projects grid is on by default; external links opt-in
    projects_section_enabled = models.BooleanField(
        default=True,
        help_text="Show Projects section and nav anchor on public portfolio",
    )

    linkedin_enabled = models.BooleanField(default=False)
    linkedin_url = models.URLField(blank=True, default="")

    github_enabled = models.BooleanField(default=False)
    github_url = models.URLField(blank=True, default="")

    instagram_enabled = models.BooleanField(default=False)
    instagram_url = models.URLField(blank=True, default="")

    tiktok_enabled = models.BooleanField(default=False)
    tiktok_url = models.URLField(blank=True, default="")

    social_other_enabled = models.BooleanField(default=False)
    social_other_label = models.CharField(max_length=40, blank=True, default="")
    social_other_url = models.URLField(blank=True, default="")

    resume_enabled = models.BooleanField(default=False)
    resume_file = models.FileField(
        null=True,
        blank=True,
        upload_to="portfolio/resumes/",
        help_text="Resume PDF or document (uses default file storage / GCS when configured)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = "Portfolios"

    def __str__(self):
        return f"{self.student.get_full_name() or self.student.email}'s Portfolio"

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.linkedin_enabled and not (self.linkedin_url or "").strip():
            errors["linkedin_url"] = "URL is required when LinkedIn is enabled."
        if self.github_enabled and not (self.github_url or "").strip():
            errors["github_url"] = "URL is required when GitHub is enabled."
        if self.instagram_enabled and not (self.instagram_url or "").strip():
            errors["instagram_url"] = "URL is required when Instagram is enabled."
        if self.tiktok_enabled and not (self.tiktok_url or "").strip():
            errors["tiktok_url"] = "URL is required when TikTok is enabled."
        if self.social_other_enabled:
            if not (self.social_other_label or "").strip():
                errors["social_other_label"] = "Label is required for the custom link when enabled."
            if not (self.social_other_url or "").strip():
                errors["social_other_url"] = "URL is required when the custom link is enabled."
        if self.resume_enabled and not self.resume_file:
            errors["resume_file"] = "Upload a resume file when resume is enabled."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def public_url(self):
        """Public path: /portfolio/<student.public_handle>. Requires a non-empty public_handle."""
        h = getattr(self.student, 'public_handle', None)
        if h:
            return f"/portfolio/{h}"
        return ""


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
    demo_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Optional external link (hosted app, demo, GitHub Pages) shown as View project on public portfolio",
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
