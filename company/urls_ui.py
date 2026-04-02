from django.urls import path

from company.views_ui import (
	BankDetailCreateView,
	BankDetailDeleteView,
	BankDetailListView,
	BankDetailUpdateView,
	CompanyProfileView,
	InvoiceSettingsView,
	OnboardingView,
	SetPrimaryBankView,
)

app_name = "company_ui"

urlpatterns = [
	path("onboarding/", OnboardingView.as_view(), name="onboarding"),
	path("profile/", CompanyProfileView.as_view(), name="profile"),
	path("bank-details/", BankDetailListView.as_view(), name="bank-list"),
	path("bank-details/create/", BankDetailCreateView.as_view(), name="bank-create"),
	path("bank-details/<uuid:pk>/edit/", BankDetailUpdateView.as_view(), name="bank-edit"),
	path("bank-details/<uuid:pk>/delete/", BankDetailDeleteView.as_view(), name="bank-delete"),
	path("bank-details/<uuid:pk>/set-primary/", SetPrimaryBankView.as_view(), name="bank-set-primary"),
	path("invoice-settings/", InvoiceSettingsView.as_view(), name="invoice-settings"),
]
