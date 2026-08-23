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
        ("bank", "Practice bank"),
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
        default="auto",
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


class CoachBank(models.Model):
    """Teacher-authored practice bank for one lesson (not a graded quiz)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.OneToOneField(
        "courses.Lesson",
        on_delete=models.CASCADE,
        related_name="coach_bank",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"CoachBank {self.lesson_id}"


class CoachItem(models.Model):
    """One practice question in a lesson Coach bank."""

    QUESTION_TYPE_CHOICES = [
        ("multiple_choice", "Multiple choice"),
        ("true_false", "True/false"),
        ("short_answer", "Short answer"),
    ]
    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("intermediate", "Intermediate"),
        ("hard", "Hard"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank = models.ForeignKey(
        CoachBank,
        on_delete=models.CASCADE,
        related_name="items",
    )
    order = models.PositiveIntegerField(default=0)
    question_type = models.CharField(
        max_length=32,
        choices=QUESTION_TYPE_CHOICES,
        default="short_answer",
    )
    prompt = models.TextField()
    options = models.JSONField(default=list, blank=True)
    answer = models.TextField()
    hints = models.JSONField(default=list, blank=True)
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=16,
        choices=DIFFICULTY_CHOICES,
        default="easy",
    )
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["bank", "order"]),
        ]

    def __str__(self):
        return f"CoachItem {self.id} ({self.difficulty})"


class CoachLessonMemory(models.Model):
    """Per-student, per-lesson Auto coach state (next mix, study gate, last feedback)."""

    ACTION_CHOICES = [
        ("practice", "Practice"),
        ("study_then_retake", "Study then retake"),
        ("mastered", "Mastered"),
    ]
    RUNG_CHOICES = [
        ("mix_easy", "Mix easy"),
        ("mix_climb", "Mix climb"),
        ("all_hard", "All hard"),
        ("mastered", "Mastered"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_coach_memories",
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.CASCADE,
        related_name="study_coach_memories",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, default="practice")
    auto_rung = models.CharField(max_length=32, choices=RUNG_CHOICES, default="mix_easy")
    next_mix = models.JSONField(default=dict, blank=True)
    study_sources = models.JSONField(default=list, blank=True)
    study_cleared_at = models.DateTimeField(null=True, blank=True)
    last_feedback = models.JSONField(default=dict, blank=True)
    last_band_scores = models.JSONField(default=dict, blank=True)
    last_session = models.ForeignKey(
        StudySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coach_memories",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "lesson"],
                name="studycoach_memory_student_lesson",
            )
        ]
        indexes = [
            models.Index(fields=["student", "-updated_at"], name="studycoach__student_mem_idx"),
        ]

    def __str__(self):
        return f"CoachLessonMemory {self.student_id} {self.lesson_id}"
