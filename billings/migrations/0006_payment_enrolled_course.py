# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billings", "0005_remove_old_subscription_model"),
        ("student", "0018_add_flask_language_choice"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="enrolled_course",
            field=models.OneToOneField(
                blank=True,
                help_text="Admin/cash payment tied to this enrollment; keeps one Payment row per enrollment.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="manual_billing_payment",
                to="student.enrolledcourse",
            ),
        ),
    ]
