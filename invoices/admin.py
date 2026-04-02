from __future__ import annotations

from django.contrib import admin

from invoices.models import Invoice, InvoiceLineItem


class InvoiceLineItemInline(admin.TabularInline):
	"""Inline admin for invoice line items."""

	model = InvoiceLineItem
	fields = (
		"sr_no",
		"product_name",
		"hsn_code",
		"quantity",
		"unit",
		"unit_price",
		"discount_percent",
		"taxable_amount",
		"gst_rate",
		"total_tax",
		"line_total",
	)
	readonly_fields = fields
	extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
	"""Admin interface for invoices."""

	list_display = ("invoice_number", "customer_name", "invoice_date", "status", "subtotal", "total_tax", "grand_total", "is_interstate")
	search_fields = ("invoice_number", "customer_name", "customer_gstin")
	list_filter = ("status", "is_interstate", "financial_year", "invoice_date", "created_at")
	readonly_fields = (
		"id",
		"invoice_number",
		"subtotal",
		"total_cgst",
		"total_sgst",
		"total_igst",
		"total_tax",
		"grand_total",
		"amount_in_words",
		"issued_at",
		"cancelled_at",
		"created_at",
		"updated_at",
	)
	inlines = [InvoiceLineItemInline]
	date_hierarchy = "invoice_date"
	list_per_page = 25
