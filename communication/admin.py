from django.contrib import admin

from communication.models import MessageTemplate, SmsRoutingLog


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("label", "channel", "slug", "is_active", "sort_order", "updated_at")
    list_filter = ("channel", "is_active")
    search_fields = ("label", "slug", "body_template")
    ordering = ("channel", "sort_order", "label")


@admin.register(SmsRoutingLog)
class SmsRoutingLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "direction",
        "inbound_routing",
        "student_phone",
        "teacher",
        "course",
        "twilio_message_sid",
    )
    list_filter = ("direction", "inbound_routing")
    search_fields = ("student_phone", "twilio_message_sid", "body")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("teacher", "course", "course_class")
