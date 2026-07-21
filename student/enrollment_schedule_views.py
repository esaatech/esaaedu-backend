"""
API views for self-paced EnrollmentSchedule (Phase 1).
"""
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from student.models import EnrolledCourse, EnrollmentSchedule
from student.serializers import (
    EnrollmentScheduleListItemSerializer,
    EnrollmentScheduleSerializer,
)
from student.services.enrollment_schedule import regenerate_schedule_events


def resolve_schedule_student_user(user, student_profile_id=None):
    """
    Return the User whose enrollments and class events should appear on the schedule.
    Students and parents using student credentials use their own user.
    Dedicated parent accounts resolve linked children via parent_email.
    """
    if not user or not user.is_authenticated:
        return None
    if user.role == 'student':
        return user
    student_profile = getattr(user, 'student_profile', None)
    if student_profile:
        return user
    if getattr(user, 'is_parent', False):
        from users.models import StudentProfile

        parent_email = (user.email or '').strip()
        if not parent_email:
            return None
        if student_profile_id:
            linked = (
                StudentProfile.objects.filter(
                    id=student_profile_id,
                    parent_email__iexact=parent_email,
                )
                .select_related('user')
                .first()
            )
            return linked.user if linked else None
        children = StudentProfile.objects.filter(parent_email__iexact=parent_email).select_related(
            'user'
        )
        if children.count() == 1:
            return children.first().user
        return None
    return None


def _user_can_manage_enrollment(user, enrollment: EnrolledCourse) -> bool:
    """Teacher of the course, enrolled student, or parent using student credentials."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_teacher', False) and enrollment.course.teacher_id == user.id:
        return True
    student_user = enrollment.student_profile.user
    if user.id == student_user.id:
        return True
    # Parent accounts that share student credentials / student_profile
    if getattr(user, 'is_parent', False):
        parent_email = (enrollment.student_profile.parent_email or '').lower()
        if parent_email and parent_email == (user.email or '').lower():
            return True
        # Current product: parents often use student credentials
        if hasattr(user, 'student_profile') and user.student_profile_id == enrollment.student_profile_id:
            return True
    return False


def _ensure_self_paced(enrollment: EnrolledCourse):
    if enrollment.course.delivery_type != 'self_paced':
        return Response(
            {
                'error': 'Enrollment schedules are only available for self-paced courses',
                'delivery_type': enrollment.course.delivery_type,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


class SelfPacedEnrollmentScheduleListView(APIView):
    """
    GET /api/student/self-paced-schedules/
    List active self-paced enrollments for the current user (student/parent credentials)
    or for a student_id query param when the requester is the course teacher.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        student_id = request.query_params.get('student_id')
        qs = EnrolledCourse.objects.filter(
            course__delivery_type='self_paced',
            status='active',
        ).select_related('course', 'student_profile__user', 'schedule')

        if student_id and getattr(request.user, 'is_teacher', False):
            qs = qs.filter(
                student_profile_id=student_id,
                course__teacher=request.user,
            )
        else:
            student_profile = getattr(request.user, 'student_profile', None)
            if student_profile:
                qs = qs.filter(student_profile=student_profile)
            elif getattr(request.user, 'is_parent', False):
                parent_email = (request.user.email or '').strip()
                if not parent_email:
                    return Response(
                        {'error': 'Parent email not found'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                qs = qs.filter(student_profile__parent_email__iexact=parent_email)
                student_profile_id = request.query_params.get('student_profile_id')
                if student_profile_id:
                    qs = qs.filter(student_profile_id=student_profile_id)
            else:
                return Response(
                    {'error': 'Student profile not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        data = EnrollmentScheduleListItemSerializer(qs, many=True).data
        return Response({'results': data}, status=status.HTTP_200_OK)


class EnrollmentScheduleDetailView(APIView):
    """
    GET/PUT /api/student/enrolled-courses/<enrollment_id>/schedule/
    Read or create/update cadence; PUT regenerates upcoming ClassEvents.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_enrollment(self, enrollment_id):
        return get_object_or_404(
            EnrolledCourse.objects.select_related('course', 'student_profile__user', 'schedule'),
            id=enrollment_id,
        )

    def get(self, request, enrollment_id):
        enrollment = self.get_enrollment(enrollment_id)
        if not _user_can_manage_enrollment(request.user, enrollment):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        err = _ensure_self_paced(enrollment)
        if err:
            return err
        schedule = None
        try:
            schedule = enrollment.schedule
        except EnrollmentSchedule.DoesNotExist:
            schedule = None
        if schedule is None:
            return Response(
                {'error': 'No schedule set yet', 'enrollment_id': str(enrollment.id)},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(EnrollmentScheduleSerializer(schedule).data, status=status.HTTP_200_OK)

    def put(self, request, enrollment_id):
        enrollment = self.get_enrollment(enrollment_id)
        if not _user_can_manage_enrollment(request.user, enrollment):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        err = _ensure_self_paced(enrollment)
        if err:
            return err

        schedule = None
        try:
            schedule = enrollment.schedule
        except EnrollmentSchedule.DoesNotExist:
            schedule = None
        serializer = EnrollmentScheduleSerializer(
            instance=schedule,
            data=request.data,
            partial=False,
        )
        serializer.is_valid(raise_exception=True)

        if schedule is None:
            schedule = EnrollmentSchedule(enrollment=enrollment)
        for field, value in serializer.validated_data.items():
            setattr(schedule, field, value)
        schedule.updated_by = request.user
        schedule.save()

        try:
            created = regenerate_schedule_events(schedule)
        except Exception as exc:
            return Response(
                {'error': 'Failed to generate schedule events', 'details': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        out = EnrollmentScheduleSerializer(schedule).data
        out['events_generated'] = created
        return Response(out, status=status.HTTP_200_OK)

    def patch(self, request, enrollment_id):
        enrollment = self.get_enrollment(enrollment_id)
        if not _user_can_manage_enrollment(request.user, enrollment):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        err = _ensure_self_paced(enrollment)
        if err:
            return err

        try:
            schedule = enrollment.schedule
        except EnrollmentSchedule.DoesNotExist:
            return Response(
                {'error': 'No schedule set yet; use PUT to create one'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EnrollmentScheduleSerializer(
            instance=schedule,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(schedule, field, value)
        schedule.updated_by = request.user
        schedule.save()

        try:
            created = regenerate_schedule_events(schedule)
        except Exception as exc:
            return Response(
                {'error': 'Failed to generate schedule events', 'details': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        out = EnrollmentScheduleSerializer(schedule).data
        out['events_generated'] = created
        return Response(out, status=status.HTTP_200_OK)
