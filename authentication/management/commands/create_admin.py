from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Create admin superuser for production'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='Admin username')
        parser.add_argument('--email', type=str, default='admin@example.com', help='Admin email')
        parser.add_argument('--password', type=str, default='admin123', help='Admin password')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        try:
            with transaction.atomic():
                # Check if user already exists
                if User.objects.filter(username=username).exists():
                    self.stdout.write(
                        self.style.WARNING(f'User "{username}" already exists')
                    )
                    return

                # Create superuser
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    firebase_uid=f'admin_{username}'  # Add required firebase_uid
                )

                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created superuser: {username}')
                )
                self.stdout.write(f'Email: {email}')
                self.stdout.write(f'Password: {password}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )
