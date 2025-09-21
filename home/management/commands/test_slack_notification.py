from django.core.management.base import BaseCommand
from home.models import ContactSubmission
from slack_notifications import send_contact_notification, send_system_notification


class Command(BaseCommand):
    help = 'Test Slack notification system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['contact', 'system'],
            default='contact',
            help='Type of notification to test'
        )

    def handle(self, *args, **options):
        notification_type = options['type']
        
        if notification_type == 'contact':
            self.test_contact_notification()
        elif notification_type == 'system':
            self.test_system_notification()

    def test_contact_notification(self):
        """Test contact form notification"""
        self.stdout.write("Testing contact form notification...")
        
        # Create a test contact submission
        test_submission = ContactSubmission(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone_number="(555) 123-4567",
            subject="general",
            child_age="6-8",
            message="This is a test contact form submission to verify Slack notifications are working correctly.",
            wants_updates=True
        )
        
        # Save the submission to get a proper created_at timestamp
        test_submission.save()
        
        # Send notification
        success = send_contact_notification(test_submission)
        
        if success:
            self.stdout.write(
                self.style.SUCCESS("✅ Contact notification sent successfully!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Failed to send contact notification")
            )
        
        # Clean up the test submission
        test_submission.delete()

    def test_system_notification(self):
        """Test system notification"""
        self.stdout.write("Testing system notification...")
        
        success = send_system_notification(
            title="🔧 System Test",
            message="This is a test system notification to verify Slack integration is working.",
            color="#36a64f"
        )
        
        if success:
            self.stdout.write(
                self.style.SUCCESS("✅ System notification sent successfully!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Failed to send system notification")
            )
