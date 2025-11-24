# Generated migration to add tldraw_board_id field

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0038_alter_assignmentsubmission_graded_questions_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="classroom",
            name="tldraw_board_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Unique tldraw board room ID for this classroom (generated on-demand)",
                max_length=100,
                null=True,
                unique=True,
            ),
        ),
    ]

