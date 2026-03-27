from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("student", "0017_rename_student_cod_css_fil_idx_code_snippe_css_fil_a579bb_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="codesnippet",
            name="language",
            field=models.CharField(
                choices=[
                    ("python", "Python"),
                    ("javascript", "JavaScript"),
                    ("html", "HTML"),
                    ("css", "CSS"),
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
    ]
