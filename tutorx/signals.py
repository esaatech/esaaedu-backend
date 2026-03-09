"""
TutorX signals.

- On lesson delete: delete TutorX images from GCS.
- On lesson save (type tutorx): invalidate lesson chat cache so chat sees content updates.
"""
import logging

from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver

from courses.models import Lesson

from .services.storage import delete_tutorx_images_from_content
from .services.lesson_chat import invalidate_lesson_chat_cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Lesson)
def invalidate_lesson_chat_cache_on_save(sender, instance, **kwargs):
    """When a TutorX lesson is saved, invalidate its chat context cache."""
    if getattr(instance, "type", None) != "tutorx":
        return
    try:
        invalidate_lesson_chat_cache(instance.id)
    except Exception as e:
        logger.warning("Failed to invalidate lesson chat cache for lesson %s: %s", instance.id, e)


@receiver(pre_delete, sender=Lesson)
def delete_tutorx_images_on_lesson_delete(sender, instance, **kwargs):
    """
    When a Lesson is deleted, if it is a TutorX lesson with content,
    delete all images referenced in tutorx_content from GCS.
    """
    if getattr(instance, "type", None) != "tutorx":
        return
    content = getattr(instance, "tutorx_content", None)
    if not content or not (isinstance(content, str) and content.strip()):
        return
    try:
        delete_tutorx_images_from_content(content)
        logger.info("Deleted TutorX images from GCS for lesson %s", instance.id)
    except Exception as e:
        logger.warning(
            "Failed to delete TutorX images from GCS for lesson %s: %s",
            instance.id,
            e,
            exc_info=True,
        )
