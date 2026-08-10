from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from ai_service.admin_playground import AIPlaygroundAdminMixin
from ai_service.models import (
    AIGatewayPlayground,
    AIModel,
    AIPromptConfiguration,
    AIService,
    StudyCoachDeckPlayground,
)
from ai_service.platform_version import AI_PLATFORM_BUILD
from ai_service.runners.gateway_probe import run_gateway_probe

admin.site.site_header = f"Little Learners Tech (AI platform {AI_PLATFORM_BUILD})"


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "provider",
        "model_id",
        "is_active",
        "sort_order",
        "default_temperature",
        "updated_at",
    )
    list_filter = ("provider", "is_active")
    search_fields = ("display_name", "model_id", "description")
    ordering = ("sort_order", "display_name")


class AIPromptConfigurationInline(admin.TabularInline):
    model = AIPromptConfiguration
    extra = 0
    fields = (
        "name",
        "slug",
        "ai_model",
        "temperature",
        "is_default",
        "is_active",
    )
    show_change_link = True


@admin.register(AIService)
class AIServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AIPromptConfigurationInline]


@admin.register(AIPromptConfiguration)
class AIPromptConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "service",
        "slug",
        "ai_model",
        "temperature",
        "is_default",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "is_default", "service")
    search_fields = ("name", "slug", "system_prompt", "service__slug")
    autocomplete_fields = ("service", "ai_model")
    readonly_fields = ("created_at", "updated_at")


def _gateway_probe_runner(*, user_message: str, prompt_config=None, **_kwargs):
    return run_gateway_probe(user_message, prompt_config=prompt_config)


@admin.register(AIGatewayPlayground)
class AIGatewayPlaygroundAdmin(AIPlaygroundAdminMixin, admin.ModelAdmin):
    """Phase 2 reference playground — Run uses the shared gateway probe runner."""

    change_form_template = "admin/ai_service/aigatewayplayground/change_form.html"
    playground_runner = _gateway_probe_runner
    playground_input_fields = ("user_message",)

    list_display = (
        "title",
        "succeeded",
        "provider",
        "model_id",
        "last_run_at",
        "updated_at",
    )
    list_filter = ("succeeded", "provider")
    search_fields = ("title", "user_message", "notes", "error_message")
    autocomplete_fields = ("prompt_config",)
    readonly_fields = (
        "succeeded_display",
        "error_message_display",
        "result_json_display",
        "provider",
        "model_id",
        "temperature",
        "instruction_slug",
        "raw_response_text_display",
        "last_run_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "prompt_config",
                    "user_message",
                    "notes",
                )
            },
        ),
        (
            "Last run results",
            {
                "fields": (
                    "succeeded_display",
                    "error_message_display",
                    "result_json_display",
                    "provider",
                    "model_id",
                    "temperature",
                    "instruction_slug",
                    "raw_response_text_display",
                    "last_run_at",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Succeeded")
    def succeeded_display(self, obj):
        if obj.succeeded is True:
            return format_html('<img src="/static/admin/img/icon-yes.svg" alt="True">')
        if obj.succeeded is False:
            return format_html('<img src="/static/admin/img/icon-no.svg" alt="False">')
        return "—"

    @admin.display(description="Error")
    def error_message_display(self, obj):
        if not obj.error_message:
            return "—"
        return format_html(
            '<span style="color:#ba2121;white-space:pre-wrap;">{}</span>',
            obj.error_message,
        )

    @admin.display(description="Result JSON")
    def result_json_display(self, obj):
        if obj.result_json is None:
            return "—"
        import json

        body = json.dumps(obj.result_json, indent=2, default=str)
        return format_html(
            '<pre id="ai-playground-ro-result" style="white-space:pre-wrap;font-size:12px;'
            'max-height:420px;overflow:auto;background:#0d1117;color:#e6edf3;'
            'padding:14px;border-radius:6px;margin:0;">{}</pre>',
            body[:200000],
        )

    @admin.display(description="Raw response")
    def raw_response_text_display(self, obj):
        if not obj.raw_response_text:
            return "—"
        return format_html(
            '<pre style="white-space:pre-wrap;font-size:12px;max-height:280px;'
            'overflow:auto;background:#f8f9fa;padding:12px;border-radius:6px;margin:0;">{}</pre>',
            obj.raw_response_text[:14000],
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        opts = self.model._meta
        basename = f"{opts.app_label}_{opts.model_name}"
        extra_context["ai_playground_run_url"] = reverse(
            f"admin:{basename}_run_preview"
        )
        if object_id:
            extra_context["ai_playground_persist_url"] = reverse(
                f"admin:{basename}_persist_run",
                args=[object_id],
            )
        else:
            extra_context["ai_playground_persist_url"] = ""
        return super().changeform_view(request, object_id, form_url, extra_context)


def _study_coach_deck_runner(
    *,
    lesson_title: str = "",
    grounding_text: str = "",
    difficulty_mode: str = "easy",
    card_count: str = "6",
    prompt_config=None,
    **_kwargs,
):
    from ai_service.runners.study_coach_deck import generate_study_coach_deck

    try:
        count = int(card_count or 6)
    except (TypeError, ValueError):
        count = 6
    return generate_study_coach_deck(
        lesson_title=lesson_title,
        grounding_text=grounding_text,
        difficulty_mode=difficulty_mode or "easy",
        card_count=count,
        prompt_config=prompt_config,
    )


@admin.register(StudyCoachDeckPlayground)
class StudyCoachDeckPlaygroundAdmin(AIPlaygroundAdminMixin, admin.ModelAdmin):
    change_form_template = "admin/ai_service/studycoachdeckplayground/change_form.html"
    playground_runner = _study_coach_deck_runner
    playground_input_fields = (
        "lesson_title",
        "grounding_text",
        "difficulty_mode",
        "card_count",
    )

    list_display = (
        "title",
        "difficulty_mode",
        "succeeded",
        "provider",
        "model_id",
        "grounding_mode",
        "last_run_at",
    )
    list_filter = ("succeeded", "difficulty_mode", "provider", "grounding_mode")
    search_fields = ("title", "lesson_title", "notes", "error_message")
    autocomplete_fields = ("prompt_config",)
    readonly_fields = (
        "succeeded_display",
        "error_message_display",
        "result_json_display",
        "provider",
        "model_id",
        "temperature",
        "instruction_slug",
        "grounding_mode",
        "raw_response_text_display",
        "last_run_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "prompt_config",
                    "lesson_title",
                    "grounding_text",
                    "difficulty_mode",
                    "card_count",
                    "notes",
                )
            },
        ),
        (
            "Last run results",
            {
                "fields": (
                    "succeeded_display",
                    "error_message_display",
                    "result_json_display",
                    "provider",
                    "model_id",
                    "temperature",
                    "instruction_slug",
                    "grounding_mode",
                    "raw_response_text_display",
                    "last_run_at",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Succeeded")
    def succeeded_display(self, obj):
        if obj.succeeded is True:
            return format_html('<img src="/static/admin/img/icon-yes.svg" alt="True">')
        if obj.succeeded is False:
            return format_html('<img src="/static/admin/img/icon-no.svg" alt="False">')
        return "—"

    @admin.display(description="Error")
    def error_message_display(self, obj):
        if not obj.error_message:
            return "—"
        return format_html(
            '<span style="color:#ba2121;white-space:pre-wrap;">{}</span>',
            obj.error_message,
        )

    @admin.display(description="Result JSON")
    def result_json_display(self, obj):
        if obj.result_json is None:
            return "—"
        import json

        body = json.dumps(obj.result_json, indent=2, default=str)
        return format_html(
            '<pre id="ai-playground-ro-result" style="white-space:pre-wrap;font-size:12px;'
            'max-height:420px;overflow:auto;background:#0d1117;color:#e6edf3;'
            'padding:14px;border-radius:6px;margin:0;">{}</pre>',
            body[:200000],
        )

    @admin.display(description="Raw response")
    def raw_response_text_display(self, obj):
        if not obj.raw_response_text:
            return "—"
        return format_html(
            '<pre style="white-space:pre-wrap;font-size:12px;max-height:280px;'
            'overflow:auto;background:#f8f9fa;padding:12px;border-radius:6px;margin:0;">{}</pre>',
            obj.raw_response_text[:14000],
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        opts = self.model._meta
        basename = f"{opts.app_label}_{opts.model_name}"
        extra_context["ai_playground_run_url"] = reverse(f"admin:{basename}_run_preview")
        if object_id:
            extra_context["ai_playground_persist_url"] = reverse(
                f"admin:{basename}_persist_run",
                args=[object_id],
            )
        else:
            extra_context["ai_playground_persist_url"] = ""
        return super().changeform_view(request, object_id, form_url, extra_context)
