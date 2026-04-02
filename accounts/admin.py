"""Admin registrations for accounts models."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	"""Admin configuration for the custom User model."""

	model = User
	ordering = ("-date_joined",)
	list_display = ("email", "first_name", "last_name", "is_staff", "is_active", "date_joined")
	search_fields = ("email", "first_name", "last_name")
	list_filter = ("is_staff", "is_active")

	fieldsets = (
		(None, {"fields": ("email", "password")}),
		("Personal Info", {"fields": ("first_name", "last_name", "phone")}),
		("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
		("Important Dates", {"fields": ("last_login", "date_joined", "updated_at")}),
	)

	add_fieldsets = (
		(
			None,
			{
				"classes": ("wide",),
				"fields": ("email", "first_name", "last_name", "phone", "password1", "password2", "is_staff", "is_active"),
			},
		),
	)

	readonly_fields = ("date_joined", "updated_at", "last_login")
