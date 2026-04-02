from django.contrib import admin

from company.models import BankDetail, CompanyProfile, InvoiceSettings


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
	list_display = ("company_name", "user", "gstin", "state", "mobile_primary", "created_at")
	search_fields = ("company_name", "gstin", "pan", "user__email")
	list_filter = ("state", "is_msme", "created_at")
	readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BankDetail)
class BankDetailAdmin(admin.ModelAdmin):
	list_display = ("bank_name", "account_number", "ifsc_code", "is_primary", "is_active")
	search_fields = ("bank_name", "account_number", "ifsc_code")
	list_filter = ("is_primary", "is_active", "account_type")


@admin.register(InvoiceSettings)
class InvoiceSettingsAdmin(admin.ModelAdmin):
	list_display = ("company", "invoice_prefix", "financial_year", "invoice_counter")
	search_fields = ("company__company_name",)
	readonly_fields = ("id", "invoice_counter", "created_at", "updated_at")
