from django.core.management.base import BaseCommand
from home.models import ContactMethod, SupportTeamMember, FAQ, SupportHours


class Command(BaseCommand):
    help = 'Populate home app with sample data based on the contact page images'

    def handle(self, *args, **options):
        # Create contact methods
        contact_methods_data = [
            {
                'type': 'live_chat',
                'title': 'Live Chat',
                'description': 'Get instant help from our support team',
                'availability': '24/7',
                'response_time': '< 2 minutes',
                'action_text': 'Click to start chatting',
                'action_value': '/chat',
                'icon': 'chat-bubble',
                'color': 'purple',
                'order': 1
            },
            {
                'type': 'email',
                'title': 'Email Support',
                'description': 'Send us a detailed message',
                'availability': '24/7',
                'response_time': '< 4 hours',
                'action_text': 'hello@sbtyacademy.com',
                'action_value': 'mailto:hello@sbtyacademy.com',
                'icon': 'envelope',
                'color': 'orange',
                'order': 2
            },
            {
                'type': 'phone',
                'title': 'Phone Support',
                'description': 'Speak directly with our team',
                'availability': 'Mon-Fri 9AM-6PM EST',
                'response_time': 'Immediate',
                'action_text': '1-800-SBTY-KIDS (728-9543)',
                'action_value': 'tel:1-800-728-9543',
                'icon': 'phone',
                'color': 'green',
                'order': 3
            },
            {
                'type': 'whatsapp',
                'title': 'WhatsApp',
                'description': 'Chat with us instantly on WhatsApp',
                'availability': '24/7',
                'response_time': '< 5 minutes',
                'action_text': 'Click to start WhatsApp chat',
                'action_value': 'https://wa.me/1234567890',
                'icon': 'whatsapp',
                'color': 'green',
                'order': 4
            }
        ]

        for method_data in contact_methods_data:
            method, created = ContactMethod.objects.get_or_create(
                type=method_data['type'],
                defaults=method_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created contact method: {method.title}')
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(f'Contact method already exists: {method.title}')
                )

        # Create support team members
        support_team_data = [
            {
                'name': 'Dr. Emily Rodriguez',
                'title': 'Education Director',
                'responsibilities': 'Learning support & curriculum',
                'email': 'emily@sbtyacademy.com',
                'avatar_initials': 'DER',
                'order': 1
            },
            {
                'name': 'Sarah Johnson',
                'title': 'Parent Success Manager',
                'responsibilities': 'Course guidance & enrollment',
                'email': 'sarah@sbtyacademy.com',
                'avatar_initials': 'SJ',
                'order': 2
            },
            {
                'name': 'Mike Chen',
                'title': 'Technical Support Lead',
                'responsibilities': 'Platform issues & troubleshooting',
                'email': 'mike@sbtyacademy.com',
                'avatar_initials': 'MC',
                'order': 3
            }
        ]

        for member_data in support_team_data:
            member, created = SupportTeamMember.objects.get_or_create(
                email=member_data['email'],
                defaults=member_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created support team member: {member.name}')
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(f'Support team member already exists: {member.name}')
                )

        # Create FAQs
        faqs_data = [
            {
                'question': 'How quickly will I get a response?',
                'answer': 'We aim to respond to all inquiries within 4 hours during business hours, and within 24 hours on weekends.',
                'category': 'General',
                'order': 1
            },
            {
                'question': 'Can I schedule a call with an education specialist?',
                'answer': 'Yes! We offer free 15-minute consultations to help you choose the right courses for your child.',
                'category': 'Consultation',
                'order': 2
            },
            {
                'question': 'Do you offer technical support for parents?',
                'answer': 'Absolutely! Our technical team can help you set up your child\'s learning environment and troubleshoot any issues.',
                'category': 'Technical',
                'order': 3
            }
        ]

        for faq_data in faqs_data:
            faq, created = FAQ.objects.get_or_create(
                question=faq_data['question'],
                defaults=faq_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created FAQ: {faq.question[:50]}...')
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(f'FAQ already exists: {faq.question[:50]}...')
                )

        # Create support hours
        support_hours_data = [
            {
                'period': 'Mon-Fri',
                'hours': '9AM-6PM EST',
                'is_emergency': False,
                'order': 1
            },
            {
                'period': 'Weekends',
                'hours': '10AM-4PM EST',
                'is_emergency': False,
                'order': 2
            },
            {
                'period': 'Emergency',
                'hours': '24/7',
                'is_emergency': True,
                'order': 3
            }
        ]

        for hours_data in support_hours_data:
            hours, created = SupportHours.objects.get_or_create(
                period=hours_data['period'],
                defaults=hours_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created support hours: {hours.period}')
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(f'Support hours already exist: {hours.period}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                '\nHome app data population completed successfully!'
            )
        )
