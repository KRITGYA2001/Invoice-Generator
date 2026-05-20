from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from company.permissions import HasCompanyProfile
from customers.models import Customer
from invoices.filters import InvoiceFilter
from invoices.models import Invoice, InvoiceLineItem
from invoices.serializers import (
	InvoiceCancelSerializer,
	InvoiceCreateSerializer,
	InvoiceDetailSerializer,
	InvoiceListSerializer,
	InvoiceSummarySerializer,
	InvoiceUpdateSerializer,
)
from invoices.services import InvoiceNumberGenerator, InvoiceService
from invoices.pdf_service import InvoicePDFService


def success_response(message: str, data: Any, status_code: int) -> Response:
	"""Return a consistent success response."""
	return Response({"success": True, "message": message, "data": data}, status=status_code)


def error_response(message: str, errors: Any, status_code: int) -> Response:
	"""Return a consistent error response."""
	return Response({"success": False, "message": message, "errors": errors}, status=status_code)


class InvoiceListCreateView(ListCreateAPIView):
	"""List and create invoices for the authenticated user's company."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_queryset(self):
		return (
			Invoice.objects.filter(company=self.request.user.company_profile)
			.select_related("customer", "company")
			.prefetch_related("line_items")
		)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		queryset = InvoiceFilter(request.query_params, queryset=self.get_queryset()).qs
		ordering = request.query_params.get("ordering", "-invoice_date")
		allowed = {"invoice_date", "-invoice_date", "grand_total", "-grand_total", "created_at", "-created_at"}
		if ordering in allowed:
			queryset = queryset.order_by(ordering)

		page_size = int(request.query_params.get("page_size", 20))
		page = int(request.query_params.get("page", 1))
		total = queryset.count()
		items = queryset[(page - 1) * page_size : page * page_size]
		serializer = InvoiceListSerializer(items, many=True)

		response = success_response(
			"Invoices retrieved successfully",
			{
				"invoices": serializer.data,
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
		serializer = InvoiceCreateSerializer(data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		company = request.user.company_profile
		customer = None
		customer_id = serializer.validated_data.get("customer")
		if customer_id:
			try:
				customer = Customer.objects.get(id=customer_id, company=company)
			except Customer.DoesNotExist:
				return error_response("Validation failed", {"customer": "Party not found for this company"}, status.HTTP_400_BAD_REQUEST)

		try:
			invoice = InvoiceService.create_invoice(
				company=company,
				customer=customer,
				invoice_data=serializer.validated_data,
				line_items_data=serializer.validated_data["line_items"],
				user=request.user,
			)
		except ValueError as exc:
			return error_response("Invoice creation failed", {"detail": str(exc)}, status.HTTP_400_BAD_REQUEST)
		return success_response("Invoice created successfully", InvoiceDetailSerializer(invoice).data, status.HTTP_201_CREATED)


class InvoiceDetailView(RetrieveUpdateAPIView):
	"""Retrieve or update a draft invoice."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get_queryset(self):
		return Invoice.objects.filter(company=self.request.user.company_profile).prefetch_related("line_items")

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		invoice = self.get_object()
		return success_response("Invoice retrieved successfully", InvoiceDetailSerializer(invoice).data, status.HTTP_200_OK)

	def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		return self._update_invoice(request, partial=False)

	def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		return self._update_invoice(request, partial=True)

	def _update_invoice(self, request: Request, partial: bool) -> Response:
		invoice = self.get_object()
		if invoice.status != Invoice.StatusChoices.DRAFT:
			return error_response("Cannot edit an issued or cancelled invoice", {"detail": "Invoice is not editable"}, status.HTTP_400_BAD_REQUEST)

		serializer = InvoiceUpdateSerializer(data=request.data, partial=partial)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		validated = serializer.validated_data
		if "line_items" not in validated:
			return error_response("Validation failed", {"line_items": "At least one line item is required"}, status.HTTP_400_BAD_REQUEST)

		try:
			with transaction.atomic():
				company = request.user.company_profile
				customer = invoice.customer
				customer_id = validated.get("customer")
				if customer_id:
					try:
						customer = Customer.objects.get(id=customer_id, company=company)
					except Customer.DoesNotExist as exc:
						raise ValueError("Party not found for this company") from exc

			scalar_fields = [
				"invoice_date",
				"due_date",
				"place_of_supply",
				"place_of_supply_code",
				"reverse_charge",
				"transport_mode",
				"vehicle_number",
				"station",
				"eway_bill_number",
				"po_number",
				"po_date",
				"notes",
				"terms_and_conditions",
			]
			for field_name in scalar_fields:
				if field_name in validated:
					setattr(invoice, field_name, validated[field_name])

				invoice.customer = customer
				if customer:
					InvoiceService._snapshot_customer(invoice, customer)
					invoice.is_interstate = bool(invoice.place_of_supply_code and customer.billing_state_code and invoice.place_of_supply_code != customer.billing_state_code)
				else:
					manual_fields = {"customer_name", "customer_address", "customer_gstin", "customer_state", "customer_state_code", "customer_mobile", "customer_email"}
					if manual_fields.intersection(validated.keys()) or not invoice.customer_name:
						InvoiceService._snapshot_manual_customer(invoice, validated)
					invoice.is_interstate = False

				invoice.bank_name = invoice.company.bank_details.filter(is_primary=True, is_active=True).values_list("bank_name", flat=True).first() or invoice.bank_name
				invoice.bank_account_number = invoice.company.bank_details.filter(is_primary=True, is_active=True).values_list("account_number", flat=True).first() or invoice.bank_account_number
				invoice.bank_ifsc = invoice.company.bank_details.filter(is_primary=True, is_active=True).values_list("ifsc_code", flat=True).first() or invoice.bank_ifsc
				invoice.bank_branch = invoice.company.bank_details.filter(is_primary=True, is_active=True).values_list("branch_name", flat=True).first() or invoice.bank_branch
				invoice.bank_upi_id = invoice.company.bank_details.filter(is_primary=True, is_active=True).values_list("upi_id", flat=True).first() or invoice.bank_upi_id
				invoice.updated_by = request.user
				invoice.save()

				invoice.line_items.all().delete()
				line_items = []
				for index, item_data in enumerate(validated["line_items"], start=1):
					line_item, _ = InvoiceService._build_line_item(invoice, company, item_data, index)
					line_items.append(line_item)
				InvoiceLineItem.objects.bulk_create(line_items)
				invoice = InvoiceService.recalculate_invoice(invoice)
		except ValueError as exc:
			return error_response("Invoice update failed", {"detail": str(exc)}, status.HTTP_400_BAD_REQUEST)

		return success_response("Invoice updated successfully", InvoiceDetailSerializer(invoice).data, status.HTTP_200_OK)


class InvoiceIssueView(GenericAPIView):
	"""Issue a draft invoice."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		invoice = Invoice.objects.get(id=kwargs["pk"], company=request.user.company_profile)
		try:
			updated = InvoiceService.issue_invoice(invoice, request.user)
		except ValueError as exc:
			return error_response("Invoice issue failed", {"detail": str(exc)}, status.HTTP_400_BAD_REQUEST)
		return success_response("Invoice issued successfully", InvoiceDetailSerializer(updated).data, status.HTTP_200_OK)


class InvoiceCancelView(GenericAPIView):
	"""Cancel an issued invoice."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		serializer = InvoiceCancelSerializer(data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		invoice = Invoice.objects.get(id=kwargs["pk"], company=request.user.company_profile)
		try:
			updated = InvoiceService.cancel_invoice(invoice, serializer.validated_data["cancellation_reason"], request.user)
		except ValueError as exc:
			return error_response("Invoice cancel failed", {"detail": str(exc)}, status.HTTP_400_BAD_REQUEST)
		return success_response("Invoice cancelled successfully", InvoiceDetailSerializer(updated).data, status.HTTP_200_OK)


class InvoiceDuplicateView(GenericAPIView):
	"""Duplicate an existing invoice as a new draft."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		source = Invoice.objects.select_related("customer", "company").prefetch_related("line_items").get(id=kwargs["pk"], company=request.user.company_profile)
		with transaction.atomic():
			duplicate = Invoice.objects.create(
				company=source.company,
				customer=source.customer,
				invoice_number=InvoiceNumberGenerator.generate(source.company),
				invoice_date=date.today(),
				due_date=source.due_date,
				financial_year=source.financial_year,
				status=Invoice.StatusChoices.DRAFT,
				place_of_supply=source.place_of_supply,
				place_of_supply_code=source.place_of_supply_code,
				reverse_charge=source.reverse_charge,
				is_interstate=source.is_interstate,
				transport_mode=source.transport_mode,
				vehicle_number=source.vehicle_number,
				station=source.station,
				po_number=source.po_number,
				po_date=source.po_date,
				customer_name=source.customer_name,
				customer_address=source.customer_address,
				customer_gstin=source.customer_gstin,
				customer_state=source.customer_state,
				customer_state_code=source.customer_state_code,
				customer_mobile=source.customer_mobile,
				customer_email=source.customer_email,
				shipping_same_as_billing=source.shipping_same_as_billing,
				shipping_name=source.shipping_name,
				shipping_address_line1=source.shipping_address_line1,
				shipping_address_line2=source.shipping_address_line2,
				shipping_city=source.shipping_city,
				shipping_state=source.shipping_state,
				shipping_state_code=source.shipping_state_code,
				shipping_pincode=source.shipping_pincode,
				shipping_country=source.shipping_country,
				terms_and_conditions=source.terms_and_conditions,
				notes=source.notes,
				bank_name=source.bank_name,
				bank_account_number=source.bank_account_number,
				bank_ifsc=source.bank_ifsc,
				bank_branch=source.bank_branch,
				bank_upi_id=source.bank_upi_id,
				created_by=request.user,
				updated_by=request.user,
			)
			for index, line_item in enumerate(source.line_items.all(), start=1):
				InvoiceLineItem.objects.create(
					invoice=duplicate,
					product=line_item.product,
					sr_no=index,
					product_name=line_item.product_name,
					hsn_code=line_item.hsn_code,
					description=line_item.description,
					quantity=line_item.quantity,
					unit=line_item.unit,
					unit_price=line_item.unit_price,
					discount_percent=line_item.discount_percent,
					discount_amount=line_item.discount_amount,
					taxable_amount=line_item.taxable_amount,
					gst_rate=line_item.gst_rate,
					cgst_rate=line_item.cgst_rate,
					sgst_rate=line_item.sgst_rate,
					igst_rate=line_item.igst_rate,
					cess_rate=line_item.cess_rate,
					cgst_amount=line_item.cgst_amount,
					sgst_amount=line_item.sgst_amount,
					igst_amount=line_item.igst_amount,
					cess_amount=line_item.cess_amount,
					total_tax=line_item.total_tax,
					line_total=line_item.line_total,
				)
			duplicate = InvoiceService.recalculate_invoice(duplicate)
		return success_response("Invoice duplicated successfully", InvoiceDetailSerializer(duplicate).data, status.HTTP_201_CREATED)


class InvoiceGSTSummaryView(GenericAPIView):
	"""Return GST summary for a single invoice."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		invoice = Invoice.objects.prefetch_related("line_items").get(id=kwargs["pk"], company=request.user.company_profile)
		breakdown: dict[str, dict[str, Decimal]] = {}
		for line_item in invoice.line_items.all():
			rate_key = str(line_item.gst_rate)
			if rate_key not in breakdown:
				breakdown[rate_key] = {
					"gst_rate": line_item.gst_rate,
					"taxable_amount": Decimal("0.00"),
					"cgst_rate": line_item.cgst_rate,
					"cgst_amount": Decimal("0.00"),
					"sgst_rate": line_item.sgst_rate,
					"sgst_amount": Decimal("0.00"),
					"igst_rate": line_item.igst_rate,
					"igst_amount": Decimal("0.00"),
					"total_tax": Decimal("0.00"),
				}
			bucket = breakdown[rate_key]
			bucket["taxable_amount"] += line_item.taxable_amount
			bucket["cgst_amount"] += line_item.cgst_amount
			bucket["sgst_amount"] += line_item.sgst_amount
			bucket["igst_amount"] += line_item.igst_amount
			bucket["total_tax"] += line_item.total_tax
		return success_response(
			"Invoice GST summary retrieved successfully",
			{
				"invoice_number": invoice.invoice_number,
				"is_interstate": invoice.is_interstate,
				"gst_breakdown": list(breakdown.values()),
				"totals": {
					"subtotal": invoice.subtotal,
					"total_cgst": invoice.total_cgst,
					"total_sgst": invoice.total_sgst,
					"total_igst": invoice.total_igst,
					"total_tax": invoice.total_tax,
					"grand_total": invoice.grand_total,
				},
			},
			status.HTTP_200_OK,
		)


class InvoiceSummaryView(GenericAPIView):
	"""Return company invoice summary metrics."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		queryset = Invoice.objects.filter(company=request.user.company_profile)
		financial_year = request.query_params.get("financial_year")
		date_from = parse_date(request.query_params.get("date_from")) if request.query_params.get("date_from") else None
		date_to = parse_date(request.query_params.get("date_to")) if request.query_params.get("date_to") else None
		if financial_year:
			queryset = queryset.filter(financial_year=financial_year)
		if date_from:
			queryset = queryset.filter(invoice_date__gte=date_from)
		if date_to:
			queryset = queryset.filter(invoice_date__lte=date_to)

		totals = queryset.aggregate(
			total_invoices=Count("id"),
			total_revenue=Sum("grand_total", filter=Q(status=Invoice.StatusChoices.ISSUED)),
			total_tax_collected=Sum("total_tax", filter=Q(status=Invoice.StatusChoices.ISSUED)),
			total_draft=Count("id", filter=Q(status=Invoice.StatusChoices.DRAFT)),
			total_cancelled=Count("id", filter=Q(status=Invoice.StatusChoices.CANCELLED)),
		)
		monthly = (
			queryset.filter(status=Invoice.StatusChoices.ISSUED)
			.values("invoice_date__month")
			.annotate(count=Count("id"), revenue=Sum("grand_total"))
			.order_by("invoice_date__month")
		)
		data = {
			"total_invoices": totals["total_invoices"] or 0,
			"total_revenue": totals["total_revenue"] or 0,
			"total_tax_collected": totals["total_tax_collected"] or 0,
			"total_draft": totals["total_draft"] or 0,
			"total_cancelled": totals["total_cancelled"] or 0,
			"monthly_breakdown": [
				{"month": item["invoice_date__month"], "count": item["count"], "revenue": item["revenue"] or 0}
				for item in monthly
			],
		}
		return success_response("Invoice summary retrieved successfully", InvoiceSummarySerializer(data).data, status.HTTP_200_OK)


class CustomerInvoiceListView(GenericAPIView):
	"""List invoices for a specific party."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		customer = Customer.objects.get(id=kwargs["customer_pk"], company=request.user.company_profile)
		queryset = Invoice.objects.filter(company=request.user.company_profile, customer=customer)
		queryset = InvoiceFilter(request.query_params, queryset=queryset).qs.order_by("-invoice_date", "-created_at")
		page_size = int(request.query_params.get("page_size", 20))
		page = int(request.query_params.get("page", 1))
		total = queryset.count()
		items = queryset[(page - 1) * page_size : page * page_size]
		serializer = InvoiceListSerializer(items, many=True)
		response = success_response(
			"Party invoices retrieved successfully",
			{
				"invoices": serializer.data,
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


class InvoicePDFView(GenericAPIView):
	"""Generate and stream a PDF copy of an issued invoice."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		invoice = Invoice.objects.get(id=kwargs["pk"], company=request.user.company_profile)
		if invoice.status != Invoice.StatusChoices.ISSUED:
			return error_response("PDF only available for issued invoices", {"detail": "PDF only available for issued invoices"}, status.HTTP_400_BAD_REQUEST)

		num_copies = request.query_params.get("copies")
		num_copies_int = int(num_copies) if num_copies else None
		pdf_bytes = InvoicePDFService.generate_pdf(invoice, num_copies=num_copies_int)
		download = request.query_params.get("download", "true").lower() != "false"
		response = HttpResponse(pdf_bytes, content_type="application/pdf")
		disposition = "attachment" if download else "inline"
		response["Content-Disposition"] = f'{disposition}; filename="{InvoicePDFService.get_pdf_filename(invoice)}"'
		response["Content-Length"] = str(len(pdf_bytes))
		return response


class InvoiceEmailView(GenericAPIView):
	"""Send an issued invoice PDF to the party by email."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		invoice = Invoice.objects.get(id=kwargs["pk"], company=request.user.company_profile)
		if invoice.status != Invoice.StatusChoices.ISSUED:
			return error_response("Invoice email failed", {"detail": "PDF only available for issued invoices"}, status.HTTP_400_BAD_REQUEST)

		recipient = request.data.get("email") or invoice.customer_email
		if not recipient:
			return error_response("Invoice email failed", {"detail": "No email available"}, status.HTTP_400_BAD_REQUEST)

		try:
			InvoicePDFService.send_invoice_email(invoice, recipient_email=recipient)
		except Exception as exc:
			return error_response("Invoice email failed", {"detail": str(exc)}, status.HTTP_500_INTERNAL_SERVER_ERROR)
		return success_response(f"Invoice sent to {recipient}", {}, status.HTTP_200_OK)
