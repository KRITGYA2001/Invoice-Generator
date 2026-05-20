from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="invoice", name="shipping_address"),
        migrations.AddField(
            model_name="invoice",
            name="shipping_same_as_billing",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="shipping_address_line1",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="invoice",
            name="shipping_address_line2",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="invoice",
            name="shipping_city",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="invoice",
            name="shipping_pincode",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="invoice",
            name="shipping_country",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
