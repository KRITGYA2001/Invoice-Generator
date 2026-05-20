from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


gstin_validator = RegexValidator(
    regex=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
    message="Enter a valid GSTIN",
)
pan_validator = RegexValidator(
    regex=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
    message="Enter a valid PAN",
)
state_code_validator = RegexValidator(regex=r"^[0-9]{2}$", message="State code must be exactly 2 digits")


class CompanyProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_profile")
    company_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255, blank=True)
    unit_division = models.CharField(max_length=255, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    state_code = models.CharField(max_length=5, validators=[state_code_validator])
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default="India")
    pan = models.CharField(max_length=10, blank=True, validators=[pan_validator])
    gstin = models.CharField(max_length=15, blank=True, validators=[gstin_validator])
    udyam_number = models.CharField(max_length=25, blank=True)
    mobile_primary = models.CharField(max_length=15)
    mobile_secondary = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    deals_in = models.TextField(blank=True, help_text="Products / services dealt in (printed on invoice header)")
    logo = models.ImageField(upload_to="company/logos/", null=True, blank=True)
    logo_text = models.CharField(max_length=6, blank=True)
    signature_image = models.ImageField(upload_to="company/signatures/", null=True, blank=True)
    authorised_signatory = models.CharField(max_length=255, blank=True)
    is_msme = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Profile"

    def __str__(self) -> str:
        return self.company_name


class BankDetail(models.Model):
    class AccountTypeChoices(models.TextChoices):
        SAVINGS = "savings", "Savings"
        CURRENT = "current", "Current"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name="bank_details")
    bank_name = models.CharField(max_length=255)
    branch_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=15)
    account_type = models.CharField(max_length=20, choices=AccountTypeChoices.choices, default=AccountTypeChoices.CURRENT)
    swift_code = models.CharField(max_length=15, blank=True)
    ad_code = models.CharField(max_length=20, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    qr_code_image = models.ImageField(upload_to="company/qr_codes/", null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bank Detail"
        ordering = ["-is_primary", "bank_name"]

    def __str__(self) -> str:
        return f"{self.bank_name} - {self.account_number}"


class InvoiceSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(CompanyProfile, on_delete=models.CASCADE, related_name="invoice_settings")
    invoice_prefix = models.CharField(max_length=20, default="INV")
    financial_year = models.CharField(max_length=10, default="25-26")
    invoice_counter = models.PositiveIntegerField(default=1)
    counter_reset_yearly = models.BooleanField(default=True)
    default_due_days = models.PositiveIntegerField(default=30)
    default_transport = models.CharField(max_length=100, default="BY Hand")
    default_place_of_supply = models.CharField(max_length=100, blank=True)
    reverse_charge_applicable = models.BooleanField(default=False)
    einvoicing_enabled = models.BooleanField(default=False)
    ewaybill_enabled = models.BooleanField(default=False)
    invoice_terms = models.TextField(blank=True)
    invoice_notes = models.TextField(blank=True)
    show_bank_details = models.BooleanField(default=True)
    show_signature = models.BooleanField(default=True)
    number_of_copies = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Invoice Settings"

    def __str__(self) -> str:
        return f"Invoice Settings - {self.company.company_name}"
