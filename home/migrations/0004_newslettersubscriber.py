from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0003_assessmentsubmission_computer_skills_level'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsletterSubscriber',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('first_name', models.CharField(blank=True, max_length=100)),
                ('source', models.CharField(blank=True, help_text='Where the signup came from, e.g. homepage, blog_post', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Newsletter Subscriber',
                'verbose_name_plural': 'Newsletter Subscribers',
                'ordering': ['-created_at'],
            },
        ),
    ]
