from __future__ import annotations

from django.urls import path

from customers.views import (
    CustomerContactDetailView,
    CustomerContactListCreateView,
    CustomerDetailView,
    CustomerListCreateView,
    CustomerNoteDeleteView,
    CustomerNoteListCreateView,
    CustomerSearchView,
    CustomerStatementView,
    CustomerSummaryView,
)

urlpatterns = [
    path("", CustomerListCreateView.as_view(), name="customer-list"),
    path("summary/", CustomerSummaryView.as_view(), name="customer-summary"),
    path("search/", CustomerSearchView.as_view(), name="customer-search"),
    path("<uuid:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
    path("<uuid:pk>/statement/", CustomerStatementView.as_view(), name="customer-statement"),
    path("<uuid:customer_pk>/contacts/", CustomerContactListCreateView.as_view(), name="contact-list"),
    path("<uuid:customer_pk>/contacts/<uuid:pk>/", CustomerContactDetailView.as_view(), name="contact-detail"),
    path("<uuid:customer_pk>/notes/", CustomerNoteListCreateView.as_view(), name="note-list"),
    path("<uuid:customer_pk>/notes/<uuid:pk>/", CustomerNoteDeleteView.as_view(), name="note-delete"),
]
