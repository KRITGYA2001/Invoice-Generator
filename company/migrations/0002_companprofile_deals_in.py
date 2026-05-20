from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="deals_in",
            field=models.TextField(
                blank=True,
                help_text="Products / services dealt in (printed on invoice header)",
            ),
        ),
    ]
