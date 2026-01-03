# Generated migration for adding order field to Project model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0048_course_thumbnail_alter_course_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='order',
            field=models.IntegerField(default=0, help_text='Project sequence within the course'),
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['order', '-created_at']},
        ),
    ]



