from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0073_lessonvideoupload'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignmentsubmission',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('submitted', 'Submitted'),
                    ('grading', 'Grading'),
                    ('grading_failed', 'Grading Failed'),
                    ('graded', 'Graded'),
                ],
                default='draft',
                help_text='Submission status: draft, submitted, grading, grading_failed, or graded',
                max_length=20,
            ),
        ),
    ]
