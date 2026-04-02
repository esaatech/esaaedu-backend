from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "communication",
            "0006_rename_message_temp_channel_0b7b2d_idx_message_tem_channel_ffe528_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="smsroutinglog",
            name="read_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Inbound only: when this inbound SMS was read or acknowledged in the UI "
                    "(null while still notifying). Applies to every inbound row; who may set it depends on routing "
                    "(e.g. assigned teacher, admin for generic handling)."
                ),
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="smsroutinglog",
            index=models.Index(
                fields=["teacher", "direction", "read_at"],
                name="sms_rt_tch_dir_read_idx",
            ),
        ),
    ]
