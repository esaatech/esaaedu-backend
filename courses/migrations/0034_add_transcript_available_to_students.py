# Generated migration for adding transcript_available_to_students field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0033_documentmaterial'),
    ]

    operations = [
        migrations.AddField(
            model_name='videomaterial',
            name='transcript_available_to_students',
            field=models.BooleanField(default=False, help_text='Whether transcript is visible to students'),
        ),
    ]

