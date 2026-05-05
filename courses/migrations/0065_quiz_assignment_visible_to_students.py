# Generated manually for quiz_assignment_visible_to_students

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0064_courseassessmentsubmission_return_feedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="visible_to_students",
            field=models.BooleanField(
                default=True,
                help_text="When False, assignment is hidden from students who have no submissions yet.",
            ),
        ),
        migrations.AddField(
            model_name="quiz",
            name="visible_to_students",
            field=models.BooleanField(
                default=True,
                help_text="When False, quiz is hidden from students who have no attempts yet.",
            ),
        ),
    ]
