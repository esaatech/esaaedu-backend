"""
TutorX signals.

- On lesson delete: delete TutorX BlockNote images, interactive video (HLS), and event images from GCS.
- On lesson save (type tutorx): invalidate lesson chat cache so chat sees content updates.
"""
import logging

from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver

from courses.models import Lesson

from .models import InteractiveVideo, InteractiveEvent
from .services.storage import (
    delete_tutorx_images_from_content,
    collect_image_urls_from_blocknote_string,
    file_path_from_tutorx_image_url,
    delete_image_and_thumbnail,
)
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


def _delete_interactive_video_assets(interactive_video):
    """Delete HLS (AudioVideoMaterial) and all event images from GCS for an InteractiveVideo."""
    if getattr(interactive_video, "audio_video_material_id", None):
        try:
            av = interactive_video.audio_video_material
            if av:
                av.delete()
                logger.info(
                    "Deleted AudioVideoMaterial (HLS) for interactive_video %s",
                    interactive_video.id,
                )
        except Exception as e:
            logger.warning(
                "Failed to delete AudioVideoMaterial for interactive_video %s: %s",
                interactive_video.id,
                e,
            )
    for event in InteractiveEvent.objects.filter(interactive_video=interactive_video):
        for field in ("prompt", "explanation", "explanation_yes", "explanation_no", "model_answer"):
            val = getattr(event, field, None)
            if isinstance(val, str):
                for image_url in collect_image_urls_from_blocknote_string(val):
                    file_path = file_path_from_tutorx_image_url(image_url)
                    if file_path:
                        try:
                            delete_image_and_thumbnail(file_path)
                        except Exception as e:
                            logger.warning(
                                "Failed to delete event image from GCS %s: %s",
                                image_url[:80] if image_url else "",
                                e,
                            )


@receiver(pre_delete, sender=Lesson)
def delete_tutorx_images_on_lesson_delete(sender, instance, **kwargs):
    """
    When a Lesson is deleted, if it is a TutorX lesson:
    - Delete all images referenced in tutorx_content (BlockNote) from GCS.
    - If it has an InteractiveVideo, delete its HLS (AudioVideoMaterial) and all
      images in event prompt/explanation from GCS so nothing is orphaned.
    """
    if getattr(instance, "type", None) != "tutorx":
        return
    try:
        content = getattr(instance, "tutorx_content", None)
        if content and isinstance(content, str) and content.strip():
            delete_tutorx_images_from_content(content)
            logger.info("Deleted TutorX BlockNote images from GCS for lesson %s", instance.id)
    except Exception as e:
        logger.warning(
            "Failed to delete TutorX content images from GCS for lesson %s: %s",
            instance.id,
            e,
            exc_info=True,
        )
    try:
        interactive_video = InteractiveVideo.objects.filter(lesson=instance).first()
        if interactive_video:
            _delete_interactive_video_assets(interactive_video)
            logger.info(
                "Deleted interactive video (HLS) and event images from GCS for lesson %s",
                instance.id,
            )
    except Exception as e:
        logger.warning(
            "Failed to delete interactive video / event images from GCS for lesson %s: %s",
            instance.id,
            e,
            exc_info=True,
        )
