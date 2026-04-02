from django.db import migrations


def seed_sms_templates(apps, schema_editor):
    MessageTemplate = apps.get_model("communication", "MessageTemplate")
    MessageTemplate.objects.get_or_create(
        channel="sms",
        slug="class-started",
        defaults={
            "label": "Course has started",
            "body_template": (
                "Hello from SBTY Academy — just to let you know that {course_title} has started. "
                "We're glad to have you with us!"
            ),
            "subject_template": "",
            "variables": ["course_title"],
            "is_active": True,
            "sort_order": 10,
        },
    )


def unseed_sms_templates(apps, schema_editor):
    MessageTemplate = apps.get_model("communication", "MessageTemplate")
    MessageTemplate.objects.filter(channel="sms", slug="class-started").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0002_messagetemplate"),
    ]

    operations = [
        migrations.RunPython(seed_sms_templates, unseed_sms_templates),
    ]
