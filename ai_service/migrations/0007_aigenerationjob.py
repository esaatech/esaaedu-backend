import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0006_quiz_and_assignment_generate_playgrounds"),
        ("courses", "0074_assignmentsubmission_grading_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AIGenerationJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("quiz", "Quiz"), ("assignment", "Assignment")], max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("run_token", models.CharField(max_length=64)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("result_json", models.JSONField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_generation_jobs",
                        to="courses.lesson",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_generation_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Generation Job",
                "verbose_name_plural": "AI Generation Jobs",
            },
        ),
        migrations.AddConstraint(
            model_name="aigenerationjob",
            constraint=models.UniqueConstraint(
                fields=("lesson", "kind"),
                name="unique_ai_generation_job_per_lesson_kind",
            ),
        ),
    ]
