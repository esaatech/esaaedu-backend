# Slack Notifications Setup Guide

This guide will help you set up Slack notifications for contact form submissions and other system events.

## 🔧 Prerequisites

1. **Slack Workspace**: You need access to a Slack workspace
2. **Admin Permissions**: Ability to create apps in your Slack workspace

## 📋 Step-by-Step Setup

### 1. Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter app name: `SBTY contant Notification `
5. Select your workspace
6. Click **"Create App"**

### 2. Configure Bot Permissions

1. In your app settings, go to **"OAuth & Permissions"**
2. Scroll down to **"Scopes"** section
3. Add these **Bot Token Scopes**:
   - `chat:write` - Send messages
   - `chat:write.public` - Send messages to channels the app isn't in
   - `channels:read` - View basic information about public channels
   - `groups:read` - View basic information about private channels

### 3. Install App to Workspace

1. Click **"Install to Workspace"**
2. Review permissions and click **"Allow"**
3. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)

### 4. Configure Environment Variables

Add these variables to your `.env` file:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_CHANNEL=#contact-notifications
ADMIN_URL=https://your-domain.com/admin
```

### 5. Create Notification Channel

1. In your Slack workspace, create a new channel (e.g., `#contact-notifications`)
2. Invite your bot to the channel: `/invite @EsaaEdu Contact Notifications`
3. Update `SLACK_CHANNEL` in your `.env` file

### 6. Test the Integration

Run the test command:

```bash
# Test contact form notification
poetry run python manage.py test_slack_notification --type=contact

# Test system notification
poetry run python manage.py test_slack_notification --type=system
```

## 📱 What You'll Receive

### Contact Form Notifications

When someone submits a contact form, you'll receive a rich Slack message with:

- **Header**: Contact form submission with subject
- **Contact Details**: Name, email, phone, child's age
- **Message**: Full message content
- **Metadata**: Submission time and ID
- **Action Buttons**:
  - View in Admin (direct link)
  - Reply via Email (pre-filled)

### System Notifications

For system events like:
- Server errors
- New user registrations
- Course creation alerts
- Maintenance notifications

## 🎨 Customization

### Message Formatting

The notification format can be customized in `slack_notifications.py`:

- **Colors**: Different colors for different subjects
- **Fields**: Add or remove contact fields
- **Buttons**: Modify action buttons
- **Layout**: Change message structure

### Channel Routing

You can route different notifications to different channels:

```python
# In slack_notifications.py
def send_contact_notification(contact_submission):
    # Route technical issues to #tech-support
    if contact_submission.subject == 'technical':
        channel = '#tech-support'
    else:
        channel = '#contact-notifications'
```

## 🔒 Security

### Bot Token Security

- **Never commit** your bot token to version control
- **Use environment variables** for all sensitive data
- **Rotate tokens** regularly
- **Limit bot permissions** to only what's needed

### Channel Access

- **Private channels**: Only invited members can see notifications
- **Public channels**: Anyone in the workspace can see notifications
- **DMs**: Send notifications directly to specific users

## 🚨 Troubleshooting

### Common Issues

1. **"Invalid token" error**:
   - Check your `SLACK_BOT_TOKEN` is correct
   - Ensure the token starts with `xoxb-`

2. **"Channel not found" error**:
   - Verify the channel exists
   - Check the bot is invited to the channel
   - Use `#channel-name` format

3. **"Missing scope" error**:
   - Add the required scopes in your app settings
   - Reinstall the app to your workspace

4. **No notifications received**:
   - Check the bot is online
   - Verify the channel name is correct
   - Check server logs for errors

### Debug Mode

Enable debug logging by adding to your `.env`:

```bash
SLACK_DEBUG=true
```

## 📊 Monitoring

### Notification Status

The system logs notification status:
- ✅ Success: `Contact form notification sent successfully`
- ❌ Failure: `Failed to send Slack notification: [error]`

### Health Check

Add a health check endpoint to monitor Slack connectivity:

```python
# In your views.py
def slack_health_check(request):
    from slack_notifications import slack_service
    return JsonResponse({
        'slack_available': slack_service.is_available()
    })
```

## 🔄 Advanced Features

### Scheduled Notifications

Send daily/weekly summaries:

```python
from django.core.management.base import BaseCommand
from slack_notifications import send_system_notification

def send_daily_summary():
    # Count today's submissions
    today_count = ContactSubmission.objects.filter(
        created_at__date=timezone.now().date()
    ).count()
    
    send_system_notification(
        title="📊 Daily Contact Summary",
        message=f"Received {today_count} contact form submissions today"
    )
```

### Conditional Notifications

Only send notifications for certain conditions:

```python
def send_contact_notification(contact_submission):
    # Only notify for urgent subjects
    urgent_subjects = ['technical', 'billing']
    if contact_submission.subject in urgent_subjects:
        slack_service.send_contact_form_notification(contact_submission)
```

## 📞 Support

If you need help with Slack setup:

1. Check the [Slack API documentation](https://api.slack.com/)
2. Review the [Slack SDK documentation](https://slack.dev/python-slack-sdk/)
3. Test with the provided test commands
4. Check server logs for detailed error messages
