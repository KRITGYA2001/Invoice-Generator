from __future__ import annotations

from django.urls import path

from invoices.views import (
    CustomerInvoiceListView,
    InvoiceCancelView,
    InvoiceDetailView,
    InvoiceDuplicateView,
    InvoiceGSTSummaryView,
    InvoiceIssueView,
    InvoiceListCreateView,
    InvoiceEmailView,
    InvoicePDFView,
    InvoiceSummaryView,
)

urlpatterns = [
    path("", InvoiceListCreateView.as_view(), name="invoice-list"),
    path("summary/", InvoiceSummaryView.as_view(), name="invoice-summary"),
    path("customer/<uuid:customer_pk>/", CustomerInvoiceListView.as_view(), name="customer-invoices"),
    path("<uuid:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("<uuid:pk>/issue/", InvoiceIssueView.as_view(), name="invoice-issue"),
    path("<uuid:pk>/cancel/", InvoiceCancelView.as_view(), name="invoice-cancel"),
    path("<uuid:pk>/duplicate/", InvoiceDuplicateView.as_view(), name="invoice-duplicate"),
    path("<uuid:pk>/gst-summary/", InvoiceGSTSummaryView.as_view(), name="invoice-gst-summary"),
    path("<uuid:pk>/pdf/", InvoicePDFView.as_view(), name="invoice-pdf"),
    path("<uuid:pk>/email/", InvoiceEmailView.as_view(), name="invoice-email"),
]
