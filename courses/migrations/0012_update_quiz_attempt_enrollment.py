from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0011_remove_unused_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quizattempt",
            name="enrollment",
            field=models.ForeignKey("student.EnrolledCourse", on_delete=models.CASCADE),
        ),
    ]
