# Generated migration for adding css_file_url field to CodeSnippet

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("student", "0015_codesnippet_class_instance_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="codesnippet",
            name="css_file_url",
            field=models.URLField(
                blank=True,
                help_text="GCP URL for CSS files. Only populated when language is 'css'. Allows CSS to be referenced in HTML via <link> tags.",
                max_length=500,
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="codesnippet",
            index=models.Index(fields=["css_file_url"], name="student_cod_css_fil_idx"),
        ),
    ]



