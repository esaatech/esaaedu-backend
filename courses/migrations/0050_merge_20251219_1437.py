# Generated merge migration to resolve conflicting migrations
# Merge of 0049_courseassessmentsubmission and 0049_project_add_order_field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0049_courseassessmentsubmission'),
        ('courses', '0049_project_add_order_field'),
    ]

    operations = [
        # This is a merge migration - no operations needed
        # Both migrations are independent and can be applied together
    ]

