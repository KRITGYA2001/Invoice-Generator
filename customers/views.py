from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from company.permissions import HasCompanyProfile
from customers.filters import CustomerFilter
from customers.models import Customer, CustomerContact, CustomerNote
from customers.serializers import (
	CustomerContactSerializer,
	CustomerCreateUpdateSerializer,
	CustomerDetailSerializer,
	CustomerListSerializer,
	CustomerNoteSerializer,
	CustomerStatementSerializer,
)
from customers.services import CustomerService


def success_response(message: str, data: Any, status_code: int) -> Response:
	"""Return a consistent success envelope."""
	return Response({"success": True, "message": message, "data": data}, status=status_code)


def error_response(message: str, errors: Any, status_code: int) -> Response:
	"""Return a consistent error envelope."""
	return Response({"success": False, "message": message, "errors": errors}, status=status_code)


class CustomerListCreateView(ListCreateAPIView):
	"""List and create parties for the authenticated user's company."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_queryset(self):
		return Customer.objects.filter(company=self.request.user.company_profile)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		queryset = CustomerFilter(request.query_params, queryset=self.get_queryset()).qs
		ordering = request.query_params.get("ordering", "name")
		allowed_ordering = {"name", "-name", "current_balance", "-current_balance", "created_at", "-created_at"}
		if ordering in allowed_ordering:
			queryset = queryset.order_by(ordering)

		page_size = int(request.query_params.get("page_size", 20))
		page = int(request.query_params.get("page", 1))
		start = (page - 1) * page_size
		total = queryset.count()
		items = queryset[start : start + page_size]

		response = success_response(
			"Parties retrieved successfully",
			{
				"customers": CustomerListSerializer(items, many=True).data,
				"pagination": {
					"page": page,
					"page_size": page_size,
					"total": total,
					"total_pages": (total + page_size - 1) // page_size,
				},
			},
			status.HTTP_200_OK,
		)
		response.headers["X-Total-Count"] = str(total)
		return response

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		serializer = CustomerCreateUpdateSerializer(data=request.data, context={"request": request})
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		company = request.user.company_profile
		name = serializer.validated_data.get("name", "")
		if Customer.objects.filter(company=company, name__iexact=name).exists():
			return error_response(
				"Duplicate party",
				{"name": "A party with this name already exists in your company"},
				status.HTTP_400_BAD_REQUEST,
			)

		customer = serializer.save()
		return success_response("Party created successfully", CustomerDetailSerializer(customer).data, status.HTTP_201_CREATED)


class CustomerDetailView(RetrieveUpdateDestroyAPIView):
	"""Retrieve, update, and soft-delete a party."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_queryset(self):
		return Customer.objects.filter(company=self.request.user.company_profile)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = self.get_object()
		return success_response("Party retrieved successfully", CustomerDetailSerializer(customer).data, status.HTTP_200_OK)

	def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = self.get_object()
		serializer = CustomerCreateUpdateSerializer(customer, data=request.data, context={"request": request})
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		updated = serializer.save()
		return success_response("Party updated successfully", CustomerDetailSerializer(updated).data, status.HTTP_200_OK)

	def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = self.get_object()
		serializer = CustomerCreateUpdateSerializer(customer, data=request.data, partial=True, context={"request": request})
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		updated = serializer.save()
		return success_response("Party updated successfully", CustomerDetailSerializer(updated).data, status.HTTP_200_OK)

	def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = self.get_object()
		if hasattr(customer, "invoices") and customer.invoices.exists():
			return error_response("Cannot delete party", {"detail": "Party has invoices"}, status.HTTP_400_BAD_REQUEST)
		customer.is_active = False
		customer.save(update_fields=["is_active"])
		return success_response("Party deleted successfully", {}, status.HTTP_204_NO_CONTENT)


class CustomerContactListCreateView(GenericAPIView):
	"""List and add contacts for a specific party."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_customer(self) -> Customer:
		return Customer.objects.get(id=self.kwargs["customer_pk"], company=self.request.user.company_profile)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		contacts = self.get_customer().contacts.all()
		return success_response("Party contacts retrieved successfully", {"contacts": CustomerContactSerializer(contacts, many=True).data}, status.HTTP_200_OK)

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = self.get_customer()
		serializer = CustomerContactSerializer(data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		with transaction.atomic():
			if serializer.validated_data.get("is_primary"):
				customer.contacts.update(is_primary=False)
			contact = CustomerContact.objects.create(customer=customer, **serializer.validated_data)

		return success_response("Party contact created successfully", CustomerContactSerializer(contact).data, status.HTTP_201_CREATED)


class CustomerContactDetailView(GenericAPIView):
	"""Retrieve, update, and delete a party contact."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_customer(self) -> Customer:
		return Customer.objects.get(id=self.kwargs["customer_pk"], company=self.request.user.company_profile)

	def get_object(self) -> CustomerContact:
		return CustomerContact.objects.get(id=self.kwargs["pk"], customer=self.get_customer())

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		return success_response("Party contact retrieved successfully", CustomerContactSerializer(self.get_object()).data, status.HTTP_200_OK)

	def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		contact = self.get_object()
		serializer = CustomerContactSerializer(contact, data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		updated = serializer.save()
		return success_response("Party contact updated successfully", CustomerContactSerializer(updated).data, status.HTTP_200_OK)

	def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		contact = self.get_object()
		serializer = CustomerContactSerializer(contact, data=request.data, partial=True)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		updated = serializer.save()
		return success_response("Party contact updated successfully", CustomerContactSerializer(updated).data, status.HTTP_200_OK)

	def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		self.get_object().delete()
		return success_response("Party contact deleted successfully", {}, status.HTTP_204_NO_CONTENT)


class CustomerNoteListCreateView(GenericAPIView):
	"""List and create internal notes for a party."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_customer(self) -> Customer:
		return Customer.objects.get(id=self.kwargs["customer_pk"], company=self.request.user.company_profile)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		notes = self.get_customer().customer_notes.order_by("-created_at")
		page_size = int(request.query_params.get("page_size", 50))
		page = int(request.query_params.get("page", 1))
		start = (page - 1) * page_size
		total = notes.count()
		items = notes[start : start + page_size]
		return success_response(
			"Party notes retrieved successfully",
			{
				"notes": CustomerNoteSerializer(items, many=True).data,
				"pagination": {
					"page": page,
					"page_size": page_size,
					"total": total,
					"total_pages": (total + page_size - 1) // page_size,
				},
			},
			status.HTTP_200_OK,
		)

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = self.get_customer()
		serializer = CustomerNoteSerializer(data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		note = CustomerNote.objects.create(customer=customer, created_by=request.user, **serializer.validated_data)
		return success_response("Party note created successfully", CustomerNoteSerializer(note).data, status.HTTP_201_CREATED)


class CustomerNoteDeleteView(GenericAPIView):
	"""Delete a note only if the creator is the authenticated user."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_object(self) -> CustomerNote:
		customer = Customer.objects.get(id=self.kwargs["customer_pk"], company=self.request.user.company_profile)
		return CustomerNote.objects.get(id=self.kwargs["pk"], customer=customer)

	def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		note = self.get_object()
		if note.created_by_id != request.user.id:
			return error_response("Forbidden", {"detail": "You can only delete your own note"}, status.HTTP_403_FORBIDDEN)
		note.delete()
		return success_response("Party note deleted successfully", {}, status.HTTP_204_NO_CONTENT)


class CustomerStatementView(GenericAPIView):
	"""Return a party statement placeholder for the requested date range."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = Customer.objects.get(id=self.kwargs["pk"], company=request.user.company_profile)
		date_from = parse_date(request.query_params.get("date_from")) if request.query_params.get("date_from") else None
		date_to = parse_date(request.query_params.get("date_to")) if request.query_params.get("date_to") else None
		data = CustomerService.get_customer_statement(customer, date_from=date_from, date_to=date_to)
		return success_response("Party statement retrieved successfully", CustomerStatementSerializer(data).data, status.HTTP_200_OK)


class CustomerSummaryView(GenericAPIView):
	"""Return party summary metrics for the company."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		summary = CustomerService.get_customer_summary(request.user.company_profile)
		return success_response("Party summary retrieved successfully", summary, status.HTTP_200_OK)


class CustomerSearchView(GenericAPIView):
	"""Quick party search for invoice autocomplete use cases."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		query = (request.query_params.get("q") or "").strip()
		if len(query) < 2:
			return error_response("Validation failed", {"q": "Search term must be at least 2 characters"}, status.HTTP_400_BAD_REQUEST)

		customers = (
			Customer.objects.filter(company=request.user.company_profile)
			.filter(Q(name__icontains=query) | Q(display_name__icontains=query) | Q(gstin__icontains=query) | Q(mobile_primary__icontains=query))
			.order_by("name")[:10]
		)
		data = [
			{
				"id": str(customer.id),
				"name": customer.name,
				"display_name": customer.display_name,
				"gstin": customer.gstin,
				"mobile_primary": customer.mobile_primary,
				"billing_state_code": customer.billing_state_code,
			}
			for customer in customers
		]
		return success_response("Party search completed successfully", {"results": data}, status.HTTP_200_OK)
