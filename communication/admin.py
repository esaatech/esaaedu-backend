from django.contrib import admin
from django import forms
from django.utils.html import format_html

from communication.models import MessageTemplate, SmsRoutingLog
from communication.services.inbound_processing import process_inbound_sms_routing


class MessageTemplateAdminForm(forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        allowed_sms = ", ".join(MessageTemplate.allowed_variables_for_channel(MessageTemplate.Channel.SMS))
        self.fields["body_template"].help_text = (
            f"Allowed variables for SMS templates: {allowed_sms}. "
            "Unknown placeholders are rejected on save."
        )
        self.fields["variables"].required = False
        self.fields["variables"].disabled = True
        self.fields["variables"].initial = self.instance.variables if self.instance and self.instance.pk else []
        self.fields["variables"].help_text = (
            "Auto-derived from body_template placeholders."
        )


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    form = MessageTemplateAdminForm
    readonly_fields = ("allowed_variables_notice",)
    fields = (
        "channel",
        "slug",
        "label",
        "allowed_variables_notice",
        "body_template",
        "subject_template",
        "variables",
        "is_active",
        "sort_order",
    )
    list_display = ("label", "channel", "slug", "is_active", "sort_order", "updated_at")
    list_filter = ("channel", "is_active")
    search_fields = ("label", "slug", "body_template")
    ordering = ("channel", "sort_order", "label")

    @admin.display(description="Allowed variables")
    def allowed_variables_notice(self, obj):
        allowed_sms = ", ".join(
            MessageTemplate.allowed_variables_for_channel(MessageTemplate.Channel.SMS)
        )
        return format_html(
            "<strong>Allowed SMS placeholders:</strong> {}. "
            "Unknown placeholders are rejected on save.",
            allowed_sms,
        )


@admin.action(description="Re-run inbound SMS correlation (reset pending, then match)")
def recorrelate_inbound_sms(modeladmin, request, queryset):
    """Fix stale rows or test after deploy: only inbound logs."""
    inbound = queryset.filter(direction=SmsRoutingLog.Direction.INBOUND)
    n = 0
    for log in inbound:
        SmsRoutingLog.objects.filter(pk=log.pk).update(
            inbound_routing=SmsRoutingLog.InboundRouting.PENDING,
            teacher_id=None,
            course_id=None,
            course_class_id=None,
            related_outbound_id=None,
        )
        process_inbound_sms_routing(log.pk)
        n += 1
    modeladmin.message_user(request, f"Re-correlated {n} inbound SMS log(s).")


@admin.register(SmsRoutingLog)
class SmsRoutingLogAdmin(admin.ModelAdmin):
    actions = (recorrelate_inbound_sms,)
    list_display = (
        "created_at",
        "direction",
        "inbound_routing",
        "read_at",
        "related_outbound",
        "student_phone",
        "teacher",
        "course",
        "twilio_message_sid",
    )
    list_filter = ("direction", "inbound_routing")
    search_fields = ("student_phone", "twilio_message_sid", "body")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("teacher", "course", "course_class", "related_outbound")
