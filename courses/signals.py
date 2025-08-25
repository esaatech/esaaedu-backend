from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Course, CourseIntroduction


@receiver(post_save, sender=Course)
def sync_course_to_introduction(sender, instance, created, **kwargs):
    """
    Sync Course changes to CourseIntroduction when Course is updated
    """
    if not created:  # Only sync on updates, not creation
        try:
            introduction = CourseIntroduction.objects.get(course=instance)
            
            # Update introduction fields with course data
            introduction.overview = instance.long_description or instance.description
            introduction.max_students = instance.max_students
            introduction.learning_objectives = instance.features or []
            
            introduction.save()
            print(f"🔄 Signal: Synced course changes to introduction for {instance.title}")
            
        except CourseIntroduction.DoesNotExist:
            # Introduction doesn't exist yet - will be created on first access
            print(f"🔄 Signal: No introduction to sync for {instance.title}")
        except Exception as e:
            print(f"⚠️ Signal: Failed to sync course to introduction: {e}")


@receiver(post_save, sender=CourseIntroduction)
def sync_introduction_to_course(sender, instance, created, **kwargs):
    """
    Sync CourseIntroduction changes to Course when CourseIntroduction is updated
    """
    if not created:  # Only sync on updates, not creation
        try:
            course = instance.course
            
            # Update course fields with introduction data
            course.long_description = instance.overview
            course.max_students = instance.max_students
            course.features = instance.learning_objectives
            
            # Temporarily disconnect this signal to avoid infinite loop
            post_save.disconnect(sync_course_to_introduction, sender=Course)
            course.save()
            post_save.connect(sync_course_to_introduction, sender=Course)
            
            print(f"🔄 Signal: Synced introduction changes to course {course.title}")
            
        except Exception as e:
            print(f"⚠️ Signal: Failed to sync introduction to course: {e}")
