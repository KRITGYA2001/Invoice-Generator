from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0005_invoice_payment"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="freight_gst_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="invoice",
            name="freight_cgst_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="invoice",
            name="freight_sgst_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="invoice",
            name="freight_igst_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="invoice",
            name="freight_tax_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
