from __future__ import annotations

import uuid
from datetime import date

from django.conf import settings
from django.db import models


class Invoice(models.Model):
	"""Invoice master record."""

	class StatusChoices(models.TextChoices):
		DRAFT = "DRAFT", "Draft"
		ISSUED = "ISSUED", "Issued"
		CANCELLED = "CANCELLED", "Cancelled"

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	company = models.ForeignKey("company.CompanyProfile", on_delete=models.PROTECT, related_name="invoices")
	customer = models.ForeignKey(
		"customers.Customer", on_delete=models.PROTECT, related_name="invoices", null=True, blank=True
	)
	invoice_number = models.CharField(max_length=50, unique=True)
	invoice_date = models.DateField(default=date.today)
	due_date = models.DateField(null=True, blank=True)
	financial_year = models.CharField(max_length=10)
	status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
	place_of_supply = models.CharField(max_length=100)
	place_of_supply_code = models.CharField(max_length=5)
	reverse_charge = models.BooleanField(default=False)
	is_interstate = models.BooleanField(default=False)
	transport_mode = models.CharField(max_length=100, blank=True)
	vehicle_number = models.CharField(max_length=50, blank=True)
	station = models.CharField(max_length=100, blank=True)
	eway_bill_number = models.CharField(max_length=50, blank=True)
	gr_rr_number = models.CharField(max_length=100, blank=True)
	order_by = models.CharField(max_length=255, blank=True)
	bags = models.CharField(max_length=50, blank=True)
	freight_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	freight_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	freight_cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	freight_sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	freight_igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	freight_tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	payment_mode = models.CharField(max_length=20, blank=True)
	ack_number = models.CharField(max_length=50, blank=True)
	po_number = models.CharField(max_length=100, blank=True)
	po_date = models.DateField(null=True, blank=True)
	customer_name = models.CharField(max_length=255, blank=True)
	customer_address = models.TextField(blank=True)
	customer_gstin = models.CharField(max_length=15, blank=True)
	customer_state = models.CharField(max_length=100, blank=True)
	customer_state_code = models.CharField(max_length=5, blank=True)
	customer_mobile = models.CharField(max_length=15, blank=True)
	customer_email = models.EmailField(blank=True)
	shipping_same_as_billing = models.BooleanField(default=True)
	shipping_name = models.CharField(max_length=255, blank=True)
	shipping_address_line1 = models.CharField(max_length=255, blank=True)
	shipping_address_line2 = models.CharField(max_length=255, blank=True)
	shipping_city = models.CharField(max_length=100, blank=True)
	shipping_state = models.CharField(max_length=100, blank=True)
	shipping_state_code = models.CharField(max_length=5, blank=True)
	shipping_pincode = models.CharField(max_length=10, blank=True)
	shipping_country = models.CharField(max_length=100, blank=True)
	subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	total_cgst = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	total_sgst = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	total_igst = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	total_cess = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	total_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	round_off = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	amount_in_words = models.CharField(max_length=500, blank=True)
	bank_name = models.CharField(max_length=255, blank=True)
	bank_account_number = models.CharField(max_length=50, blank=True)
	bank_ifsc = models.CharField(max_length=15, blank=True)
	bank_branch = models.CharField(max_length=255, blank=True)
	bank_upi_id = models.CharField(max_length=100, blank=True)
	terms_and_conditions = models.TextField(blank=True)
	notes = models.TextField(blank=True)
	irn = models.CharField(max_length=100, blank=True)
	irn_generated_at = models.DateTimeField(null=True, blank=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_invoices"
	)
	updated_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="updated_invoices"
	)
	issued_at = models.DateTimeField(null=True, blank=True)
	cancelled_at = models.DateTimeField(null=True, blank=True)
	cancellation_reason = models.TextField(blank=True)
	use_esign = models.BooleanField(default=True)
	amount_received = models.DecimalField(max_digits=14, decimal_places=2, default=0)
	payment_status = models.CharField(
		max_length=10,
		choices=[("UNPAID", "Unpaid"), ("PARTIAL", "Partial"), ("PAID", "Paid")],
		default="UNPAID",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-invoice_date", "-created_at"]
		unique_together = ("company", "invoice_number")
		verbose_name = "Invoice"
		verbose_name_plural = "Invoices"

	def __str__(self) -> str:
		return self.invoice_number


class InvoiceLineItem(models.Model):
	"""Individual invoice row."""

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")
	product = models.ForeignKey(
		"products.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoice_lines"
	)
	sr_no = models.PositiveIntegerField()
	product_name = models.CharField(max_length=255)
	hsn_code = models.CharField(max_length=10)
	description = models.TextField(blank=True)
	quantity = models.DecimalField(max_digits=12, decimal_places=3)
	unit = models.CharField(max_length=20)
	unit_price = models.DecimalField(max_digits=12, decimal_places=2)
	discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
	gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
	cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	cess_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	line_total = models.DecimalField(max_digits=12, decimal_places=2)

	class Meta:
		ordering = ["sr_no"]

	def __str__(self) -> str:
		return f"{self.sr_no}. {self.product_name} x {self.quantity}"


class InvoicePayment(models.Model):
	"""Records a payment received against an invoice."""

	PAYMENT_MODE_CHOICES = [
		("CASH", "Cash"),
		("BANK_TRANSFER", "Bank Transfer"),
		("CHEQUE", "Cheque"),
		("UPI", "UPI"),
		("CARD", "Card"),
		("OTHER", "Other"),
	]

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
	amount = models.DecimalField(max_digits=14, decimal_places=2)
	payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES)
	payment_date = models.DateField()
	reference = models.CharField(max_length=100, blank=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="recorded_payments"
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-payment_date", "-created_at"]

	def __str__(self) -> str:
		return f"{self.invoice.invoice_number} – {self.amount} ({self.payment_mode})"
