from django.contrib import admin

from .models import StudySession


@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "lesson", "difficulty_mode", "status", "created_at")
    list_filter = ("difficulty_mode", "status", "grounding_mode")
    search_fields = ("id", "student__email", "lesson__title")
    readonly_fields = ("id", "created_at", "updated_at")
