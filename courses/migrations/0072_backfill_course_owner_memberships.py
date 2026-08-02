from django.db import migrations


def backfill_owner_memberships(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    CourseMembership = apps.get_model('courses', 'CourseMembership')
    for course in Course.objects.all().iterator():
        CourseMembership.objects.get_or_create(
            course_id=course.id,
            user_id=course.teacher_id,
            defaults={'role': 'owner'},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0071_coursemembership'),
    ]

    operations = [
        migrations.RunPython(backfill_owner_memberships, noop_reverse),
    ]
