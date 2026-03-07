"""
TutorX signals.

Ensures TutorX images in GCS are deleted when a lesson is deleted.
"""
import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from courses.models import Lesson

from .services.storage import delete_tutorx_images_from_content

logger = logging.getLogger(__name__)


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
