import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("courses", "0072_backfill_course_owner_memberships"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudySession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "difficulty_mode",
                    models.CharField(
                        choices=[
                            ("easy", "Easy"),
                            ("hard", "Hard"),
                            ("auto", "Auto"),
                        ],
                        default="easy",
                        max_length=16,
                    ),
                ),
                (
                    "grounding_mode",
                    models.CharField(
                        choices=[
                            ("grounded", "Grounded"),
                            ("title", "Title"),
                            ("static", "Static"),
                        ],
                        default="static",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("abandoned", "Abandoned"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("cards", models.JSONField(blank=True, default=list)),
                ("progress", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="study_coach_sessions",
                        to="courses.lesson",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="study_coach_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="studysession",
            index=models.Index(
                fields=["student", "-created_at"],
                name="studycoach__student_7a0c1d_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="studysession",
            index=models.Index(
                fields=["lesson", "-created_at"],
                name="studycoach__lesson_3b8e2a_idx",
            ),
        ),
    ]
