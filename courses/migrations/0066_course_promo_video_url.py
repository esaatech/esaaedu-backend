from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0065_quiz_assignment_visible_to_students'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='promo_video_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Optional YouTube URL for landing page hero video',
                max_length=500,
            ),
        ),
    ]
