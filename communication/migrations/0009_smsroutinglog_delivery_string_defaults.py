"""
Ensure delivery_* varchar columns have a DB default of '' on PostgreSQL.

Without it, INSERTs that omit these columns (e.g. older app versions after migrate)
get NULL and violate NOT NULL. Inbound rows never set delivery fields in application code.
"""

from django.db import connection, migrations


def ensure_postgres_delivery_defaults(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE sms_routing_logs
            ALTER COLUMN delivery_status SET DEFAULT '',
            ALTER COLUMN delivery_error_code SET DEFAULT '',
            ALTER COLUMN delivery_error_message SET DEFAULT '';
            """
        )
        cursor.execute(
            "UPDATE sms_routing_logs SET delivery_status = '' WHERE delivery_status IS NULL"
        )
        cursor.execute(
            "UPDATE sms_routing_logs SET delivery_error_code = '' WHERE delivery_error_code IS NULL"
        )
        cursor.execute(
            "UPDATE sms_routing_logs SET delivery_error_message = '' WHERE delivery_error_message IS NULL"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0008_smsroutinglog_delivery_tracking"),
    ]

    operations = [
        migrations.RunPython(ensure_postgres_delivery_defaults, migrations.RunPython.noop),
    ]
