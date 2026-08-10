from django.contrib import admin

from .models import AIModel, AIPromptConfiguration, AIService


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
