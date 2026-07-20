# Generated manually for Lesson.show_ask_ai

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0068_alter_course_promo_video_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='show_ask_ai',
            field=models.BooleanField(
                default=False,
                help_text='When True, show Ask AI UI for students on this TutorX lesson.',
            ),
        ),
    ]
