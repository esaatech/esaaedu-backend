"""
Phase 2: Run scheduling checks for students at local midnight.
Run hourly (e.g. cron / Cloud Scheduler): python manage.py run_scheduling_checks

No side effects: only logs schedule | remind | skip per student/enrollment.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone as django_tz
from tutorx.scheduling.services import SchedulingChecker


class Command(BaseCommand):
    help = (
        'Run scheduling checks for students whose local time is midnight. '
        'Logs schedule | remind | skip per enrollment (no side effects).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without changing anything (this command never changes anything; just for clarity)',
        )

    def handle(self, *args, **options):
        now_utc = django_tz.now()
        self.stdout.write(f'Run at UTC: {now_utc.isoformat()}')

        checker = SchedulingChecker(now_utc=now_utc)
        timezones_at_midnight = checker.get_timezones_at_midnight()
        self.stdout.write(f'Timezones at local midnight: {len(timezones_at_midnight)}')

        students = checker.get_students_in_timezones(timezones_at_midnight)
        count = students.count()
        self.stdout.write(f'Students in those timezones: {count}')

        schedule_count = 0
        remind_count = 0
        skip_count = 0

        for student_profile in students:
            results = checker.run_for_student(student_profile)
            for r in results:
                decision = r['decision']
                if decision == 'schedule':
                    schedule_count += 1
                elif decision == 'remind':
                    remind_count += 1
                else:
                    skip_count += 1

                course_title = r['enrollment'].course.title if r['enrollment'] else '-'
                student_name = student_profile.user.get_full_name() or student_profile.user.email
                self.stdout.write(
                    f"  {student_name} | {course_title} | {decision} | {r.get('reason', '')}"
                )

        self.stdout.write('')
        self.stdout.write(f'Summary: schedule={schedule_count} remind={remind_count} skip={skip_count}')
        self.stdout.write(self.style.SUCCESS('Done.'))
