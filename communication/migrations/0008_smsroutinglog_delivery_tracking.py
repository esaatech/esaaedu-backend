from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0007_smsroutinglog_read_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="smsroutinglog",
            name="delivery_status",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Outbound only: Twilio MessageStatus (e.g. queued, sent, delivered, undelivered, failed). "
                    "Updated from the REST response and the status callback webhook."
                ),
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="smsroutinglog",
            name="delivery_error_code",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Outbound only: Twilio ErrorCode when delivery failed or was not completed.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="smsroutinglog",
            name="delivery_error_message",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Outbound only: optional provider error text.",
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="smsroutinglog",
            name="delivery_updated_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When delivery_status was last updated (send response or status callback).",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="smsroutinglog",
            index=models.Index(
                fields=["direction", "delivery_status", "delivery_updated_at"],
                name="sms_rt_dir_deliver_idx",
            ),
        ),
    ]
