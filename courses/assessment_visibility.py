"""
Helpers for teacher-controlled visibility of quizzes and assignments on student-facing APIs.
"""
from courses.models import QuizAttempt, AssignmentSubmission


def quiz_visible_for_student_payload(quiz, user):
    """
    Include quiz in student lesson payloads when visible_to_students is True,
    or when the student has any attempt for this quiz (so they retain access / history).
    """
    if getattr(quiz, 'visible_to_students', True):
        return True
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return QuizAttempt.objects.filter(student=user, quiz=quiz).exists()


def assignment_visible_for_student_payload(assignment, user):
    """
    Include assignment when visible_to_students is True, or when the student has
    any submission row for this assignment (including drafts / returned).
    """
    if getattr(assignment, 'visible_to_students', True):
        return True
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return AssignmentSubmission.objects.filter(
        assignment=assignment,
        enrollment__student_profile__user=user,
    ).exists()
