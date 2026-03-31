from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0013_teacherpayout"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="teacherprofile",
            name="next_pay_day",
        ),
        migrations.RemoveField(
            model_name="teacherprofile",
            name="pay_status",
        ),
    ]

