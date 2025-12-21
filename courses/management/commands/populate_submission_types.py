"""
Management command to populate initial SubmissionType data
This command creates the standard submission types for projects
"""

from django.core.management.base import BaseCommand
from courses.models import SubmissionType


class Command(BaseCommand):
    help = 'Populate initial SubmissionType data with standard submission types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing submission types before adding new ones',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing submission types...')
            SubmissionType.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing submission types cleared.'))

        submission_types_data = [
            {
                'name': 'link',
                'display_name': 'Link/URL',
                'description': 'Students submit URLs (GitHub repositories, live websites, etc.)',
                'requires_file_upload': False,
                'requires_text_input': False,
                'requires_url_input': True,
                'is_active': True,
                'icon': 'external-link',
                'order': 1,
            },
            {
                'name': 'image',
                'display_name': 'Image',
                'description': 'Students upload image files (designs, screenshots, diagrams)',
                'requires_file_upload': True,
                'requires_text_input': False,
                'requires_url_input': False,
                'is_active': True,
                'icon': 'image',
                'order': 2,
            },
            {
                'name': 'video',
                'display_name': 'Video',
                'description': 'Students upload video files (presentations, demos, tutorials)',
                'requires_file_upload': True,
                'requires_text_input': False,
                'requires_url_input': False,
                'is_active': True,
                'icon': 'video',
                'order': 3,
            },
            {
                'name': 'audio',
                'display_name': 'Audio',
                'description': 'Students upload audio files (podcasts, voice notes, recordings)',
                'requires_file_upload': True,
                'requires_text_input': False,
                'requires_url_input': False,
                'is_active': True,
                'icon': 'mic',
                'order': 4,
            },
            {
                'name': 'file',
                'display_name': 'File Upload',
                'description': 'Students upload general files (documents, code files, etc.)',
                'requires_file_upload': True,
                'requires_text_input': False,
                'requires_url_input': False,
                'is_active': True,
                'icon': 'file',
                'order': 5,
            },
            {
                'name': 'note',
                'display_name': 'Text Note',
                'description': 'Students submit text-based content (essays, reflections, notes)',
                'requires_file_upload': False,
                'requires_text_input': True,
                'requires_url_input': False,
                'is_active': True,
                'icon': 'sticky-note',
                'order': 6,
            },
            {
                'name': 'code',
                'display_name': 'Code',
                'description': 'Students submit code (programming assignments, scripts)',
                'requires_file_upload': False,
                'requires_text_input': True,
                'requires_url_input': False,
                'is_active': True,
                'icon': 'code',
                'order': 7,
            },
            {
                'name': 'presentation',
                'display_name': 'Presentation',
                'description': 'Students submit presentation files (PowerPoint, PDF, etc.)',
                'requires_file_upload': True,
                'requires_text_input': False,
                'requires_url_input': False,
                'is_active': True,
                'icon': 'presentation',
                'order': 8,
            },
        ]

        created_count = 0
        updated_count = 0

        for type_data in submission_types_data:
            submission_type, created = SubmissionType.objects.update_or_create(
                name=type_data['name'],
                defaults=type_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created submission type: {submission_type.display_name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Updated submission type: {submission_type.display_name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Successfully processed {len(submission_types_data)} submission types '
            f'({created_count} created, {updated_count} updated)'
        ))

