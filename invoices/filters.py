from __future__ import annotations

from django_filters import BooleanFilter, CharFilter, ChoiceFilter, DateFilter, FilterSet, NumberFilter

from invoices.models import Invoice


class InvoiceFilter(FilterSet):
    """FilterSet for invoice list and reporting views."""

    invoice_number = CharFilter(field_name="invoice_number", lookup_expr="icontains")
    customer_name = CharFilter(field_name="customer_name", lookup_expr="icontains")
    status = ChoiceFilter(field_name="status")
    date_from = DateFilter(field_name="invoice_date", lookup_expr="gte")
    date_to = DateFilter(field_name="invoice_date", lookup_expr="lte")
    due_date_from = DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = DateFilter(field_name="due_date", lookup_expr="lte")
    min_amount = NumberFilter(field_name="grand_total", lookup_expr="gte")
    max_amount = NumberFilter(field_name="grand_total", lookup_expr="lte")
    financial_year = CharFilter(field_name="financial_year", lookup_expr="exact")
    is_interstate = BooleanFilter(field_name="is_interstate")

    class Meta:
        model = Invoice
        fields = [
            "invoice_number",
            "customer_name",
            "status",
            "date_from",
            "date_to",
            "due_date_from",
            "due_date_to",
            "min_amount",
            "max_amount",
            "financial_year",
            "is_interstate",
        ]
