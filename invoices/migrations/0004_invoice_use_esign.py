from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0003_invoice_new_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="use_esign",
            field=models.BooleanField(default=True),
        ),
    ]
