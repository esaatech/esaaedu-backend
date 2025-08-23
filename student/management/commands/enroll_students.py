from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from courses.models import Course
from users.models import StudentProfile
from student.models import EnrolledCourse
from decimal import Decimal
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Enroll all students in a specific course by title'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course-title',
            type=str,
            default='Androids and java',
            help='Title of the course to enroll students in (default: "Androids and java")'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be enrolled without actually creating enrollments'
        )
        parser.add_argument(
            '--max-students',
            type=int,
            help='Maximum number of students to enroll (optional)'
        )

    def handle(self, *args, **options):
        course_title = options['course_title']
        dry_run = options['dry_run']
        max_students = options['max_students']

        self.stdout.write(
            self.style.SUCCESS(f'🎓 Starting enrollment process for course: "{course_title}"')
        )

        try:
            # Find the course
            try:
                course = Course.objects.get(title__icontains=course_title)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Found course: "{course.title}" (ID: {course.id})')
                )
                self.stdout.write(f'   Teacher: {course.teacher.get_full_name()}')
                self.stdout.write(f'   Level: {course.level}')
                self.stdout.write(f'   Status: {course.status}')
            except Course.DoesNotExist:
                raise CommandError(f'❌ Course with title containing "{course_title}" not found')
            except Course.MultipleObjectsReturned:
                courses = Course.objects.filter(title__icontains=course_title)
                self.stdout.write(self.style.ERROR(f'❌ Multiple courses found with title containing "{course_title}":'))
                for c in courses:
                    self.stdout.write(f'   - {c.title} (ID: {c.id})')
                raise CommandError('Please be more specific with the course title')

            # Get all student profiles
            student_profiles = StudentProfile.objects.select_related('user').all()
            
            if not student_profiles.exists():
                raise CommandError('❌ No student profiles found in the database')

            # Filter out students already enrolled in this course
            already_enrolled_ids = EnrolledCourse.objects.filter(
                course=course
            ).values_list('student_profile_id', flat=True)

            available_students = student_profiles.exclude(id__in=already_enrolled_ids)

            if not available_students.exists():
                self.stdout.write(
                    self.style.WARNING(f'⚠️  All students are already enrolled in "{course.title}"')
                )
                return

            # Apply max_students limit if specified
            if max_students:
                available_students = available_students[:max_students]

            self.stdout.write(f'📊 Enrollment Summary:')
            self.stdout.write(f'   Total student profiles: {student_profiles.count()}')
            self.stdout.write(f'   Already enrolled: {len(already_enrolled_ids)}')
            self.stdout.write(f'   Available to enroll: {available_students.count()}')
            
            if max_students:
                self.stdout.write(f'   Max students limit: {max_students}')

            if dry_run:
                self.stdout.write(self.style.WARNING('\n🔍 DRY RUN - No actual enrollments will be created'))
                self.stdout.write('Students that would be enrolled:')
                for student in available_students:
                    self.stdout.write(f'   - {student.user.get_full_name()} ({student.user.email})')
                return

            # Create enrollments
            enrollments_created = 0
            
            with transaction.atomic():
                for student_profile in available_students:
                    try:
                        # Create realistic enrollment data
                        enrollment = EnrolledCourse.objects.create(
                            student_profile=student_profile,
                            course=course,
                            status='active',
                            enrolled_by=course.teacher,  # Simulate teacher enrollment
                            progress_percentage=Decimal('0.00'),
                            completed_lessons_count=0,
                            total_lessons_count=course.lessons.count(),
                            payment_status=random.choice(['paid', 'pending', 'scholarship']),
                            amount_paid=Decimal(str(random.uniform(50, 200))),  # Random amount
                            parent_notifications_enabled=True,
                            reminder_emails_enabled=True,
                        )
                        
                        enrollments_created += 1
                        self.stdout.write(
                            f'✅ Enrolled: {student_profile.user.get_full_name()} '
                            f'({student_profile.user.email}) - Payment: {enrollment.payment_status}'
                        )
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'❌ Failed to enroll {student_profile.user.get_full_name()}: {str(e)}'
                            )
                        )

            # Final summary
            self.stdout.write(
                self.style.SUCCESS(f'\n🎉 Enrollment completed!')
            )
            self.stdout.write(f'   Successfully enrolled: {enrollments_created} students')
            self.stdout.write(f'   Course: "{course.title}"')
            self.stdout.write(f'   Total enrolled students now: {course.student_enrollments.count()}')

            # Show some enrollment statistics
            if enrollments_created > 0:
                self.stdout.write(f'\n📈 Enrollment Statistics:')
                payment_stats = EnrolledCourse.objects.filter(course=course).values_list('payment_status', flat=True)
                for status in ['paid', 'pending', 'scholarship']:
                    count = list(payment_stats).count(status)
                    if count > 0:
                        self.stdout.write(f'   {status.title()}: {count} students')

        except Exception as e:
            raise CommandError(f'❌ Error during enrollment: {str(e)}')

        self.stdout.write(
            self.style.SUCCESS(f'\n✨ You can now test the student API endpoints!')
        )
        self.stdout.write('API endpoints available:')
        self.stdout.write('   GET /api/student/enrolled-courses/ - List enrollments')
        self.stdout.write('   GET /api/student/enrolled-courses/<id>/ - Get enrollment details')
