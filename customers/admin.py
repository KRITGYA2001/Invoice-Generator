from django.contrib import admin

from customers.models import Customer, CustomerContact, CustomerNote


class CustomerContactInline(admin.TabularInline):
	"""Inline admin for party contacts."""

	model = CustomerContact
	fields = ("name", "designation", "mobile", "email", "is_primary")
	extra = 1


class CustomerNoteInline(admin.TabularInline):
	"""Inline admin for internal party notes."""

	model = CustomerNote
	fields = ("note", "created_by", "created_at")
	readonly_fields = ("created_by", "created_at")
	extra = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
	"""Admin interface for customer/party master."""

	list_display = ("name", "party_type", "gstin", "mobile_primary", "billing_state", "current_balance", "credit_limit", "is_active")
	search_fields = ("name", "display_name", "gstin", "pan", "mobile_primary", "email")
	list_filter = ("party_type", "billing_state", "is_active", "created_at")
	readonly_fields = ("id", "current_balance", "created_at", "updated_at")
	inlines = [CustomerContactInline, CustomerNoteInline]
	list_per_page = 50
