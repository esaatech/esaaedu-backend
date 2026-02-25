"""
Admin for LeadMagnet and LeadMagnetSubmission.
Uploads PDF and preview image to GCP at lead_magnets/{slug}/guide.pdf and
lead_magnets/{slug}/preview.<ext>, saves paths and URLs on the model.
"""
import logging
import os
from django.contrib import admin
from django import forms
from django.core.files.storage import default_storage

from .models import LeadMagnet, LeadMagnetSubmission

logger = logging.getLogger(__name__)


class LeadMagnetAdminForm(forms.ModelForm):
    """Form with file uploads for PDF and preview; actual storage is in save_model."""
    pdf_upload = forms.FileField(
        required=False,
        label="PDF file",
        help_text="Upload or replace the guide PDF. Saved to GCP as lead_magnets/{slug}/guide.pdf",
    )
    preview_upload = forms.ImageField(
        required=False,
        label="Preview image",
        help_text="Upload or replace the preview image. Saved to GCP as lead_magnets/{slug}/preview.jpg (or .png)",
    )

    class Meta:
        model = LeadMagnet
        fields = [
            "slug",
            "title",
            "description",
            "benefits",
            "brevo_list_id",
            "is_active",
        ]


@admin.register(LeadMagnet)
class LeadMagnetAdmin(admin.ModelAdmin):
    form = LeadMagnetAdminForm
    list_display = ["title", "slug", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["title", "slug", "description"]
    readonly_fields = ["created_at", "updated_at", "pdf_file_name", "pdf_url", "preview_image_name", "preview_image_url"]
    prepopulated_fields = {"slug": ("title",)}

    fieldsets = (
        (None, {
            "fields": ("slug", "title", "description", "benefits", "is_active"),
        }),
        ("Files (upload to GCP)", {
            "description": "Upload PDF and preview image. They are saved to GCP at lead_magnets/{slug}/guide.pdf and lead_magnets/{slug}/preview.jpg",
            "fields": ("pdf_upload", "preview_upload", "pdf_file_name", "pdf_url", "preview_image_name", "preview_image_url"),
        }),
        ("Brevo", {
            "fields": ("brevo_list_id",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        slug = (form.cleaned_data.get("slug") or getattr(obj, "slug", "") or "").strip()
        if not slug and obj.title:
            from django.utils.text import slugify
            slug = slugify(obj.title)
        if not slug:
            super().save_model(request, obj, form, change)
            return

        # Save the instance first so we have pk and slug for paths
        super().save_model(request, obj, form, change)
        slug = obj.slug

        def _upload_to_gcp(file_field_value, path_prefix, default_ext):
            if not file_field_value:
                return None, None
            ext = os.path.splitext(getattr(file_field_value, "name", ""))[1].lower() or default_ext
            if ext and not ext.startswith("."):
                ext = "." + ext
            path = f"lead_magnets/{slug}/{path_prefix}{ext}"
            try:
                default_storage.delete(path)
            except Exception:
                pass
            saved_path = default_storage.save(path, file_field_value)
            url = default_storage.url(saved_path)
            return saved_path, url

        updated = False

        pdf_upload = form.cleaned_data.get("pdf_upload")
        if pdf_upload:
            old_path = obj.pdf_file_name
            saved_path, url = _upload_to_gcp(pdf_upload, "guide", ".pdf")
            if saved_path:
                if old_path and old_path != saved_path and default_storage.exists(old_path):
                    try:
                        default_storage.delete(old_path)
                    except Exception as e:
                        logger.exception("Error deleting old PDF: %s", e)
                obj.pdf_file_name = saved_path
                obj.pdf_url = url
                updated = True

        preview_upload = form.cleaned_data.get("preview_upload")
        if preview_upload:
            old_path = obj.preview_image_name
            saved_path, url = _upload_to_gcp(preview_upload, "preview", ".jpg")
            if saved_path:
                if old_path and old_path != saved_path and default_storage.exists(old_path):
                    try:
                        default_storage.delete(old_path)
                    except Exception as e:
                        logger.exception("Error deleting old preview: %s", e)
                obj.preview_image_name = saved_path
                obj.preview_image_url = url
                updated = True

        if updated:
            obj.save(update_fields=["pdf_file_name", "pdf_url", "preview_image_name", "preview_image_url"])

    def delete_model(self, request, obj):
        # Model.delete() already deletes GCP files; call it via instance delete
        obj.delete()


@admin.register(LeadMagnetSubmission)
class LeadMagnetSubmissionAdmin(admin.ModelAdmin):
    list_display = ["email", "first_name", "lead_magnet", "created_at"]
    list_filter = ["lead_magnet", "created_at"]
    search_fields = ["email", "first_name"]
    raw_id_fields = ["lead_magnet"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"
