import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0004_invoice_use_esign"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="amount_received",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_status",
            field=models.CharField(
                choices=[("UNPAID", "Unpaid"), ("PARTIAL", "Partial"), ("PAID", "Paid")],
                default="UNPAID",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="InvoicePayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "payment_mode",
                    models.CharField(
                        choices=[
                            ("CASH", "Cash"),
                            ("BANK_TRANSFER", "Bank Transfer"),
                            ("CHEQUE", "Cheque"),
                            ("UPI", "UPI"),
                            ("CARD", "Card"),
                            ("OTHER", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                ("payment_date", models.DateField()),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recorded_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="invoices.invoice",
                    ),
                ),
            ],
            options={
                "ordering": ["-payment_date", "-created_at"],
            },
        ),
    ]
