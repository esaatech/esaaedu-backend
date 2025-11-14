from django.db.models.signals import post_save
from django.dispatch import receiver
from courses.models import QuizAttempt, AssignmentSubmission


@receiver(post_save, sender=QuizAttempt)
def update_student_quiz_aggregates(sender, instance, **kwargs):
    """
    Update student profile quiz aggregates when a quiz attempt is completed/graded.
    This triggers recalculation of overall quiz averages across all courses.
    Also updates weekly performance aggregates.
    """
    if instance.completed_at and instance.score is not None:
        try:
            student_profile = instance.student.student_profile
            if student_profile:
                # Update overall aggregates
                student_profile.recalculate_quiz_aggregates()
                
                # Update weekly performance for the week of completion
                # Only update if the table exists (migration has been run)
                try:
                    from users.models import StudentWeeklyPerformance
                    StudentWeeklyPerformance.update_weekly_performance(
                        student_profile,
                        instance.completed_at
                    )
                except Exception as weekly_error:
                    # Silently fail if table doesn't exist yet (migration not run)
                    # This prevents errors during app startup or before migration
                    pass
        except Exception as e:
            print(f"⚠️ Signal: Failed to update quiz aggregates for {instance.student.email}: {e}")


@receiver(post_save, sender=AssignmentSubmission)
def update_student_assignment_aggregates(sender, instance, **kwargs):
    """
    Update student profile assignment aggregates when an assignment is graded.
    This triggers recalculation of overall assignment averages across all courses.
    Also updates weekly performance aggregates.
    """
    if instance.is_graded and instance.percentage is not None:
        try:
            student_profile = instance.student.student_profile
            if student_profile:
                # Update overall aggregates
                student_profile.recalculate_assignment_aggregates()
                
                # Update weekly performance for the week of grading/submission
                # Only update if the table exists (migration has been run)
                try:
                    from users.models import StudentWeeklyPerformance
                    # Use graded_at if available, otherwise submitted_at
                    completion_date = instance.graded_at or instance.submitted_at
                    if completion_date:
                        StudentWeeklyPerformance.update_weekly_performance(
                            student_profile,
                            completion_date
                        )
                except Exception as weekly_error:
                    # Silently fail if table doesn't exist yet (migration not run)
                    # This prevents errors during app startup or before migration
                    pass
        except Exception as e:
            print(f"⚠️ Signal: Failed to update assignment aggregates for {instance.student.email}: {e}")

