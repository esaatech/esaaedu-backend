from django.db.models.signals import post_save
from django.dispatch import receiver
from courses.models import QuizAttempt, AssignmentSubmission


@receiver(post_save, sender=QuizAttempt)
def update_student_quiz_aggregates(sender, instance, **kwargs):
    """
    Update student profile quiz aggregates when a quiz attempt is completed/graded.
    This triggers recalculation of overall quiz averages across all courses.
    """
    if instance.completed_at and instance.score is not None:
        try:
            student_profile = instance.student.student_profile
            if student_profile:
                student_profile.recalculate_quiz_aggregates()
        except Exception as e:
            print(f"⚠️ Signal: Failed to update quiz aggregates for {instance.student.email}: {e}")


@receiver(post_save, sender=AssignmentSubmission)
def update_student_assignment_aggregates(sender, instance, **kwargs):
    """
    Update student profile assignment aggregates when an assignment is graded.
    This triggers recalculation of overall assignment averages across all courses.
    """
    if instance.is_graded and instance.percentage is not None:
        try:
            student_profile = instance.student.student_profile
            if student_profile:
                student_profile.recalculate_assignment_aggregates()
        except Exception as e:
            print(f"⚠️ Signal: Failed to update assignment aggregates for {instance.student.email}: {e}")

