from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0002_remove_portfolio_custom_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfolio",
            name="projects_section_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Show Projects section and nav anchor on public portfolio",
            ),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="linkedin_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="linkedin_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="github_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="github_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="instagram_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="instagram_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="tiktok_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="tiktok_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="social_other_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="social_other_label",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="social_other_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="resume_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="resume_file",
            field=models.FileField(
                blank=True,
                help_text="Resume PDF or document (uses default file storage / GCS when configured)",
                null=True,
                upload_to="portfolio/resumes/",
            ),
        ),
    ]
