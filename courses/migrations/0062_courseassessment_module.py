# Add CourseAssessment.module for "test per module" scheduling

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0061_lesson_tutorx_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseassessment",
            name="module",
            field=models.ForeignKey(
                blank=True,
                help_text='Module this test concludes (for scheduling: "test for this module").',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assessments",
                to="courses.module",
            ),
        ),
    ]
