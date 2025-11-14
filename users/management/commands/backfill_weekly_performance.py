"""
One-time command to backfill weekly performance aggregates.

This command calculates and creates StudentWeeklyPerformance records for all students
based on their historical QuizAttempt and AssignmentSubmission data.

Run once: python manage.py backfill_weekly_performance
Then remove this file after running (optional - can keep for future backfills).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from users.models import StudentProfile, StudentWeeklyPerformance
from courses.models import QuizAttempt, AssignmentSubmission


class Command(BaseCommand):
    help = 'Backfill weekly performance aggregates for all students (one-time migration)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )
        parser.add_argument(
            '--student-id',
            type=str,
            help='Backfill only a specific student by user ID (optional)',
        )
        parser.add_argument(
            '--weeks',
            type=int,
            default=12,
            help='Number of weeks back to backfill (default: 12)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        student_id = options.get('student_id')
        weeks_back = options['weeks']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Backfilling Weekly Performance Aggregates'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))
        
        # Get students to process
        if student_id:
            students = StudentProfile.objects.filter(user_id=student_id)
            if not students.exists():
                self.stdout.write(
                    self.style.ERROR(f'Student with ID {student_id} not found')
                )
                return
        else:
            students = StudentProfile.objects.all()
        
        total_students = students.count()
        self.stdout.write(f'\nFound {total_students} student(s) to process')
        self.stdout.write(f'Backfilling last {weeks_back} weeks of data\n')
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(weeks=weeks_back)
        
        try:
            with transaction.atomic():
                for idx, student_profile in enumerate(students, 1):
                    try:
                        self.stdout.write(
                            f'[{idx}/{total_students}] Processing: {student_profile.user.email}'
                        )
                        
                        # Get all quiz attempts in the date range
                        quiz_attempts = QuizAttempt.objects.filter(
                            student=student_profile.user,
                            completed_at__isnull=False,
                            completed_at__gte=start_date,
                            score__isnull=False
                        ).order_by('completed_at')
                        
                        # Get all assignment submissions in the date range
                        from django.db.models import Q
                        assignment_submissions = AssignmentSubmission.objects.filter(
                            student=student_profile.user,
                            is_graded=True,
                            percentage__isnull=False
                        ).filter(
                            # Use graded_at if available, otherwise submitted_at
                            Q(graded_at__isnull=False, graded_at__gte=start_date) |
                            Q(graded_at__isnull=True, submitted_at__gte=start_date)
                        ).order_by('graded_at', 'submitted_at')
                        
                        # Group by week and create/update weekly performance records
                        weeks_processed = set()
                        
                        # Process quiz attempts
                        for attempt in quiz_attempts:
                            if attempt.completed_at:
                                weekly_perf, created = StudentWeeklyPerformance.get_or_create_week_performance(
                                    student_profile,
                                    attempt.completed_at
                                )
                                
                                week_key = (weekly_perf.year, weekly_perf.week_number)
                                if week_key not in weeks_processed:
                                    if not dry_run:
                                        weekly_perf.recalculate_week_averages()
                                    if created:
                                        created_count += 1
                                    else:
                                        updated_count += 1
                                    weeks_processed.add(week_key)
                        
                        # Process assignment submissions
                        for submission in assignment_submissions:
                            completion_date = submission.graded_at or submission.submitted_at
                            if completion_date and completion_date >= start_date:
                                weekly_perf, created = StudentWeeklyPerformance.get_or_create_week_performance(
                                    student_profile,
                                    completion_date
                                )
                                
                                week_key = (weekly_perf.year, weekly_perf.week_number)
                                if week_key not in weeks_processed:
                                    if not dry_run:
                                        weekly_perf.recalculate_week_averages()
                                    if created:
                                        created_count += 1
                                    else:
                                        updated_count += 1
                                    weeks_processed.add(week_key)
                        
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Processed {len(weeks_processed)} week(s)')
                        )
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ Error: {str(e)}')
                        )
                        error_count += 1
                        continue
                
                if dry_run:
                    self.stdout.write('\n' + self.style.WARNING('DRY RUN - No changes were saved'))
                    self.stdout.write(f'Would create/update {created_count + updated_count} weekly performance record(s)')
                else:
                    self.stdout.write('\n' + self.style.SUCCESS('=' * 60))
                    self.stdout.write(self.style.SUCCESS('Backfill Complete!'))
                    self.stdout.write(self.style.SUCCESS('=' * 60))
                    self.stdout.write(f'✓ Created: {created_count} weekly performance record(s)')
                    self.stdout.write(f'✓ Updated: {updated_count} weekly performance record(s)')
                    if error_count > 0:
                        self.stdout.write(
                            self.style.ERROR(f'✗ Errors: {error_count} student(s)')
                        )
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nFatal error: {str(e)}')
            )
            import traceback
            traceback.print_exc()
            raise

