import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_service", "0008_assessmentgenerateplayground"),
        ("courses", "0074_assignmentsubmission_grading_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="aigenerationjob",
            name="assessment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ai_generation_jobs",
                to="courses.courseassessment",
            ),
        ),
        migrations.AlterField(
            model_name="aigenerationjob",
            name="kind",
            field=models.CharField(
                choices=[
                    ("quiz", "Quiz"),
                    ("assignment", "Assignment"),
                    ("assessment", "Assessment"),
                ],
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="aigenerationjob",
            name="unique_ai_generation_job_per_lesson_kind",
        ),
        migrations.AddConstraint(
            model_name="aigenerationjob",
            constraint=models.UniqueConstraint(
                condition=models.Q(assessment__isnull=True),
                fields=("lesson", "kind"),
                name="unique_ai_generation_job_per_lesson_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="aigenerationjob",
            constraint=models.UniqueConstraint(
                condition=models.Q(kind="assessment"),
                fields=("assessment", "lesson"),
                name="unique_assessment_generation_job_per_lesson",
            ),
        ),
    ]
