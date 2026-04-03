"""
Inbound provider webhooks (Twilio SMS, future WhatsApp, etc.).

Mount under api/webhooks/ from backend/urls.py.
"""
from django.urls import path

from communication import views

urlpatterns = [
    path(
        "twilio/sms/",
        views.TwilioInboundSmsWebhookView.as_view(),
        name="twilio-sms-inbound",
    ),
    path(
        "twilio/sms/status/",
        views.TwilioSmsStatusWebhookView.as_view(),
        name="twilio-sms-status",
    ),
]
