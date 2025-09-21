"""
Slack notification system for contact form submissions and other events
"""
import os
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.conf import settings
from django.utils import timezone
from decouple import config


class SlackNotificationService:
    """
    Service for sending Slack notifications
    """
    
    def __init__(self):
        self.client = None
        self.channel = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Slack client with bot token"""
        try:
            slack_token = config('SLACK_BOT_TOKEN', default='')
            if not slack_token:
                print("Warning: SLACK_BOT_TOKEN not found in environment variables")
                return
            
            self.client = WebClient(token=slack_token)
            self.channel = config('SLACK_CHANNEL', default='#general')
            
            # Test the connection
            self.client.auth_test()
            print(f"Slack client initialized successfully. Channel: {self.channel}")
            
        except SlackApiError as e:
            print(f"Error initializing Slack client: {e.response['error']}")
            self.client = None
        except Exception as e:
            print(f"Unexpected error initializing Slack client: {str(e)}")
            self.client = None
    
    def is_available(self):
        """Check if Slack notifications are available"""
        return self.client is not None
    
    def send_contact_form_notification(self, contact_submission):
        """
        Send notification for new contact form submission
        """
        if not self.is_available():
            print("Slack notifications not available")
            return False
        
        try:
            # Create the message
            message = self._format_contact_message(contact_submission)
            
            # Send to Slack
            response = self.client.chat_postMessage(
                channel=self.channel,
                text="New Contact Form Submission",
                blocks=message
            )
            
            print(f"Contact form notification sent successfully: {response['ts']}")
            return True
            
        except SlackApiError as e:
            print(f"Error sending Slack notification: {e.response['error']}")
            return False
        except Exception as e:
            print(f"Unexpected error sending Slack notification: {str(e)}")
            return False
    
    def _format_contact_message(self, submission):
        """
        Format contact submission into Slack message blocks
        """
        # Determine priority color based on subject
        color_map = {
            'technical': '#ff6b6b',  # Red for technical issues
            'billing': '#ffa726',    # Orange for billing
            'course_guidance': '#42a5f5',  # Blue for course guidance
            'enrollment': '#66bb6a',  # Green for enrollment
            'general': '#9c27b0',    # Purple for general
            'other': '#607d8b'       # Blue-grey for other
        }
        
        color = color_map.get(submission.subject, '#9c27b0')
        
        # Format child age for display
        child_age_display = f" ({submission.get_child_age_display()})" if submission.child_age else ""
        
        # Format message text (truncate if too long)
        message_text = submission.message
        if len(message_text) > 1000:
            message_text = message_text[:1000] + "..."
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📧 New Contact Form Submission - {submission.get_subject_display()}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Name:*\n{submission.full_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Email:*\n{submission.email}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Phone:*\n{submission.phone_number or 'Not provided'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Child's Age:*\n{submission.get_child_age_display() if submission.child_age else 'Not specified'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Subject:*\n{submission.get_subject_display()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Wants Updates:*\n{'Yes' if submission.wants_updates else 'No'}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:*\n```{message_text}```"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Submitted: {submission.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC | ID: {str(submission.id)[:8]}..."
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in Admin"
                        },
                        "url": f"{settings.ADMIN_URL}/admin/home/contactsubmission/{submission.id}/change/",
                        "action_id": "view_admin"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Reply via Email"
                        },
                        "url": f"mailto:{submission.email}?subject=Re: {submission.get_subject_display()}",
                        "action_id": "reply_email"
                    }
                ]
            }
        ]
        
        return blocks
    
    def send_system_notification(self, title, message, color="#36a64f"):
        """
        Send a general system notification
        """
        if not self.is_available():
            print("Slack notifications not available")
            return False
        
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                        }
                    ]
                }
            ]
            
            response = self.client.chat_postMessage(
                channel=self.channel,
                text=title,
                blocks=blocks
            )
            
            print(f"System notification sent successfully: {response['ts']}")
            return True
            
        except SlackApiError as e:
            print(f"Error sending system notification: {e.response['error']}")
            return False
        except Exception as e:
            print(f"Unexpected error sending system notification: {str(e)}")
            return False


# Global instance
slack_service = SlackNotificationService()


def send_contact_notification(contact_submission):
    """
    Convenience function to send contact form notification
    """
    return slack_service.send_contact_form_notification(contact_submission)


def send_system_notification(title, message, color="#36a64f"):
    """
    Convenience function to send system notification
    """
    return slack_service.send_system_notification(title, message, color)
