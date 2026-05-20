from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0002_structured_shipping_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="gr_rr_number",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="invoice",
            name="order_by",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="invoice",
            name="bags",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="invoice",
            name="freight_charges",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_mode",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="invoice",
            name="ack_number",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
