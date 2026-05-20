from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="customer", name="same_as_billing"),
        migrations.RemoveField(model_name="customer", name="shipping_address_line1"),
        migrations.RemoveField(model_name="customer", name="shipping_address_line2"),
        migrations.RemoveField(model_name="customer", name="shipping_city"),
        migrations.RemoveField(model_name="customer", name="shipping_state"),
        migrations.RemoveField(model_name="customer", name="shipping_state_code"),
        migrations.RemoveField(model_name="customer", name="shipping_pincode"),
        migrations.RemoveField(model_name="customer", name="shipping_country"),
    ]
