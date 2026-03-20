from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0062_courseassessment_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectsubmission',
            name='file_urls',
            field=models.JSONField(blank=True, default=list, help_text='List of uploaded file URLs for multi-file submissions'),
        ),
    ]

