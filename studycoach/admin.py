from django.contrib import admin

from .models import CoachBank, CoachItem, StudySession


@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "lesson", "difficulty_mode", "status", "created_at")
    list_filter = ("difficulty_mode", "status", "grounding_mode")
    search_fields = ("id", "student__email", "lesson__title")
    readonly_fields = ("id", "created_at", "updated_at")


class CoachItemInline(admin.TabularInline):
    model = CoachItem
    extra = 0
    fields = ("order", "question_type", "prompt", "difficulty")
    readonly_fields = ()
    show_change_link = True


@admin.register(CoachBank)
class CoachBankAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "updated_at")
    search_fields = ("id", "lesson__title")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [CoachItemInline]


@admin.register(CoachItem)
class CoachItemAdmin(admin.ModelAdmin):
    list_display = ("id", "bank", "order", "question_type", "difficulty", "updated_at")
    list_filter = ("question_type", "difficulty")
    search_fields = ("prompt",)
    readonly_fields = ("id", "created_at", "updated_at")
