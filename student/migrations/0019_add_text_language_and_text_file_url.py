from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("student", "0018_add_flask_language_choice"),
    ]

    operations = [
        migrations.AddField(
            model_name="codesnippet",
            name="text_file_url",
            field=models.URLField(
                blank=True,
                help_text="GCP URL for plain text files. Only populated when language is 'text'.",
                max_length=500,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="codesnippet",
            name="language",
            field=models.CharField(
                choices=[
                    ("python", "Python"),
                    ("javascript", "JavaScript"),
                    ("html", "HTML"),
                    ("css", "CSS"),
                    ("text", "Plain text"),
                    ("json", "JSON"),
                    ("flask", "Flask"),
                    ("java", "Java"),
                    ("cpp", "C++"),
                    ("c", "C"),
                    ("other", "Other"),
                ],
                default="python",
                help_text="Programming language",
                max_length=50,
            ),
        ),
        migrations.AddIndex(
            model_name="codesnippet",
            index=models.Index(fields=["text_file_url"], name="student_cod_text_fil_idx"),
        ),
    ]
