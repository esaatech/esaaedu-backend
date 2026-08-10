import uuid

from django.conf import settings
from django.db import models


class StudySession(models.Model):
    """A student Study Coach quiz-card session for one lesson."""

    DIFFICULTY_MODE_CHOICES = [
        ("easy", "Easy"),
        ("hard", "Hard"),
        ("auto", "Auto"),
    ]
    GROUNDING_MODE_CHOICES = [
        ("grounded", "Grounded"),
        ("title", "Title"),
        ("static", "Static"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("abandoned", "Abandoned"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_coach_sessions",
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.CASCADE,
        related_name="study_coach_sessions",
    )
    difficulty_mode = models.CharField(
        max_length=16,
        choices=DIFFICULTY_MODE_CHOICES,
        default="easy",
    )
    grounding_mode = models.CharField(
        max_length=16,
        choices=GROUNDING_MODE_CHOICES,
        default="static",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="active",
    )
    cards = models.JSONField(default=list, blank=True)
    progress = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "-created_at"]),
            models.Index(fields=["lesson", "-created_at"]),
        ]

    def __str__(self):
        return f"StudySession {self.id} ({self.difficulty_mode})"
