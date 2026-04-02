# Generated manually for course FK + inbound_routing on SmsRoutingLog

from django.db import migrations, models
import django.db.models.deletion


def backfill_course_and_inbound_routing(apps, schema_editor):
    SmsRoutingLog = apps.get_model("communication", "SmsRoutingLog")
    Class = apps.get_model("courses", "Class")
    for log in SmsRoutingLog.objects.filter(course_class_id__isnull=False).iterator():
        updates = {}
        if log.course_id is None:
            try:
                cls = Class.objects.get(pk=log.course_class_id)
                updates["course_id"] = cls.course_id
            except Class.DoesNotExist:
                pass
        if log.direction == "inbound" and log.inbound_routing is None:
            updates["inbound_routing"] = "generic_admin"
        if updates:
            SmsRoutingLog.objects.filter(pk=log.pk).update(**updates)

    # Inbound rows without course_class: mark legacy unprocessed rows as generic_admin
    SmsRoutingLog.objects.filter(
        direction="inbound",
        inbound_routing__isnull=True,
    ).update(inbound_routing="generic_admin")


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0003_seed_message_templates"),
        ("courses", "0064_courseassessmentsubmission_return_feedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="smsroutinglog",
            name="course",
            field=models.ForeignKey(
                blank=True,
                help_text="Course context for outbound and routed inbound.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sms_routing_logs",
                to="courses.course",
            ),
        ),
        migrations.AddField(
            model_name="smsroutinglog",
            name="inbound_routing",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("routed", "Routed"),
                    ("generic_admin", "Generic / admin"),
                ],
                help_text="Inbound only: pending until routing runs; routed if matched to prior outbound; generic_admin otherwise. Null for outbound.",
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_course_and_inbound_routing, migrations.RunPython.noop),
    ]
