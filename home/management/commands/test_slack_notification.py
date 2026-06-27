from django.core.management.base import BaseCommand
from decouple import config
from home.models import ContactSubmission
from slack_notifications import (
    send_contact_notification,
    send_system_notification,
    send_enrollment_notification,
)


class Command(BaseCommand):
    help = 'Test Slack notification system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['contact', 'system', 'error-alerts', 'enrollment'],
            default='contact',
            help='Type of notification to test'
        )

    def handle(self, *args, **options):
        notification_type = options['type']
        
        if notification_type == 'contact':
            self.test_contact_notification()
        elif notification_type == 'system':
            self.test_system_notification()
        elif notification_type == 'error-alerts':
            self.test_error_alerts_notification()
        elif notification_type == 'enrollment':
            self.test_enrollment_notification()

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

    def test_error_alerts_notification(self):
        """Test error alerts channel (SLACK_ERROR_ALERTS)"""
        channel = (config("SLACK_ERROR_ALERTS", default="") or "").strip()
        if not channel:
            self.stdout.write(
                self.style.ERROR("❌ SLACK_ERROR_ALERTS is not set in .env")
            )
            return

        self.stdout.write(f"Testing error alerts notification to {channel}...")

        success = send_system_notification(
            title="Application Error: test_alert",
            message=(
                "*Source:* test\n"
                "*Error code:* `test_alert`\n"
                "*Context:* test_slack_notification command\n"
                "This is a test error alert."
            ),
            color="#e01e5a",
            channel=channel,
        )

        if success:
            self.stdout.write(
                self.style.SUCCESS("✅ Error alerts notification sent successfully!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Failed to send error alerts notification")
            )

    def test_enrollment_notification(self):
        """Test enrollment notification (SLACK_ENROLLMENT) using the most recent enrollment"""
        from student.models import EnrolledCourse

        self.stdout.write("Testing enrollment notification...")

        enrollment = (
            EnrolledCourse.objects.select_related(
                "student_profile__user", "course", "enrolled_by"
            )
            .order_by("-enrollment_date")
            .first()
        )

        if not enrollment:
            self.stdout.write(
                self.style.ERROR(
                    "❌ No EnrolledCourse rows found. Create an enrollment first, "
                    "then re-run this command."
                )
            )
            return

        success = send_enrollment_notification(enrollment)

        if success:
            self.stdout.write(
                self.style.SUCCESS("✅ Enrollment notification sent successfully!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Failed to send enrollment notification")
            )
