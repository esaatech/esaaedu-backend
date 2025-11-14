"""
One-time command to backfill student performance aggregates.

This command calculates and updates:
- overall_quiz_average_score
- overall_assignment_average_score  
- overall_average_score
- total_quizzes_completed
- total_assignments_completed

for all StudentProfile records.

Run once: python manage.py backfill_student_aggregates
Then remove this file after running.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import StudentProfile


class Command(BaseCommand):
    help = 'Backfill student performance aggregates (one-time migration)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )
        parser.add_argument(
            '--student-id',
            type=str,
            help='Update only a specific student by user ID (optional)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        student_id = options.get('student_id')

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Backfilling Student Performance Aggregates'))
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
        self.stdout.write(f'\nFound {total_students} student(s) to process\n')
        
        updated_count = 0
        error_count = 0
        
        try:
            with transaction.atomic():
                for idx, student_profile in enumerate(students, 1):
                    try:
                        self.stdout.write(
                            f'[{idx}/{total_students}] Processing: {student_profile.user.email}'
                        )
                        
                        # Store old values for comparison
                        old_quiz_avg = student_profile.overall_quiz_average_score
                        old_assignment_avg = student_profile.overall_assignment_average_score
                        old_overall_avg = student_profile.overall_average_score
                        old_quiz_count = student_profile.total_quizzes_completed
                        old_assignment_count = student_profile.total_assignments_completed
                        
                        if not dry_run:
                            # Recalculate aggregates
                            quiz_success = student_profile.recalculate_quiz_aggregates()
                            assignment_success = student_profile.recalculate_assignment_aggregates()
                            
                            if quiz_success and assignment_success:
                                # Refresh from DB to get updated values
                                student_profile.refresh_from_db()
                                
                                # Show changes
                                changes = []
                                if old_quiz_avg != student_profile.overall_quiz_average_score:
                                    changes.append(
                                        f'Quiz Avg: {old_quiz_avg} → {student_profile.overall_quiz_average_score}'
                                    )
                                if old_assignment_avg != student_profile.overall_assignment_average_score:
                                    changes.append(
                                        f'Assignment Avg: {old_assignment_avg} → {student_profile.overall_assignment_average_score}'
                                    )
                                if old_overall_avg != student_profile.overall_average_score:
                                    changes.append(
                                        f'Overall Avg: {old_overall_avg} → {student_profile.overall_average_score}'
                                    )
                                if old_quiz_count != student_profile.total_quizzes_completed:
                                    changes.append(
                                        f'Quiz Count: {old_quiz_count} → {student_profile.total_quizzes_completed}'
                                    )
                                if old_assignment_count != student_profile.total_assignments_completed:
                                    changes.append(
                                        f'Assignment Count: {old_assignment_count} → {student_profile.total_assignments_completed}'
                                    )
                                
                                if changes:
                                    self.stdout.write(
                                        self.style.SUCCESS(f'  ✓ Updated: {", ".join(changes)}')
                                    )
                                else:
                                    self.stdout.write(
                                        self.style.WARNING('  - No changes needed')
                                    )
                                
                                updated_count += 1
                            else:
                                self.stdout.write(
                                    self.style.ERROR('  ✗ Failed to recalculate aggregates')
                                )
                                error_count += 1
                        else:
                            # Dry run - just show what would happen
                            self.stdout.write('  [DRY RUN] Would recalculate aggregates')
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ Error: {str(e)}')
                        )
                        error_count += 1
                        continue
                
                if dry_run:
                    self.stdout.write('\n' + self.style.WARNING('DRY RUN - No changes were saved'))
                    self.stdout.write(f'Would update {updated_count} student(s)')
                else:
                    self.stdout.write('\n' + self.style.SUCCESS('=' * 60))
                    self.stdout.write(self.style.SUCCESS('Backfill Complete!'))
                    self.stdout.write(self.style.SUCCESS('=' * 60))
                    self.stdout.write(f'✓ Successfully updated: {updated_count} student(s)')
                    if error_count > 0:
                        self.stdout.write(
                            self.style.ERROR(f'✗ Errors: {error_count} student(s)')
                        )
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nFatal error: {str(e)}')
            )
            raise

