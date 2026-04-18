from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0003_portfolio_links_resume"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfolioitem",
            name="demo_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="Optional external link (hosted app, demo, GitHub Pages) shown as View project on public portfolio",
                max_length=500,
            ),
        ),
    ]
