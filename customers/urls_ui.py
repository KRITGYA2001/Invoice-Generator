from django.urls import path

from customers.views_ui import (
	ContactCreateView,
	ContactDeleteView,
	CustomerCreateView,
	CustomerDeleteView,
	CustomerDetailView,
	CustomerListView,
	CustomerStatementView,
	CustomerUpdateView,
	NoteCreateView,
	NoteDeleteView,
)

app_name = "customers_ui"

urlpatterns = [
	path("", CustomerListView.as_view(), name="customer-list"),
	path("create/", CustomerCreateView.as_view(), name="customer-create"),
	path("<uuid:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
	path("<uuid:pk>/edit/", CustomerUpdateView.as_view(), name="customer-edit"),
	path("<uuid:pk>/delete/", CustomerDeleteView.as_view(), name="customer-delete"),
	path("<uuid:pk>/statement/", CustomerStatementView.as_view(), name="customer-statement"),
	path("<uuid:customer_pk>/contacts/create/", ContactCreateView.as_view(), name="contact-create"),
	path("<uuid:customer_pk>/contacts/<uuid:pk>/delete/", ContactDeleteView.as_view(), name="contact-delete"),
	path("<uuid:customer_pk>/notes/create/", NoteCreateView.as_view(), name="note-create"),
	path("<uuid:customer_pk>/notes/<uuid:pk>/delete/", NoteDeleteView.as_view(), name="note-delete"),
]
