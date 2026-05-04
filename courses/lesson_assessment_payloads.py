"""
Shared payloads for lesson-linked quizzes and assignments (student + teacher views).
"""
from courses.models import QuizAttempt, AssignmentSubmission


def teacher_lesson_quiz_with_questions(quiz, lesson):
    """Full quiz dict with ordered questions and lesson context (teacher lesson_quiz GET)."""
    questions = quiz.questions.all().order_by('order')
    quiz_data = {
        'id': str(quiz.id),
        'title': quiz.title,
        'description': quiz.description or '',
        'time_limit': quiz.time_limit,
        'passing_score': quiz.passing_score,
        'max_attempts': quiz.max_attempts,
        'show_correct_answers': quiz.show_correct_answers,
        'randomize_questions': quiz.randomize_questions,
        'total_points': quiz.total_points,
        'question_count': quiz.question_count,
        'created_at': quiz.created_at.isoformat() if quiz.created_at else None,
        'updated_at': quiz.updated_at.isoformat() if quiz.updated_at else None,
        'questions': [],
    }
    for question in questions:
        quiz_data['questions'].append({
            'id': str(question.id),
            'question_text': question.question_text,
            'type': question.type,
            'points': question.points,
            'content': question.content,
            'explanation': question.explanation or '',
            'order': question.order,
            'created_at': question.created_at.isoformat() if question.created_at else None,
            'updated_at': question.updated_at.isoformat() if question.updated_at else None,
        })
    quiz_data['lesson'] = {
        'id': str(lesson.id),
        'title': lesson.title,
        'course': lesson.course.title,
        'type': lesson.type,
        'order': lesson.order,
    }
    return quiz_data


def student_lesson_quiz_detail(quiz, user):
    """Quiz block for student lesson detail API (questions + attempts)."""
    questions = quiz.questions.all().order_by('order')
    attempts = []
    if user.is_authenticated:
        attempts = list(
            QuizAttempt.objects.filter(
                student=user,
                quiz=quiz,
            ).order_by('-started_at')
        )
    return {
        'id': str(quiz.id),
        'title': quiz.title,
        'description': quiz.description or '',
        'time_limit': quiz.time_limit,
        'passing_score': quiz.passing_score,
        'max_attempts': quiz.max_attempts,
        'show_correct_answers': quiz.show_correct_answers,
        'randomize_questions': quiz.randomize_questions,
        'total_points': quiz.total_points,
        'question_count': quiz.question_count,
        'questions': [
            {
                'id': str(q.id),
                'question_text': q.question_text,
                'type': q.type,
                'content': q.content,
                'points': q.points,
                'explanation': q.explanation or '',
                'order': q.order,
            }
            for q in questions
        ],
        'user_attempts_count': len(attempts),
        'user_attempts': [
            {
                'id': str(attempt.id),
                'attempt_number': attempt.attempt_number,
                'score': float(attempt.score) if attempt.score else None,
                'points_earned': attempt.points_earned,
                'passed': attempt.passed,
                'answers': attempt.answers,
                'started_at': attempt.started_at.isoformat(),
                'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
                'is_teacher_graded': attempt.is_teacher_graded,
                'display_status': attempt.display_status,
            }
            for attempt in attempts
        ],
        'can_retake': len(attempts) < quiz.max_attempts if attempts else True,
        'has_passed': any(attempt.passed for attempt in attempts),
        'last_attempt': attempts[0].score if attempts else None,
        'last_attempt_passed': attempts[0].passed if attempts else None,
    }


def student_lesson_assignment_detail(assignment, user):
    """Assignment block for student lesson detail API."""
    questions = assignment.questions.all().order_by('order')
    submissions = []
    submission_data = None
    if user.is_authenticated:
        submissions = list(
            AssignmentSubmission.objects.filter(
                assignment=assignment,
                enrollment__student_profile__user=user,
            ).order_by('-submitted_at')
        )
        if submissions:
            latest_submission = submissions[0]
            submission_data = {
                'id': str(latest_submission.id),
                'attempt_number': latest_submission.attempt_number,
                'status': latest_submission.status,
                'submitted_at': latest_submission.submitted_at.isoformat(),
                'answers': latest_submission.answers,
                'is_graded': latest_submission.is_graded,
                'points_earned': latest_submission.points_earned,
                'points_possible': latest_submission.points_possible,
                'percentage': latest_submission.percentage,
                'passed': latest_submission.passed,
                'return_for_revision_count': getattr(latest_submission, 'return_for_revision_count', 0),
            }
    assignment_data = {
        'id': str(assignment.id),
        'title': assignment.title,
        'description': assignment.description or '',
        'assignment_type': assignment.assignment_type,
        'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
        'passing_score': assignment.passing_score,
        'max_attempts': assignment.max_attempts,
        'show_correct_answers': assignment.show_correct_answers,
        'randomize_questions': assignment.randomize_questions,
        'question_count': assignment.question_count,
        'submission_count': assignment.submissions.count(),
        'questions': [
            {
                'id': str(q.id),
                'question_text': q.question_text,
                'type': q.type,
                'content': q.content,
                'points': q.points,
                'explanation': q.explanation or '',
                'order': q.order,
            }
            for q in questions
        ],
        'user_submissions_count': len(submissions),
        'can_submit': len(submissions) < assignment.max_attempts if submissions else True,
        'has_passed': any(submission.passed for submission in submissions),
        'last_submission': submissions[0].submitted_at.isoformat() if submissions else None,
        'last_submission_passed': submissions[0].passed if submissions else None,
        'submission': submission_data,
    }
    if submissions:
        from student.views import _submission_has_return_feedback, _attach_return_feedback_to_questions

        latest = submissions[0]
        if _submission_has_return_feedback(latest):
            assignment_data['questions'] = _attach_return_feedback_to_questions(
                assignment_data['questions'], latest.return_feedback
            )
    return assignment_data
