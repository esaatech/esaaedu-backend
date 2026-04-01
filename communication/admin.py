from django.contrib import admin

from communication.models import SmsRoutingLog


@admin.register(SmsRoutingLog)
class SmsRoutingLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "direction",
        "student_phone",
        "teacher",
        "twilio_message_sid",
    )
    list_filter = ("direction",)
    search_fields = ("student_phone", "twilio_message_sid", "body")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("teacher", "course_class")
