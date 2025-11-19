from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from student.models import EnrolledCourse, StudentLessonProgress
from courses.models import Lesson


class Command(BaseCommand):
    help = 'Fix incorrectly completed lessons - resets lessons that were completed without proper quiz validation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--student-id',
            type=str,
            default=None,
            help='UUID of specific student to fix (most specific identifier)'
        )
        parser.add_argument(
            '--student-email',
            type=str,
            default=None,
            help='Email of specific student to fix (alternative to student-id)'
        )
        parser.add_argument(
            '--enrollment-id',
            type=str,
            default=None,
            help='UUID of specific enrollment to fix (most targeted option)'
        )
        parser.add_argument(
            '--course-id',
            type=str,
            default=None,
            help='UUID of specific course to fix (optional)'
        )
        parser.add_argument(
            '--keep-lesson-1',
            action='store_true',
            default=True,
            help='Keep lesson 1 as completed even if quiz not passed (default: True)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually making changes'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reset even lesson 1 if quiz not passed'
        )

    def handle(self, *args, **options):
        student_id = options.get('student_id')
        student_email = options.get('student_email')
        enrollment_id = options.get('enrollment_id')
        course_id = options.get('course_id')
        keep_lesson_1 = options.get('keep_lesson_1') and not options.get('force')
        dry_run = options.get('dry_run')

        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('Fixing Incorrectly Completed Lessons'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 DRY RUN MODE - No changes will be made\n'))
        
        if keep_lesson_1:
            self.stdout.write('✅ Will keep lesson 1 as completed (unless --force is used)')
        else:
            self.stdout.write('⚠️  Will reset ALL lessons including lesson 1 if quiz not passed')

        # Validate that at least one identifier is provided (unless fixing all)
        if not any([student_id, student_email, enrollment_id, course_id]):
            self.stdout.write(self.style.WARNING(
                '\n⚠️  WARNING: No student/course filter specified. This will process ALL students!'
            ))
            confirm = input('Continue with ALL students? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operation cancelled. Please specify --student-id, --student-email, --enrollment-id, or --course-id'))
                return

        # Build query for completed progress records
        completed_progress = StudentLessonProgress.objects.filter(
            status='completed'
        ).select_related('enrollment', 'enrollment__student_profile__user', 'lesson', 'lesson__course')

        # Apply filters in order of specificity
        if enrollment_id:
            completed_progress = completed_progress.filter(
                enrollment__id=enrollment_id
            )
            # Get enrollment details for confirmation
            try:
                from student.models import EnrolledCourse
                enrollment = EnrolledCourse.objects.select_related(
                    'student_profile__user', 'course'
                ).get(id=enrollment_id)
                self.stdout.write(f'\n🎯 Filtering for enrollment: {enrollment_id}')
                self.stdout.write(f'   Student: {enrollment.student_profile.user.get_full_name()} ({enrollment.student_profile.user.email})')
                self.stdout.write(f'   Course: {enrollment.course.title}')
            except EnrolledCourse.DoesNotExist:
                raise CommandError(f'Enrollment with ID {enrollment_id} not found')

        elif student_id:
            completed_progress = completed_progress.filter(
                enrollment__student_profile__user__id=student_id
            )
            # Get student details for confirmation
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                student = User.objects.get(id=student_id)
                self.stdout.write(f'\n👤 Filtering for student ID: {student_id}')
                self.stdout.write(f'   Name: {student.get_full_name()}')
                self.stdout.write(f'   Email: {student.email}')
            except User.DoesNotExist:
                raise CommandError(f'Student with ID {student_id} not found')

        elif student_email:
            completed_progress = completed_progress.filter(
                enrollment__student_profile__user__email=student_email
            )
            # Get student details for confirmation
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                student = User.objects.get(email=student_email)
                self.stdout.write(f'\n📧 Filtering for student email: {student_email}')
                self.stdout.write(f'   Name: {student.get_full_name()}')
                self.stdout.write(f'   ID: {student.id}')
            except User.DoesNotExist:
                raise CommandError(f'Student with email {student_email} not found')

        if course_id:
            completed_progress = completed_progress.filter(
                enrollment__course__id=course_id
            )
            # Get course details for confirmation
            try:
                from courses.models import Course
                course = Course.objects.get(id=course_id)
                self.stdout.write(f'\n📚 Filtering for course: {course_id}')
                self.stdout.write(f'   Title: {course.title}')
            except Course.DoesNotExist:
                raise CommandError(f'Course with ID {course_id} not found')

        total_records = completed_progress.count()
        self.stdout.write(f'\n📊 Found {total_records} completed lesson progress records to check\n')

        if total_records == 0:
            self.stdout.write(self.style.SUCCESS('No completed lessons found. Nothing to fix.'))
            return

        # Show which students will be affected
        unique_students = set()
        unique_enrollments = set()
        for progress in completed_progress[:10]:  # Show first 10
            student = progress.enrollment.student_profile.user
            unique_students.add((student.id, student.get_full_name(), student.email))
            unique_enrollments.add((progress.enrollment.id, progress.enrollment.course.title))
        
        if unique_students:
            self.stdout.write(self.style.WARNING('\n👥 Students that will be affected:'))
            for student_id, name, email in sorted(unique_students):
                self.stdout.write(f'   • {name} ({email}) - ID: {student_id}')
            if len(unique_students) > 10:
                self.stdout.write(f'   ... and {len(unique_students) - 10} more students')
        
        if unique_enrollments:
            self.stdout.write(self.style.WARNING('\n📚 Enrollments that will be affected:'))
            for enrollment_id, course_title in sorted(unique_enrollments)[:5]:
                self.stdout.write(f'   • {course_title} - Enrollment ID: {enrollment_id}')
            if len(unique_enrollments) > 5:
                self.stdout.write(f'   ... and {len(unique_enrollments) - 5} more enrollments')

        # Track statistics
        stats = {
            'checked': 0,
            'kept_lesson_1': 0,
            'kept_valid': 0,
            'reset_invalid': 0,
            'reset_no_quiz_attempt': 0,
            'reset_quiz_not_passed': 0,
            'enrollments_updated': set(),
            'students_affected': set()
        }

        records_to_reset = []
        enrollments_to_update = set()

        # Check each completed progress record
        for progress in completed_progress:
            stats['checked'] += 1
            enrollment = progress.enrollment
            lesson = progress.lesson
            student_name = enrollment.student_profile.user.get_full_name()
            course_title = enrollment.course.title

            # Check if lesson has quiz
            has_quiz = hasattr(lesson, 'quiz') and lesson.quiz is not None
            requires_quiz = progress.requires_quiz

            # Determine if this completion is valid
            is_valid = True
            reason = ""

            # Lesson 1 special handling
            if lesson.order == 1 and keep_lesson_1:
                stats['kept_lesson_1'] += 1
                if not dry_run:
                    self.stdout.write(
                        f"✅ KEPT: {student_name} - {course_title} - Lesson {lesson.order}: {lesson.title[:50]} "
                        f"(Lesson 1, keeping as requested)"
                    )
                continue

            # Check quiz requirements
            if requires_quiz:
                if progress.quiz_attempts_count == 0:
                    is_valid = False
                    reason = "Quiz required but never attempted"
                    stats['reset_no_quiz_attempt'] += 1
                elif not progress.quiz_passed:
                    is_valid = False
                    reason = "Quiz required but not passed"
                    stats['reset_quiz_not_passed'] += 1
                else:
                    # Quiz passed, valid completion
                    stats['kept_valid'] += 1
                    if not dry_run:
                        self.stdout.write(
                            f"✅ VALID: {student_name} - {course_title} - Lesson {lesson.order}: {lesson.title[:50]} "
                            f"(Quiz passed)"
                        )
            else:
                # No quiz required, completion is valid
                stats['kept_valid'] += 1
                if not dry_run:
                    self.stdout.write(
                        f"✅ VALID: {student_name} - {course_title} - Lesson {lesson.order}: {lesson.title[:50]} "
                        f"(No quiz required)"
                    )

            # Mark for reset if invalid
            if not is_valid:
                records_to_reset.append(progress)
                enrollments_to_update.add(enrollment)
                stats['reset_invalid'] += 1
                stats['students_affected'].add((enrollment.student_profile.user.id, student_name))
                
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ INVALID: {student_name} (ID: {enrollment.student_profile.user.id}) - "
                        f"{course_title} - Lesson {lesson.order}: {lesson.title[:50]} "
                        f"({reason})"
                    )
                )

        # Summary
        self.stdout.write(self.style.WARNING('\n' + '=' * 80))
        self.stdout.write(self.style.WARNING('SUMMARY'))
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(f"Total checked: {stats['checked']}")
        self.stdout.write(f"Kept (valid): {stats['kept_valid']}")
        self.stdout.write(f"Kept (lesson 1): {stats['kept_lesson_1']}")
        self.stdout.write(f"Will reset (invalid): {stats['reset_invalid']}")
        self.stdout.write(f"  - No quiz attempt: {stats['reset_no_quiz_attempt']}")
        self.stdout.write(f"  - Quiz not passed: {stats['reset_quiz_not_passed']}")
        self.stdout.write(f"Enrollments to update: {len(enrollments_to_update)}")
        self.stdout.write(f"Students affected: {len(stats['students_affected'])}")
        
        if stats['students_affected']:
            self.stdout.write(self.style.WARNING('\n👥 Students that will be affected:'))
            for student_id, student_name in sorted(stats['students_affected']):
                self.stdout.write(f'   • {student_name} (ID: {student_id})')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 DRY RUN - No changes made'))
            return

        if not records_to_reset:
            self.stdout.write(self.style.SUCCESS('\n✅ No invalid completions found. Nothing to reset.'))
            return

        # Confirm before proceeding
        self.stdout.write(self.style.WARNING(f'\n⚠️  About to reset {len(records_to_reset)} invalid lesson completions'))
        confirm = input('Continue? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Operation cancelled.'))
            return

        # Reset invalid completions
        self.stdout.write('\n🔄 Resetting invalid completions...')
        
        with transaction.atomic():
            for progress in records_to_reset:
                # Reset progress record
                progress.status = 'not_started'
                progress.started_at = None
                progress.completed_at = None
                progress.time_spent = 0
                # Keep quiz data for reference, but reset progress
                progress.save()
                
                self.stdout.write(
                    f"  ✓ Reset: Lesson {progress.lesson.order} for "
                    f"{progress.enrollment.student_profile.user.get_full_name()}"
                )

            # Update enrollment counters
            self.stdout.write('\n📊 Updating enrollment counters...')
            for enrollment in enrollments_to_update:
                # Recalculate completed lessons count
                valid_completions = StudentLessonProgress.objects.filter(
                    enrollment=enrollment,
                    status='completed'
                ).count()
                
                old_count = enrollment.completed_lessons_count
                enrollment.completed_lessons_count = valid_completions
                
                # Recalculate progress percentage
                if enrollment.total_lessons_count > 0:
                    enrollment.progress_percentage = (
                        enrollment.completed_lessons_count / enrollment.total_lessons_count
                    ) * 100
                else:
                    enrollment.progress_percentage = 0
                
                # Update current_lesson if needed
                if enrollment.completed_lessons_count == 0:
                    # No completed lessons, set to first lesson
                    first_lesson = enrollment.course.lessons.order_by('order').first()
                    enrollment.current_lesson = first_lesson
                elif enrollment.completed_lessons_count >= enrollment.total_lessons_count:
                    # All lessons completed
                    enrollment.current_lesson = None
                    enrollment.status = 'completed'
                    enrollment.completion_date = timezone.now().date()
                else:
                    # Find next uncompleted lesson
                    completed_lesson_orders = StudentLessonProgress.objects.filter(
                        enrollment=enrollment,
                        status='completed'
                    ).values_list('lesson__order', flat=True)
                    
                    next_lesson = enrollment.course.lessons.filter(
                        order__gt=max(completed_lesson_orders) if completed_lesson_orders else 0
                    ).order_by('order').first()
                    
                    enrollment.current_lesson = next_lesson
                
                enrollment.save()
                stats['enrollments_updated'].add(enrollment.id)
                
                self.stdout.write(
                    f"  ✓ Updated: {enrollment.student_profile.user.get_full_name()} - "
                    f"{enrollment.course.title} "
                    f"(completed: {old_count} → {enrollment.completed_lessons_count})"
                )

        # Final summary
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('✅ FIX COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f"Reset {len(records_to_reset)} invalid lesson completions")
        self.stdout.write(f"Updated {len(stats['enrollments_updated'])} enrollments")
        self.stdout.write(self.style.SUCCESS('\n✅ All invalid completions have been reset!'))

