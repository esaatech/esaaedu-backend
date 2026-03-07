"""
Phase 2 scheduling: one class per task, well-defined functions.
Determines per student: schedule | remind | skip (no side effects).
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone as django_tz

# Lazy imports to avoid circular / heavy imports at module load
def _student_profile_model():
    from users.models import StudentProfile
    return StudentProfile


def _enrolled_course_model():
    from student.models import EnrolledCourse
    return EnrolledCourse


def _class_model():
    from courses.models import Class
    return Class


def _class_event_model():
    from courses.models import ClassEvent
    return ClassEvent


def _lesson_model():
    from courses.models import Lesson
    return Lesson


def _module_model():
    from courses.models import Module
    return Module


class SchedulingChecker:
    """
    Hourly scheduling logic: for students at local midnight, determine
    schedule | remind | skip. No side effects (no sending, no calendar).
    """

    def __init__(self, now_utc=None):
        self.now_utc = now_utc or django_tz.now()
        if self.now_utc.tzinfo is None:
            self.now_utc = django_tz.make_aware(self.now_utc)

    # --- Timezone and student selection ---

    def get_timezones_at_midnight(self):
        """
        Return set of IANA timezone names where local time is in the first hour (00:00–00:59).
        Uses self.now_utc.
        """
        from zoneinfo import available_timezones
        out = set()
        for tz_name in available_timezones():
            try:
                z = ZoneInfo(tz_name)
                local = self.now_utc.astimezone(z)
                if local.hour == 0:
                    out.add(tz_name)
            except Exception:
                continue
        return out

    def get_students_in_timezones(self, timezone_names):
        """
        Return StudentProfile queryset for students whose timezone is in timezone_names
        and timezone is non-empty.
        """
        StudentProfile = _student_profile_model()
        return StudentProfile.objects.filter(
            timezone__in=timezone_names
        ).exclude(
            timezone=''
        ).select_related('user')

    # --- Enrollment and class (one class per course) ---

    def get_enrollments_for_student(self, student_profile):
        """Return active enrollments for this student (one per course)."""
        EnrolledCourse = _enrolled_course_model()
        return EnrolledCourse.objects.filter(
            student_profile=student_profile,
            status='active'
        ).select_related('course')

    def get_class_for_enrollment(self, enrollment):
        """
        Return the single Class for this enrollment (student is in class, same course).
        One class per course; None if not in any class.
        """
        Class = _class_model()
        user = enrollment.student_profile.user
        return Class.objects.filter(
            course=enrollment.course,
            students=user,
            is_active=True
        ).first()

    # --- Last / next class event ---

    def get_last_class_event(self, class_obj):
        """Return the most recent past ClassEvent for this class, or None."""
        ClassEvent = _class_event_model()
        return ClassEvent.objects.filter(
            class_instance=class_obj,
            start_time__lt=self.now_utc
        ).order_by('-start_time').select_related('lesson', 'assessment').first()

    def get_next_class_event(self, class_obj):
        """Return the next future ClassEvent for this class, or None."""
        ClassEvent = _class_event_model()
        return ClassEvent.objects.filter(
            class_instance=class_obj,
            start_time__gt=self.now_utc
        ).order_by('start_time').select_related('lesson', 'assessment').first()

    # --- Lesson / module helpers ---

    def is_lesson_last_in_module(self, lesson):
        """True if this lesson is the last lesson in its module (by order)."""
        if not lesson or not lesson.module_id:
            return False
        Module = _module_model()
        Lesson = _lesson_model()
        last_in_module = Lesson.objects.filter(module_id=lesson.module_id).order_by('-order').first()
        return last_in_module and last_in_module.id == lesson.id

    def get_lesson_before_test(self, class_event):
        """
        For a test/exam ClassEvent, return the last lesson of the module this test concludes.
        Uses assessment.module when set; otherwise falls back to order-based inference.
        """
        if not class_event or class_event.event_type not in ('test', 'exam') or not class_event.assessment_id:
            return None
        assessment = class_event.assessment
        Lesson = _lesson_model()
        # Prefer explicit module link (get test based on module)
        if getattr(assessment, 'module_id', None):
            module = assessment.module
            if module:
                return Lesson.objects.filter(module=module).order_by('-order').first()
        # Fallback: infer module by assessment order (assessment order 1 = after module 1)
        course = assessment.course
        Module = _module_model()
        modules = list(Module.objects.filter(course=course).order_by('order'))
        if not modules:
            return None
        idx = max(0, (assessment.order or 1) - 1)
        if idx >= len(modules):
            idx = len(modules) - 1
        module = modules[idx]
        return Lesson.objects.filter(module=module).order_by('-order').first()

    def get_test_for_module(self, class_obj, module):
        """
        Return the ClassEvent (test) for this module in this class, if any.
        Uses CourseAssessment.module when set; otherwise matches by order.
        """
        if not class_obj or not module:
            return None
        ClassEvent = _class_event_model()
        from courses.models import CourseAssessment
        # Prefer: assessment linked to this module
        assessment = CourseAssessment.objects.filter(
            course=class_obj.course,
            assessment_type='test',
            module=module,
        ).first()
        if assessment:
            return ClassEvent.objects.filter(
                class_instance=class_obj,
                assessment=assessment,
                event_type__in=('test', 'exam'),
            ).order_by('start_time').first()
        # Fallback: same order as module (module order 1 -> first test)
        assessments = list(
            CourseAssessment.objects.filter(
                course=class_obj.course,
                assessment_type='test',
            ).order_by('order')
        )
        if not assessments:
            return None
        idx = min(module.order - 1 if getattr(module, 'order', None) else 0, len(assessments) - 1)
        idx = max(0, idx)
        assessment = assessments[idx]
        return ClassEvent.objects.filter(
            class_instance=class_obj,
            assessment=assessment,
            event_type__in=('test', 'exam'),
        ).order_by('start_time').first()

    # --- Quiz / assignment completion for a lesson ---

    def is_lesson_quiz_completed(self, enrollment, lesson):
        """True if the lesson has no quiz, or enrollment has passed the quiz for this lesson."""
        from student.models import StudentLessonProgress
        from courses.models import Quiz
        if not lesson:
            return True
        progress = StudentLessonProgress.objects.filter(
            enrollment=enrollment,
            lesson=lesson
        ).first()
        if progress and progress.quiz_passed:
            return True
        quiz = Quiz.objects.filter(lessons=lesson).first()
        if not quiz:
            return True
        from courses.models import QuizAttempt
        return QuizAttempt.objects.filter(
            enrollment=enrollment,
            quiz=quiz,
            passed=True,
            completed_at__isnull=False
        ).exists()

    def is_lesson_assignment_completed(self, enrollment, lesson):
        """True if the lesson has no assignment, or enrollment has a submitted/graded submission."""
        from courses.models import Assignment, AssignmentSubmission
        if not lesson:
            return True
        assignment = Assignment.objects.filter(lessons=lesson).first()
        if not assignment:
            return True
        return AssignmentSubmission.objects.filter(
            enrollment=enrollment,
            assignment=assignment
        ).filter(status__in=('submitted', 'graded')).exists()

    def is_lesson_requirements_met(self, enrollment, lesson):
        """True if both quiz and assignment for this lesson are completed."""
        return (
            self.is_lesson_quiz_completed(enrollment, lesson) and
            self.is_lesson_assignment_completed(enrollment, lesson)
        )

    # --- 24h rule ---

    def is_next_event_within_24h(self, next_event, student_timezone):
        """True if next_event.start_time is within 24 hours from now in student's timezone."""
        if not next_event or not next_event.start_time:
            return False
        try:
            z = ZoneInfo(student_timezone)
        except Exception:
            return False
        now_local = self.now_utc.astimezone(z)
        start_local = next_event.start_time.astimezone(z)
        delta = start_local - now_local
        return timedelta(0) <= delta <= timedelta(hours=24)

    # --- High-level decision ---

    def get_next_schedulable_event(self, class_obj, last_event, enrollment):
        """
        Determine what should be scheduled next: a ClassEvent (lesson or test) or None.
        Does not check 24h; caller uses is_next_event_within_24h.
        Returns (event_or_none, reason_string).
        """
        ClassEvent = _class_event_model()
        Lesson = _lesson_model()

        if not last_event:
            # No last event: schedule first lesson (first event of the class)
            next_ev = self.get_next_class_event(class_obj)
            if next_ev:
                return next_ev, 'first_lesson'
            return None, 'no_events'

        if last_event.event_type in ('test', 'exam'):
            # Last was test: check lesson before test; then next = next lesson (first of next module)
            lesson_before = self.get_lesson_before_test(last_event)
            if not self.is_lesson_requirements_met(enrollment, lesson_before):
                return None, 'remind_lesson_before_test'
            next_ev = self.get_next_class_event(class_obj)
            return next_ev, 'next_lesson_after_test'

        # Last was a lesson
        lesson = last_event.lesson
        if not self.is_lesson_requirements_met(enrollment, lesson):
            return None, 'remind_lesson'

        if self.is_lesson_last_in_module(lesson):
            # Schedule module test: get test for this module (module-based)
            next_ev = self.get_test_for_module(class_obj, lesson.module)
            if next_ev:
                return next_ev, 'module_test'
            # No test linked to module; fall back to chronologically next event
            next_ev = self.get_next_class_event(class_obj)
            return next_ev, 'module_test'
        next_ev = self.get_next_class_event(class_obj)
        return next_ev, 'next_lesson'

    def run_for_student(self, student_profile):
        """
        Run the full flow for one student. Returns list of dicts, one per enrollment:
        { enrollment, class, last_event, next_event, decision: 'schedule'|'remind'|'skip', reason }
        """
        results = []
        enrollments = self.get_enrollments_for_student(student_profile)
        tz_name = (student_profile.timezone or '').strip()
        if not tz_name:
            return results

        for enrollment in enrollments:
            class_obj = self.get_class_for_enrollment(enrollment)
            if not class_obj:
                results.append({
                    'enrollment': enrollment,
                    'class': None,
                    'last_event': None,
                    'next_event': None,
                    'decision': 'skip',
                    'reason': 'no_class',
                })
                continue

            last_event = self.get_last_class_event(class_obj)
            next_event, reason = self.get_next_schedulable_event(class_obj, last_event, enrollment)

            if reason in ('remind_lesson', 'remind_lesson_before_test'):
                results.append({
                    'enrollment': enrollment,
                    'class': class_obj,
                    'last_event': last_event,
                    'next_event': next_event,
                    'decision': 'remind',
                    'reason': reason,
                })
                continue

            if not next_event:
                results.append({
                    'enrollment': enrollment,
                    'class': class_obj,
                    'last_event': last_event,
                    'next_event': None,
                    'decision': 'skip',
                    'reason': reason or 'no_next_event',
                })
                continue

            if not self.is_next_event_within_24h(next_event, tz_name):
                results.append({
                    'enrollment': enrollment,
                    'class': class_obj,
                    'last_event': last_event,
                    'next_event': next_event,
                    'decision': 'skip',
                    'reason': 'next_not_within_24h',
                })
                continue

            results.append({
                'enrollment': enrollment,
                'class': class_obj,
                'last_event': last_event,
                'next_event': next_event,
                'decision': 'schedule',
                'reason': reason or 'schedule',
            })

        return results
