from django.urls import path

from company.views import (
    BankDetailDetailView,
    BankDetailListCreateView,
    CompanyCompleteProfileView,
    CompanyOnboardingView,
    CompanyProfileView,
    InvoiceSettingsView,
    SetPrimaryBankView,
)

urlpatterns = [
    path("onboarding/", CompanyOnboardingView.as_view(), name="company-onboarding"),
    path("profile/", CompanyProfileView.as_view(), name="company-profile"),
    path("bank-details/", BankDetailListCreateView.as_view(), name="bank-detail-list"),
    path("bank-details/<uuid:pk>/", BankDetailDetailView.as_view(), name="bank-detail-detail"),
    path("bank-details/<uuid:pk>/set-primary/", SetPrimaryBankView.as_view(), name="bank-set-primary"),
    path("invoice-settings/", InvoiceSettingsView.as_view(), name="invoice-settings"),
    path("complete/", CompanyCompleteProfileView.as_view(), name="company-complete"),
]