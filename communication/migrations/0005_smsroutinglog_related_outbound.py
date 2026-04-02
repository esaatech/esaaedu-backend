import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0004_smsroutinglog_course_inbound_routing"),
    ]

    operations = [
        migrations.AddField(
            model_name="smsroutinglog",
            name="related_outbound",
            field=models.ForeignKey(
                blank=True,
                help_text="Inbound only: outbound row this SMS replies to when correlation succeeds.",
                limit_choices_to={"direction": "outbound"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inbound_replies",
                to="communication.smsroutinglog",
            ),
        ),
    ]
