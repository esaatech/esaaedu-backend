"""
Lead Magnet models: guides (PDF + preview) and submissions.
"""
import logging
from django.db import models
from django.core.files.storage import default_storage
from django.utils.text import slugify

logger = logging.getLogger(__name__)


def _default_benefits():
    return []


class LeadMagnet(models.Model):
    """
    A lead magnet guide: PDF, preview image, copy, and optional Brevo list.
    PDF and preview are stored in GCP at lead_magnets/{slug}/guide.pdf and
    lead_magnets/{slug}/preview.jpg (or uploaded extension).
    """
    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    benefits = models.JSONField(default=_default_benefits, blank=True)

    # GCP paths and URLs (set by admin on upload)
    pdf_file_name = models.CharField(max_length=500, blank=True)
    pdf_url = models.URLField(max_length=500, blank=True)
    preview_image_name = models.CharField(max_length=500, blank=True)
    preview_image_url = models.URLField(max_length=500, blank=True)

    brevo_list_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Brevo list ID to add contacts to on submission.",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead magnet'
        verbose_name_plural = 'Lead magnets'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            base = slugify(self.title)
            slug = base
            c = 1
            while LeadMagnet.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{c}'
                c += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete PDF and preview from GCP before deleting the model."""
        if self.pdf_file_name:
            try:
                if default_storage.exists(self.pdf_file_name):
                    default_storage.delete(self.pdf_file_name)
                    logger.info("Deleted lead magnet PDF from GCP: %s", self.pdf_file_name)
            except Exception as e:
                logger.exception("Error deleting lead magnet PDF from GCP: %s", e)
        if self.preview_image_name:
            try:
                if default_storage.exists(self.preview_image_name):
                    default_storage.delete(self.preview_image_name)
                    logger.info("Deleted lead magnet preview from GCP: %s", self.preview_image_name)
            except Exception as e:
                logger.exception("Error deleting lead magnet preview from GCP: %s", e)
        super().delete(*args, **kwargs)


class LeadMagnetSubmission(models.Model):
    """A submission for a lead magnet: first name, email, linked to the guide."""
    lead_magnet = models.ForeignKey(
        LeadMagnet,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    first_name = models.CharField(max_length=255)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead magnet submission'
        verbose_name_plural = 'Lead magnet submissions'
        # One submission per email per lead magnet
        unique_together = [['lead_magnet', 'email']]

    def __str__(self):
        return f"{self.email} — {self.lead_magnet.slug}"
