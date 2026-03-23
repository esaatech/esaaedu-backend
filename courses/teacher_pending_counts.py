"""
Pending submission counts for teacher dashboards (mirror assignment semantics).

Assignment reference: status='submitted' and is_graded=False (lesson-scoped via assignment).

Assessments: status in ('submitted', 'auto_submitted') and is_graded=False, split by assessment_type.
Only the **latest attempt** per (student, assessment) counts. Older attempts remain in the DB when
students retake; the teacher list API also shows only the latest attempt per assessment, so badges
must match that scope (avoids inflated counts from superseded attempts).

Projects: status='SUBMITTED' only (exclude RETURNED waiting on student; exclude GRADED).
"""
from __future__ import annotations

from django.db.models import Max, Q


def _count_pending_latest_assessment_submissions(base_qs, group_fields: tuple[str, ...]) -> int:
    """
    Restrict to rows whose (attempt_number) is the max for each group (e.g. per assessment or per
    student+assessment), then apply pending (submitted/ungraded) filters.
    """
    agg = list(base_qs.values(*group_fields).annotate(max_att=Max("attempt_number")))
    if not agg:
        return 0

    q = Q()
    for row in agg:
        part = Q(
            **{
                **{f: row[f] for f in group_fields},
                "attempt_number": row["max_att"],
            }
        )
        q |= part

    return (
        base_qs.filter(q)
        .filter(status__in=["submitted", "auto_submitted"], is_graded=False)
        .count()
    )


def pending_assignment_count_for_teacher(teacher):
    from courses.models import AssignmentSubmission

    return AssignmentSubmission.objects.filter(
        assignment__lessons__course__teacher=teacher,
        status="submitted",
        is_graded=False,
    ).count()


def pending_test_submission_count_for_teacher(teacher):
    from courses.models import CourseAssessmentSubmission

    base = CourseAssessmentSubmission.objects.filter(
        assessment__course__teacher=teacher,
        assessment__assessment_type="test",
    )
    return _count_pending_latest_assessment_submissions(base, ("student", "assessment"))


def pending_exam_submission_count_for_teacher(teacher):
    from courses.models import CourseAssessmentSubmission

    base = CourseAssessmentSubmission.objects.filter(
        assessment__course__teacher=teacher,
        assessment__assessment_type="exam",
    )
    return _count_pending_latest_assessment_submissions(base, ("student", "assessment"))


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

    base = CourseAssessmentSubmission.objects.filter(
        student=student_user,
        assessment__course=course,
        assessment__assessment_type="test",
    )
    return _count_pending_latest_assessment_submissions(base, ("assessment",))


def pending_exam_submission_count_for_enrollment(student_user, course):
    from courses.models import CourseAssessmentSubmission

    base = CourseAssessmentSubmission.objects.filter(
        student=student_user,
        assessment__course=course,
        assessment__assessment_type="exam",
    )
    return _count_pending_latest_assessment_submissions(base, ("assessment",))


def pending_project_submission_count_for_enrollment(student_user, course):
    from courses.models import ProjectSubmission

    return ProjectSubmission.objects.filter(
        student=student_user,
        project__course=course,
        status="SUBMITTED",
    ).count()
