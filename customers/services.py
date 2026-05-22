from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import models, transaction

from customers.models import Customer


class CustomerService:
    """Business logic for party balances, summaries, and statements."""

    @staticmethod
    def update_balance(customer: Customer, amount: Decimal, operation: str) -> Customer:
        """Update customer balance safely with a row lock."""
        with transaction.atomic():
            locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
            if operation == "add":
                locked_customer.current_balance += amount
            elif operation == "subtract":
                locked_customer.current_balance -= amount
            else:
                raise ValueError("operation must be 'add' or 'subtract'")
            locked_customer.save(update_fields=["current_balance", "updated_at"])
            return locked_customer

    @staticmethod
    def get_customer_summary(company) -> dict[str, Any]:
        """Return party summary metrics for a company."""
        customers = Customer.objects.filter(company=company)
        active_customers = customers.filter(is_active=True)
        total_outstanding = sum((customer.current_balance for customer in customers if customer.current_balance > 0), Decimal("0"))
        over_credit_limit = customers.filter(credit_limit__gt=0, current_balance__gt=models.F("credit_limit")).count()
        top_customers = customers.order_by("-current_balance")[:5]

        return {
            "total_customers": customers.count(),
            "active_customers": active_customers.count(),
            "total_outstanding": total_outstanding,
            "over_credit_limit": over_credit_limit,
            "top_customers": [
                {"id": str(customer.id), "name": customer.name, "balance": customer.current_balance}
                for customer in top_customers
            ],
        }

    @staticmethod
    def get_customer_statement(
        customer: Customer,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Return a running statement based on issued invoices and payments."""
        from invoices.models import Invoice, InvoicePayment

        invoices = Invoice.objects.filter(customer=customer, status=Invoice.StatusChoices.ISSUED).order_by("invoice_date", "created_at")
        if date_from:
            invoices = invoices.filter(invoice_date__gte=date_from)
        if date_to:
            invoices = invoices.filter(invoice_date__lte=date_to)

        # Build a combined list of invoice charges and payments, sorted by date
        invoice_ids = list(invoices.values_list("id", flat=True))
        payments_qs = InvoicePayment.objects.filter(invoice_id__in=invoice_ids).order_by("payment_date", "created_at")

        entries = []
        for invoice in invoices:
            entries.append({
                "date": invoice.invoice_date,
                "type": "invoice",
                "invoice_id": invoice.id,
                "invoice_no": invoice.invoice_number,
                "description": f"Invoice #{invoice.invoice_number}",
                "debit": invoice.grand_total,
                "credit": Decimal("0"),
                "sort_key": (invoice.invoice_date, "invoice"),
            })
        for payment in payments_qs:
            entries.append({
                "date": payment.payment_date,
                "type": "payment",
                "invoice_id": payment.invoice_id,
                "invoice_no": payment.invoice.invoice_number if hasattr(payment, "invoice") else "",
                "description": f"Payment received ({payment.get_payment_mode_display()})",
                "debit": Decimal("0"),
                "credit": payment.amount,
                "sort_key": (payment.payment_date, "payment"),
            })

        entries.sort(key=lambda e: e["sort_key"])

        running_balance = customer.opening_balance
        transactions: list[dict[str, Any]] = []
        for entry in entries:
            running_balance += entry["debit"] - entry["credit"]
            transactions.append({
                **entry,
                "balance": running_balance,
            })

        return {
            "customer": {"id": str(customer.id), "name": customer.name, "gstin": customer.gstin},
            "opening_balance": customer.opening_balance,
            "transactions": transactions,
            "closing_balance": running_balance,
        }
