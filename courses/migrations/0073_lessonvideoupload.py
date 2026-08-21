# Generated manually for LessonVideoUpload staged signed-URL flow

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0072_backfill_course_owner_memberships'),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonVideoUpload',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('target', models.CharField(choices=[('video_audio', 'Video/Audio lesson'), ('tutorx', 'TutorX interactive video')], max_length=20)),
                ('status', models.CharField(choices=[('draft', 'Draft (awaiting upload)'), ('uploaded', 'Uploaded to storage'), ('processing', 'Converting'), ('ready', 'Ready'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], db_index=True, default='draft', max_length=20)),
                ('original_filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(default='video/mp4', max_length=100)),
                ('declared_size_bytes', models.PositiveBigIntegerField(default=0)),
                ('gcs_object_name', models.CharField(help_text='Pending object path in GCS (source upload before HLS).', max_length=512)),
                ('playlist_url', models.URLField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uploaded_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('audio_video_material', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='source_uploads', to='courses.audiovideomaterial')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lesson_video_uploads', to=settings.AUTH_USER_MODEL)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='video_uploads', to='courses.lesson')),
            ],
            options={
                'verbose_name': 'Lesson video upload',
                'verbose_name_plural': 'Lesson video uploads',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='lessonvideoupload',
            index=models.Index(fields=['lesson', 'status'], name='courses_les_lesson__9a2c1d_idx'),
        ),
        migrations.AddIndex(
            model_name='lessonvideoupload',
            index=models.Index(fields=['status', 'created_at'], name='courses_les_status_4e8b2a_idx'),
        ),
    ]
