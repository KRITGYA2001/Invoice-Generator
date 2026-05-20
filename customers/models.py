from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


gstin_validator = RegexValidator(
	regex=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
	message="Enter a valid GSTIN",
)
pan_validator = RegexValidator(regex=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", message="Enter a valid PAN")
state_code_validator = RegexValidator(regex=r"^[0-9]{2}$", message="Billing state code must be exactly 2 digits")


class Customer(models.Model):
	"""Customer/party master scoped to a company."""

	PARTY_BUSINESS = "BUSINESS"
	PARTY_INDIVIDUAL = "INDIVIDUAL"
	PARTY_GOVERNMENT = "GOVERNMENT"

	PARTY_TYPE_CHOICES = [
		(PARTY_BUSINESS, "Business / Firm"),
		(PARTY_INDIVIDUAL, "Individual"),
		(PARTY_GOVERNMENT, "Government"),
	]

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	company = models.ForeignKey(
		"company.CompanyProfile", on_delete=models.CASCADE, related_name="customers"
	)
	party_type = models.CharField(max_length=20, choices=PARTY_TYPE_CHOICES, default=PARTY_BUSINESS)
	name = models.CharField(max_length=255)
	display_name = models.CharField(max_length=255, blank=True)
	gstin = models.CharField(max_length=15, blank=True, validators=[gstin_validator])
	pan = models.CharField(max_length=10, blank=True, validators=[pan_validator])
	mobile_primary = models.CharField(max_length=15)
	mobile_secondary = models.CharField(max_length=15, blank=True)
	email = models.EmailField(blank=True)
	website = models.URLField(blank=True)
	billing_address_line1 = models.CharField(max_length=255)
	billing_address_line2 = models.CharField(max_length=255, blank=True)
	billing_city = models.CharField(max_length=100)
	billing_state = models.CharField(max_length=100)
	billing_state_code = models.CharField(max_length=5, validators=[state_code_validator])
	billing_pincode = models.CharField(max_length=10)
	billing_country = models.CharField(max_length=100, default="India")
	credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	payment_terms_days = models.PositiveIntegerField(default=0)
	opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	notes = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("company", "name")
		ordering = ["name"]
		verbose_name = "Customer"
		verbose_name_plural = "Customers"

	def __str__(self) -> str:
		return self.display_name or self.name

	@property
	def is_over_credit_limit(self) -> bool:
		"""Check whether the party is beyond the approved credit limit."""
		return self.credit_limit > 0 and self.current_balance > self.credit_limit

	@property
	def full_billing_address(self) -> str:
		"""Return a single formatted billing address string."""
		parts = [
			self.billing_address_line1,
			self.billing_address_line2,
			self.billing_city,
			self.billing_state,
			self.billing_state_code,
			self.billing_pincode,
			self.billing_country,
		]
		return ", ".join(part for part in parts if part)


class CustomerContact(models.Model):
	"""Additional contact person for a customer/party."""

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="contacts")
	name = models.CharField(max_length=150)
	designation = models.CharField(max_length=100, blank=True)
	mobile = models.CharField(max_length=15, blank=True)
	email = models.EmailField(blank=True)
	is_primary = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-is_primary", "name"]

	def __str__(self) -> str:
		return f"{self.name} ({self.customer.name})"


class CustomerNote(models.Model):
	"""Internal note history for a customer/party."""

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="customer_notes")
	note = models.TextField()
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="customer_notes"
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"Note for {self.customer.name} at {self.created_at}"
