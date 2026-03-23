"""
Pending submission counts for teacher dashboards (mirror assignment semantics).

Assignment reference: status='submitted' and is_graded=False (lesson-scoped via assignment).

Assessments: status in ('submitted', 'auto_submitted') and is_graded=False, split by assessment_type.

Projects: status='SUBMITTED' only (exclude RETURNED waiting on student; exclude GRADED).
"""
from __future__ import annotations

def pending_assignment_count_for_teacher(teacher):
    from courses.models import AssignmentSubmission

    return AssignmentSubmission.objects.filter(
        assignment__lessons__course__teacher=teacher,
        status="submitted",
        is_graded=False,
    ).count()


def pending_test_submission_count_for_teacher(teacher):
    from courses.models import CourseAssessmentSubmission

    return CourseAssessmentSubmission.objects.filter(
        assessment__course__teacher=teacher,
        assessment__assessment_type="test",
        status__in=["submitted", "auto_submitted"],
        is_graded=False,
    ).count()


def pending_exam_submission_count_for_teacher(teacher):
    from courses.models import CourseAssessmentSubmission

    return CourseAssessmentSubmission.objects.filter(
        assessment__course__teacher=teacher,
        assessment__assessment_type="exam",
        status__in=["submitted", "auto_submitted"],
        is_graded=False,
    ).count()


def pending_project_submission_count_for_teacher(teacher):
    from courses.models import ProjectSubmission

    return ProjectSubmission.objects.filter(
        project__course__teacher=teacher,
        status="SUBMITTED",
    ).count()


def pending_assignment_count_for_enrollment(student_user, course):
    from courses.models import AssignmentSubmission

    return AssignmentSubmission.objects.filter(
        student=student_user,
        assignment__lessons__course=course,
        status="submitted",
        is_graded=False,
    ).count()


def pending_test_submission_count_for_enrollment(student_user, course):
    from courses.models import CourseAssessmentSubmission

    return CourseAssessmentSubmission.objects.filter(
        student=student_user,
        assessment__course=course,
        assessment__assessment_type="test",
        status__in=["submitted", "auto_submitted"],
        is_graded=False,
    ).count()


def pending_exam_submission_count_for_enrollment(student_user, course):
    from courses.models import CourseAssessmentSubmission

    return CourseAssessmentSubmission.objects.filter(
        student=student_user,
        assessment__course=course,
        assessment__assessment_type="exam",
        status__in=["submitted", "auto_submitted"],
        is_graded=False,
    ).count()


def pending_project_submission_count_for_enrollment(student_user, course):
    from courses.models import ProjectSubmission

    return ProjectSubmission.objects.filter(
        student=student_user,
        project__course=course,
        status="SUBMITTED",
    ).count()
