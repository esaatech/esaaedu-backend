"""
Signals for marketing app to handle file cleanup.
"""
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.files.storage import default_storage
import logging
from .models import Program

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Program)
def delete_program_hero_media(sender, instance, **kwargs):
    """
    Delete hero_media file from GCS when Program is deleted.
    """
    if instance.hero_media:
        try:
            if default_storage.exists(instance.hero_media.name):
                default_storage.delete(instance.hero_media.name)
                logger.info(f"Deleted hero_media from GCS: {instance.hero_media.name}")
        except Exception as e:
            logger.error(f"Error deleting hero_media from GCS: {e}")







