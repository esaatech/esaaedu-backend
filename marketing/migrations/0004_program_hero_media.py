# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0003_alter_program_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='hero_media',
            field=models.FileField(blank=True, null=True, upload_to='marketing/programs/hero_media/', help_text='Hero image or video file (uploaded to GCS automatically). Supports images (jpg, png, gif, webp) and videos (mp4, webm).'),
        ),
        migrations.AlterField(
            model_name='program',
            name='hero_media_url',
            field=models.URLField(blank=True, editable=False, help_text='GCS URL for hero media (auto-generated from hero_media file)', max_length=500, null=True),
        ),
    ]

