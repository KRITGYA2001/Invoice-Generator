from django.urls import path

from invoices.views_ui import (
	CustomerQuickCreateView,
	CustomerSearchJsonView,
	CustomerSearchView,
	InvoiceCancelView,
	InvoiceCreateView,
	InvoiceDetailView,
	InvoiceDuplicateView,
	InvoiceEmailView,
	InvoiceIssueView,
	InvoiceListView,
	InvoicePDFView,
	InvoiceRecordPaymentView,
	InvoiceUpdateView,
	ProductSearchJsonView,
	ProductSearchView,
)

app_name = "invoices_ui"
urlpatterns = [
	path("", InvoiceListView.as_view(), name="invoice-list"),
	path("create/", InvoiceCreateView.as_view(), name="invoice-create"),
	path("customer-search/", CustomerSearchView.as_view(), name="customer-search"),
	path("customer-search-json/", CustomerSearchJsonView.as_view(), name="customer-search-json"),
	path("customer-quick-create/", CustomerQuickCreateView.as_view(), name="customer-quick-create"),
	path("product-search/", ProductSearchView.as_view(), name="product-search"),
	path("product-search-json/", ProductSearchJsonView.as_view(), name="product-search-json"),
	path("<uuid:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
	path("<uuid:pk>/edit/", InvoiceUpdateView.as_view(), name="invoice-edit"),
	path("<uuid:pk>/issue/", InvoiceIssueView.as_view(), name="invoice-issue"),
	path("<uuid:pk>/cancel/", InvoiceCancelView.as_view(), name="invoice-cancel"),
	path("<uuid:pk>/duplicate/", InvoiceDuplicateView.as_view(), name="invoice-duplicate"),
	path("<uuid:pk>/pdf/", InvoicePDFView.as_view(), name="invoice-pdf"),
	path("<uuid:pk>/send-email/", InvoiceEmailView.as_view(), name="invoice-email"),
	path("<uuid:pk>/record-payment/", InvoiceRecordPaymentView.as_view(), name="invoice-record-payment"),
]
