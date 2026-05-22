from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views import View

from core.views import OnboardingCheckMixin
from customers.models import Customer
from invoices.models import Invoice, InvoiceLineItem, InvoicePayment
from invoices.pdf_service import InvoicePDFService
from invoices.services import InvoiceNumberGenerator, InvoiceService
from products.models import Product

ALLOWED_ORDERING = {
    "invoice_date",
    "-invoice_date",
    "grand_total",
    "-grand_total",
    "created_at",
    "-created_at",
}


def _current_fy(today: date | None = None) -> str:
    today = today or date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    end_year_short = str((start_year + 1) % 100).zfill(2)
    return f"{str(start_year)[-2:]}-{end_year_short}"


def _to_decimal(raw, default: Decimal = Decimal("0")) -> Decimal:
    if raw in (None, ""):
        return default
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _preview_invoice_number(company) -> str:
    settings = company.invoice_settings
    return f"{settings.invoice_prefix}/{settings.financial_year}/{settings.invoice_counter:04d}"


def _parse_lines_from_post(request: HttpRequest) -> list[dict]:
    lines = []
    i = 0
    while f"lines[{i}][name]" in request.POST:
        name = (request.POST.get(f"lines[{i}][name]", "") or "").strip()
        if name:
            product_raw = (request.POST.get(f"lines[{i}][product_id]") or "").strip()
            lines.append(
                {
                    "product": product_raw or None,
                    "product_name": name,
                    "hsn_code": (request.POST.get(f"lines[{i}][hsn_code]", "") or "").strip(),
                    "description": (request.POST.get(f"lines[{i}][description]", "") or "").strip(),
                    "quantity": _to_decimal(request.POST.get(f"lines[{i}][quantity]", 1), Decimal("1")),
                    "unit": (request.POST.get(f"lines[{i}][unit]", "Pcs") or "Pcs").strip() or "Pcs",
                    "unit_price": _to_decimal(request.POST.get(f"lines[{i}][unit_price]", 0), Decimal("0")),
                    "discount_percent": _to_decimal(request.POST.get(f"lines[{i}][discount_percent]", 0), Decimal("0")),
                    "gst_rate": _to_decimal(request.POST.get(f"lines[{i}][gst_rate]", 18), Decimal("18")),
                    "cess_rate": _to_decimal(request.POST.get(f"lines[{i}][cess_rate]", 0), Decimal("0")),
                }
            )
        i += 1
    return lines


def _lines_to_json(lines: list[dict]) -> str:
    normalized = []
    for idx, line in enumerate(lines):
        normalized.append(
            {
                "id": line.get("id") or (idx + 1) * 1001,
                "product_id": str(line.get("product") or line.get("product_id") or ""),
                "name": line.get("product_name") or line.get("name") or "",
                "description": line.get("description") or "",
                "hsn_code": line.get("hsn_code") or "",
                "quantity": float(_to_decimal(line.get("quantity"), Decimal("1"))),
                "unit": line.get("unit") or "Pcs",
                "unit_price": float(_to_decimal(line.get("unit_price"), Decimal("0"))),
                "discount_percent": float(_to_decimal(line.get("discount_percent"), Decimal("0"))),
                "gst_rate": float(_to_decimal(line.get("gst_rate"), Decimal("18"))),
                "cess_rate": float(_to_decimal(line.get("cess_rate"), Decimal("0"))),
                "taxable_amount": float(_to_decimal(line.get("taxable_amount"), Decimal("0"))),
                "tax_amount": float(
                    _to_decimal(
                        line.get("tax_amount"),
                        _to_decimal(line.get("total_tax"), Decimal("0")),
                    )
                ),
                "line_total": float(_to_decimal(line.get("line_total"), Decimal("0"))),
            }
        )
    return json.dumps(normalized)


def _invoice_form_context(company, *, invoice=None, is_edit=False, existing_lines_json="[]", error_message="") -> dict:
    customers = Customer.objects.filter(company=company, is_active=True).order_by("name")[:50]
    products = Product.objects.filter(company=company, is_active=True).select_related("unit").order_by("name")
    return {
        "invoice": invoice,
        "invoice_number_preview": _preview_invoice_number(company),
        "inv_settings": company.invoice_settings,
        "customers": customers,
        "products": products,
        "today": date.today(),
        "is_edit": is_edit,
        "existing_lines_json": existing_lines_json,
        "page_title": "Edit Invoice" if is_edit else "New Invoice",
        "error_message": error_message,
    }


def _invoice_from_post(post_data) -> dict:
    return {
        "invoice_date": parse_date(post_data.get("invoice_date") or "") or date.today(),
        "due_date": parse_date(post_data.get("due_date") or "") or None,
        "place_of_supply": (post_data.get("place_of_supply") or "").strip(),
        "place_of_supply_code": (post_data.get("place_of_supply_code") or "").strip(),
        "reverse_charge": (post_data.get("reverse_charge") or "false").lower() == "true",
        "transport_mode": (post_data.get("transport_mode") or "").strip(),
        "vehicle_number": (post_data.get("vehicle_number") or "").strip(),
        "station": (post_data.get("station") or "").strip(),
        "eway_bill_number": (post_data.get("eway_bill_number") or "").strip(),
        "gr_rr_number": (post_data.get("gr_rr_number") or "").strip(),
        "order_by": (post_data.get("order_by") or "").strip(),
        "bags": (post_data.get("bags") or "").strip(),
        "freight_charges": _to_decimal(post_data.get("freight_charges") or "0"),
        "payment_mode": (post_data.get("payment_mode") or "").strip(),
        "ack_number": (post_data.get("ack_number") or "").strip(),
        "po_number": (post_data.get("po_number") or "").strip(),
        "po_date": parse_date(post_data.get("po_date") or "") or None,
        "notes": (post_data.get("notes") or "").strip(),
        "terms_and_conditions": (post_data.get("terms_and_conditions") or "").strip(),
        "use_esign": post_data.get("use_esign") == "esign",
        "customer_name": (post_data.get("customer_name") or "").strip(),
        "customer_gstin": (post_data.get("customer_gstin") or "").strip().upper(),
        "customer_state": (post_data.get("customer_state") or "").strip(),
        "customer_state_code": (post_data.get("customer_state_code") or "").strip(),
        "customer_mobile": (post_data.get("customer_mobile") or "").strip(),
        "customer_email": (post_data.get("customer_email") or "").strip(),
        "customer_address": (post_data.get("customer_address") or "").strip(),
        "shipping_same_as_billing": (post_data.get("shipping_same_as_billing") or "true").lower() in {"true", "1", "yes", "on"},
        "shipping_name": (post_data.get("shipping_name") or "").strip(),
        "shipping_address_line1": (post_data.get("shipping_address_line1") or "").strip(),
        "shipping_address_line2": (post_data.get("shipping_address_line2") or "").strip(),
        "shipping_city": (post_data.get("shipping_city") or "").strip(),
        "shipping_state": (post_data.get("shipping_state") or "").strip(),
        "shipping_state_code": (post_data.get("shipping_state_code") or "").strip(),
        "shipping_pincode": (post_data.get("shipping_pincode") or "").strip(),
        "shipping_country": (post_data.get("shipping_country") or "India").strip() or "India",
    }


def _invoice_from_post_for_template(post_data) -> SimpleNamespace:
    return SimpleNamespace(
        invoice_number=(post_data.get("invoice_number") or "").strip(),
        invoice_date=parse_date(post_data.get("invoice_date") or "") or date.today(),
        due_date=parse_date(post_data.get("due_date") or "") or None,
        place_of_supply=(post_data.get("place_of_supply") or "").strip(),
        place_of_supply_code=(post_data.get("place_of_supply_code") or "").strip(),
        reverse_charge=(post_data.get("reverse_charge") or "false").lower() == "true",
        customer_name=(post_data.get("customer_name") or "").strip(),
        customer_id=(post_data.get("customer_id") or "").strip(),
        customer_gstin=(post_data.get("customer_gstin") or "").strip().upper(),
        customer_state=(post_data.get("customer_state") or "").strip(),
        customer_state_code=(post_data.get("customer_state_code") or "").strip(),
        customer_mobile=(post_data.get("customer_mobile") or "").strip(),
        customer_address=(post_data.get("customer_address") or "").strip(),
        shipping_same_as_billing=(post_data.get("shipping_same_as_billing") or "true").lower() in {"true", "1", "yes", "on"},
        shipping_name=(post_data.get("shipping_name") or "").strip(),
        shipping_address_line1=(post_data.get("shipping_address_line1") or "").strip(),
        shipping_address_line2=(post_data.get("shipping_address_line2") or "").strip(),
        shipping_city=(post_data.get("shipping_city") or "").strip(),
        shipping_state=(post_data.get("shipping_state") or "").strip(),
        shipping_state_code=(post_data.get("shipping_state_code") or "").strip(),
        shipping_pincode=(post_data.get("shipping_pincode") or "").strip(),
        shipping_country=(post_data.get("shipping_country") or "India").strip() or "India",
        transport_mode=(post_data.get("transport_mode") or "").strip(),
        vehicle_number=(post_data.get("vehicle_number") or "").strip(),
        station=(post_data.get("station") or "").strip(),
        eway_bill_number=(post_data.get("eway_bill_number") or "").strip(),
        gr_rr_number=(post_data.get("gr_rr_number") or "").strip(),
        order_by=(post_data.get("order_by") or "").strip(),
        bags=(post_data.get("bags") or "").strip(),
        freight_charges=_to_decimal(post_data.get("freight_charges") or "0"),
        payment_mode=(post_data.get("payment_mode") or "").strip(),
        ack_number=(post_data.get("ack_number") or "").strip(),
        po_number=(post_data.get("po_number") or "").strip(),
        po_date=parse_date(post_data.get("po_date") or "") or None,
        notes=(post_data.get("notes") or "").strip(),
        terms_and_conditions=(post_data.get("terms_and_conditions") or "").strip(),
        use_esign=post_data.get("use_esign") == "esign",
    )


@method_decorator(login_required, name="dispatch")
class InvoiceListView(OnboardingCheckMixin, View):
    template_name = "invoices_ui/invoice_list.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        queryset = Invoice.objects.filter(company=company).select_related("customer")

        search = (request.GET.get("search") or "").strip()
        status_filter = (request.GET.get("status") or "").strip()
        date_from_raw = (request.GET.get("date_from") or "").strip()
        date_to_raw = (request.GET.get("date_to") or "").strip()
        financial_year = (request.GET.get("financial_year") or "").strip()
        customer_id = (request.GET.get("customer") or "").strip()
        ordering = (request.GET.get("ordering") or "-invoice_date").strip()
        payment_status_filter = (request.GET.get("payment_status") or "").strip()
        payment_mode_filter = (request.GET.get("payment_mode") or "").strip()

        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(customer__name__icontains=search)
                | Q(customer__display_name__icontains=search)
            )
        if status_filter in {Invoice.StatusChoices.DRAFT, Invoice.StatusChoices.ISSUED, Invoice.StatusChoices.CANCELLED}:
            queryset = queryset.filter(status=status_filter)

        date_from = parse_date(date_from_raw) if date_from_raw else None
        date_to = parse_date(date_to_raw) if date_to_raw else None
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)

        if financial_year:
            queryset = queryset.filter(financial_year=financial_year)
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if payment_status_filter in {"UNPAID", "PARTIAL", "PAID"}:
            queryset = queryset.filter(payment_status=payment_status_filter)
        if payment_mode_filter:
            valid_modes = {m[0] for m in InvoicePayment.PAYMENT_MODE_CHOICES}
            if payment_mode_filter in valid_modes:
                queryset = queryset.filter(payments__payment_mode=payment_mode_filter).distinct()

        if ordering not in ALLOWED_ORDERING:
            ordering = "-invoice_date"
        queryset = queryset.order_by(ordering, "-created_at")

        paginator = Paginator(queryset, 20)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        summary_qs = Invoice.objects.filter(company=company)
        if financial_year:
            summary_qs = summary_qs.filter(financial_year=financial_year)

        issued_qs = summary_qs.filter(status=Invoice.StatusChoices.ISSUED)
        issued_total = issued_qs.aggregate(v=Sum("grand_total")).get("v") or Decimal("0")
        received_total = issued_qs.aggregate(v=Sum("amount_received")).get("v") or Decimal("0")

        summary = {
            "total": summary_qs.count(),
            "issued_count": issued_qs.count(),
            "issued_total": issued_total,
            "received_total": received_total,
            "outstanding_total": issued_total - received_total,
            "draft_count": summary_qs.filter(status=Invoice.StatusChoices.DRAFT).count(),
            "cancelled_count": summary_qs.filter(status=Invoice.StatusChoices.CANCELLED).count(),
        }

        financial_years = (
            Invoice.objects.filter(company=company)
            .exclude(financial_year="")
            .values_list("financial_year", flat=True)
            .distinct()
            .order_by("-financial_year")
        )

        current_filters = {
            "search": search,
            "status": status_filter,
            "date_from": date_from_raw,
            "date_to": date_to_raw,
            "financial_year": financial_year,
            "customer": customer_id,
            "ordering": ordering,
            "payment_status": payment_status_filter,
            "payment_mode": payment_mode_filter,
        }

        context = {
            "invoices": page_obj.object_list,
            "page_obj": page_obj,
            "status_choices": [Invoice.StatusChoices.DRAFT, Invoice.StatusChoices.ISSUED, Invoice.StatusChoices.CANCELLED],
            "financial_years": financial_years,
            "summary": summary,
            "current_filters": current_filters,
            "payment_modes": InvoicePayment.PAYMENT_MODE_CHOICES,
            "page_title": "Invoices",
        }
        if request.headers.get("HX-Request"):
            return render(request, "invoices_ui/_invoice_table.html", context)
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class InvoiceCreateView(OnboardingCheckMixin, View):
    template_name = "invoices_ui/invoice_form.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        context = _invoice_form_context(company, invoice=None, is_edit=False, existing_lines_json="[]")
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        lines = _parse_lines_from_post(request)

        if not lines:
            context = _invoice_form_context(
                company,
                invoice=_invoice_from_post_for_template(request.POST),
                is_edit=False,
                existing_lines_json="[]",
                error_message="At least one line item is required.",
            )
            return render(request, self.template_name, context, status=400)

        customer = None
        customer_id = (request.POST.get("customer_id") or "").strip()
        if customer_id:
            customer = get_object_or_404(Customer, company=company, pk=customer_id)

        invoice_data = _invoice_from_post(request.POST)
        action = (request.POST.get("action") or "draft").strip().lower()

        try:
            invoice = InvoiceService.create_invoice(
                company=company,
                customer=customer,
                invoice_data=invoice_data,
                line_items_data=lines,
                user=request.user,
            )
            if action == "issue":
                invoice = InvoiceService.issue_invoice(invoice, request.user)
                messages.success(request, f"Invoice {invoice.invoice_number} created and issued")
            else:
                messages.success(request, f"Invoice {invoice.invoice_number} created")
            return redirect("invoices_ui:invoice-detail", pk=invoice.pk)
        except Exception as exc:
            context = _invoice_form_context(
                company,
                invoice=_invoice_from_post_for_template(request.POST),
                is_edit=False,
                existing_lines_json=_lines_to_json(lines),
                error_message=str(exc),
            )
            return render(request, self.template_name, context, status=400)


@method_decorator(login_required, name="dispatch")
class InvoiceDetailView(OnboardingCheckMixin, View):
    template_name = "invoices_ui/invoice_detail.html"

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice.objects.filter(company=company).prefetch_related("line_items"), pk=pk)
        context = {
            "invoice": invoice,
            "gst_breakdown": InvoicePDFService.get_gst_breakdown(invoice),
            "can_edit": invoice.status == Invoice.StatusChoices.DRAFT,
            "can_issue": invoice.status == Invoice.StatusChoices.DRAFT,
            "can_cancel": invoice.status == Invoice.StatusChoices.ISSUED,
            "can_duplicate": True,
            "page_title": invoice.invoice_number,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class InvoiceUpdateView(OnboardingCheckMixin, View):
    template_name = "invoices_ui/invoice_form.html"

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice.objects.filter(company=company).prefetch_related("line_items"), pk=pk)

        if invoice.status != Invoice.StatusChoices.DRAFT:
            messages.error(request, "Only draft invoices can be edited")
            return redirect("invoices_ui:invoice-detail", pk=invoice.pk)

        existing_lines_json = json.dumps(
            [
                {
                    "id": int(str(item.id).replace("-", "")[:12], 16),
                    "product_id": str(item.product_id) if item.product_id else "",
                    "name": item.product_name,
                    "description": item.description,
                    "hsn_code": item.hsn_code,
                    "quantity": float(item.quantity),
                    "unit": item.unit,
                    "unit_price": float(item.unit_price),
                    "discount_percent": float(item.discount_percent),
                    "gst_rate": float(item.gst_rate),
                    "cess_rate": float(item.cess_rate),
                    "taxable_amount": float(item.taxable_amount),
                    "tax_amount": float(item.total_tax),
                    "line_total": float(item.line_total),
                }
                for item in invoice.line_items.all()
            ]
        )
        context = _invoice_form_context(company, invoice=invoice, is_edit=True, existing_lines_json=existing_lines_json)
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice.objects.filter(company=company).prefetch_related("line_items"), pk=pk)

        if invoice.status != Invoice.StatusChoices.DRAFT:
            messages.error(request, "Only draft invoices can be edited")
            return redirect("invoices_ui:invoice-detail", pk=invoice.pk)

        lines = _parse_lines_from_post(request)
        if not lines:
            context = _invoice_form_context(
                company,
                invoice=_invoice_from_post_for_template(request.POST),
                is_edit=True,
                existing_lines_json="[]",
                error_message="At least one line item is required.",
            )
            return render(request, self.template_name, context, status=400)

        customer = None
        customer_id = (request.POST.get("customer_id") or "").strip()
        if customer_id:
            customer = get_object_or_404(Customer, company=company, pk=customer_id)

        data = _invoice_from_post(request.POST)
        action = (request.POST.get("action") or "draft").strip().lower()

        try:
            with transaction.atomic():
                for field in [
                    "invoice_date",
                    "due_date",
                    "place_of_supply",
                    "place_of_supply_code",
                    "reverse_charge",
                    "transport_mode",
                    "vehicle_number",
                    "station",
                    "eway_bill_number",
                    "gr_rr_number",
                    "order_by",
                    "bags",
                    "freight_charges",
                    "payment_mode",
                    "ack_number",
                    "po_number",
                    "po_date",
                    "notes",
                    "terms_and_conditions",
                    "use_esign",
                ]:
                    setattr(invoice, field, data.get(field))

                invoice.customer = customer
                if customer:
                    InvoiceService._snapshot_customer(invoice, customer)
                    invoice.is_interstate = bool(
                        invoice.place_of_supply_code
                        and customer.billing_state_code
                        and invoice.place_of_supply_code != customer.billing_state_code
                    )
                else:
                    InvoiceService._snapshot_manual_customer(invoice, data)
                    invoice.is_interstate = False

                InvoiceService._snapshot_shipping(invoice, customer, data)
                InvoiceService._snapshot_bank(invoice, company)
                invoice.updated_by = request.user
                invoice.save()

                invoice.line_items.all().delete()
                line_items = []
                for idx, item_data in enumerate(lines, start=1):
                    line_item, _ = InvoiceService._build_line_item(invoice, company, item_data, idx)
                    line_items.append(line_item)
                InvoiceLineItem.objects.bulk_create(line_items)
                invoice = InvoiceService.recalculate_invoice(invoice)

                if action == "issue":
                    invoice = InvoiceService.issue_invoice(invoice, request.user)
                    messages.success(request, f"Invoice {invoice.invoice_number} updated and issued successfully")
                else:
                    messages.success(request, "Invoice updated successfully")

            return redirect("invoices_ui:invoice-detail", pk=invoice.pk)
        except Exception as exc:
            context = _invoice_form_context(
                company,
                invoice=_invoice_from_post_for_template(request.POST),
                is_edit=True,
                existing_lines_json=_lines_to_json(lines),
                error_message=str(exc),
            )
            return render(request, self.template_name, context, status=400)


@method_decorator(login_required, name="dispatch")
class InvoiceIssueView(OnboardingCheckMixin, View):
    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)
        return render(request, "invoices_ui/_issue_modal.html", {"invoice": invoice})

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)
        try:
            updated = InvoiceService.issue_invoice(invoice, request.user)
            messages.success(request, f"Invoice {updated.invoice_number} issued successfully")
        except Exception as exc:
            messages.error(request, str(exc))
        if request.headers.get("HX-Request"):
            response = HttpResponse("")
            response["HX-Redirect"] = reverse("invoices_ui:invoice-detail", kwargs={"pk": invoice.pk})
            return response
        return redirect("invoices_ui:invoice-detail", pk=invoice.pk)


@method_decorator(login_required, name="dispatch")
class InvoiceCancelView(View):
    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)
        return render(request, "invoices_ui/_cancel_modal.html", {"invoice": invoice})

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)
        reason = (request.POST.get("cancellation_reason") or "").strip()
        if len(reason) < 10:
            response = render(
                request,
                "invoices_ui/_cancel_modal.html",
                {"invoice": invoice, "error_message": "Cancellation reason must be at least 10 characters."},
                status=400,
            )
            return response

        try:
            cancelled = InvoiceService.cancel_invoice(invoice, reason, request.user)
            messages.success(request, f"Invoice {cancelled.invoice_number} cancelled")
            response = HttpResponse("")
            response["HX-Redirect"] = reverse("invoices_ui:invoice-detail", kwargs={"pk": invoice.pk})
            return response
        except Exception as exc:
            response = render(
                request,
                "invoices_ui/_cancel_modal.html",
                {"invoice": invoice, "error_message": str(exc)},
                status=400,
            )
            return response


@method_decorator(login_required, name="dispatch")
class InvoiceDuplicateView(View):
    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        source = get_object_or_404(
            Invoice.objects.filter(company=company).select_related("customer").prefetch_related("line_items"),
            pk=pk,
        )

        try:
            with transaction.atomic():
                duplicate = Invoice.objects.create(
                    company=source.company,
                    customer=source.customer,
                    invoice_number=InvoiceNumberGenerator.generate(source.company),
                    invoice_date=date.today(),
                    due_date=source.due_date,
                    financial_year=source.company.invoice_settings.financial_year,
                    status=Invoice.StatusChoices.DRAFT,
                    place_of_supply=source.place_of_supply,
                    place_of_supply_code=source.place_of_supply_code,
                    reverse_charge=source.reverse_charge,
                    is_interstate=source.is_interstate,
                    transport_mode=source.transport_mode,
                    vehicle_number=source.vehicle_number,
                    station=source.station,
                    eway_bill_number="",
                    gr_rr_number="",
                    order_by=source.order_by,
                    bags=source.bags,
                    freight_charges=source.freight_charges,
                    payment_mode=source.payment_mode,
                    ack_number="",
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
                    irn="",
                    issued_at=None,
                    cancelled_at=None,
                    cancellation_reason="",
                    use_esign=source.use_esign,
                    created_by=request.user,
                    updated_by=request.user,
                )

                for idx, item in enumerate(source.line_items.all(), start=1):
                    InvoiceLineItem.objects.create(
                        invoice=duplicate,
                        product=item.product,
                        sr_no=idx,
                        product_name=item.product_name,
                        hsn_code=item.hsn_code,
                        description=item.description,
                        quantity=item.quantity,
                        unit=item.unit,
                        unit_price=item.unit_price,
                        discount_percent=item.discount_percent,
                        discount_amount=item.discount_amount,
                        taxable_amount=item.taxable_amount,
                        gst_rate=item.gst_rate,
                        cgst_rate=item.cgst_rate,
                        sgst_rate=item.sgst_rate,
                        igst_rate=item.igst_rate,
                        cess_rate=item.cess_rate,
                        cgst_amount=item.cgst_amount,
                        sgst_amount=item.sgst_amount,
                        igst_amount=item.igst_amount,
                        cess_amount=item.cess_amount,
                        total_tax=item.total_tax,
                        line_total=item.line_total,
                    )

                duplicate = InvoiceService.recalculate_invoice(duplicate)

            messages.success(request, f"Invoice duplicated as {duplicate.invoice_number}")
            return redirect("invoices_ui:invoice-edit", pk=duplicate.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("invoices_ui:invoice-detail", pk=source.pk)


@method_decorator(login_required, name="dispatch")
class InvoicePDFView(OnboardingCheckMixin, View):
    """
    Generates and downloads invoice PDF using Playwright.
    GET /invoices/<uuid:pk>/pdf/
    Query params:
      copies=1|2|3  (default from invoice settings)
      download=true|false (default true)
        true  = attachment (download)
        false = inline (view in browser)
    """

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        try:
            invoice = Invoice.objects.get(pk=pk, company=company)
        except Invoice.DoesNotExist:
            messages.error(request, "Invoice not found")
            return redirect("invoices_ui:invoice-list")

        if invoice.status != Invoice.StatusChoices.ISSUED:
            messages.error(
                request,
                "PDF is only available for issued invoices. "
                "Please issue the invoice first.",
            )
            return redirect("invoices_ui:invoice-detail", pk=pk)

        try:
            copies = int(request.GET.get("copies", 1))
            copies = max(1, min(3, copies))
        except (ValueError, TypeError):
            copies = 1

        download = request.GET.get("download", "true").lower()
        is_download = download != "false"

        try:
            pdf_bytes = InvoicePDFService.generate_pdf(invoice, copies)
        except Exception as exc:
            messages.error(request, f"PDF generation failed: {str(exc)}")
            return redirect("invoices_ui:invoice-detail", pk=pk)

        filename = InvoicePDFService.get_pdf_filename(invoice)
        disposition = "attachment" if is_download else "inline"

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        response["Content-Length"] = len(pdf_bytes)
        return response


@method_decorator(login_required, name="dispatch")
class InvoiceEmailView(OnboardingCheckMixin, View):
    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)
        return render(request, "invoices_ui/_email_modal.html", {"invoice": invoice})

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)

        if invoice.status != Invoice.StatusChoices.ISSUED:
            return HttpResponse('<div class="alert alert-danger">Only issued invoices can be emailed.</div>')

        recipient = (request.POST.get("email") or "").strip() or invoice.customer_email
        if not recipient:
            return HttpResponse('<div class="alert alert-danger">No recipient email provided.</div>')

        try:
            InvoicePDFService.send_invoice_email(invoice, recipient_email=recipient)
            return HttpResponse('<div class="alert alert-success">Invoice email sent successfully.</div>')
        except Exception as exc:
            return HttpResponse(f'<div class="alert alert-danger">{str(exc)}</div>')


@method_decorator(login_required, name="dispatch")
class CustomerSearchView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        query = (request.GET.get("q") or request.GET.get("customer_search_q") or "").strip()

        customers = []
        if len(query) >= 2:
            customers = (
                Customer.objects.filter(company=company, is_active=True)
                .filter(
                    Q(name__icontains=query)
                    | Q(display_name__icontains=query)
                    | Q(gstin__icontains=query)
                    | Q(mobile_primary__icontains=query)
                )
                .order_by("name")[:8]
            )
        return render(request, "invoices_ui/_customer_results.html", {"customers": customers})


@method_decorator(login_required, name="dispatch")
class ProductSearchView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        query = (request.GET.get("q") or "").strip()

        base_qs = (
            Product.objects.filter(company=company, is_active=True)
            .select_related("unit")
            .order_by("name")
        )

        if query:
            products = base_qs.filter(
                Q(name__icontains=query)
                | Q(sku__icontains=query)
                | Q(hsn_code__icontains=query)
            )[:8]
        else:
            products = base_qs[:8]

        return render(request, "invoices_ui/_product_results.html", {"products": products})


@method_decorator(login_required, name="dispatch")
class CustomerSearchJsonView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        from django.http import JsonResponse
        company = request.user.company_profile
        query = (request.GET.get("q") or "").strip()

        qs = Customer.objects.filter(company=company, is_active=True)
        if len(query) >= 2:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(display_name__icontains=query)
                | Q(gstin__icontains=query)
                | Q(mobile_primary__icontains=query)
            )
        customers = qs.order_by("name")[:10]

        data = [
            {
                "id": str(c.id),
                "name": c.name,
                "display_name": c.display_name or c.name,
                "gstin": c.gstin,
                "billing_state": c.billing_state,
                "billing_state_code": c.billing_state_code,
                "billing_address_line1": c.billing_address_line1,
                "billing_address_line2": c.billing_address_line2,
                "billing_city": c.billing_city,
                "billing_pincode": c.billing_pincode,
                "billing_country": c.billing_country,
                "full_billing_address": c.full_billing_address,
                "mobile_primary": c.mobile_primary,
                "email": c.email,
            }
            for c in customers
        ]
        return JsonResponse(data, safe=False)


@method_decorator(login_required, name="dispatch")
class ProductSearchJsonView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        from django.http import JsonResponse
        company = request.user.company_profile
        query = (request.GET.get("q") or "").strip()

        base_qs = (
            Product.objects.filter(company=company, is_active=True)
            .select_related("unit")
            .order_by("name")
        )

        if query:
            qs = base_qs.filter(
                Q(name__icontains=query)
                | Q(sku__icontains=query)
                | Q(hsn_code__icontains=query)
            )[:10]
        else:
            qs = base_qs[:10]

        data = [
            {
                "id": str(p.id),
                "name": p.name,
                "hsn_code": p.hsn_code or "",
                "sku": p.sku or "",
                "unit": p.unit.short_name if p.unit else "Pcs",
                "selling_price": float(p.selling_price),
                "gst_rate": float(p.gst_rate),
                "cess_rate": float(p.cess_rate),
                "track_inventory": p.track_inventory,
                "current_stock": float(p.current_stock) if p.track_inventory else None,
                "is_low_stock": p.is_low_stock if p.track_inventory else False,
            }
            for p in qs
        ]
        return JsonResponse(data, safe=False)


@method_decorator(login_required, name="dispatch")
class InvoiceRecordPaymentView(OnboardingCheckMixin, View):
    """Record a payment received against an issued invoice."""

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)
        if invoice.status != Invoice.StatusChoices.ISSUED:
            return HttpResponse('<div class="alert alert-danger">Only issued invoices can receive payments.</div>', status=400)
        remaining = invoice.grand_total - invoice.amount_received
        return render(request, "invoices_ui/_payment_modal.html", {
            "invoice": invoice,
            "remaining": remaining,
            "payment_modes": InvoicePayment.PAYMENT_MODE_CHOICES,
            "today": date.today(),
        })

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from customers.services import CustomerService

        company = request.user.company_profile
        invoice = get_object_or_404(Invoice, company=company, pk=pk)

        if invoice.status != Invoice.StatusChoices.ISSUED:
            return HttpResponse('<div class="alert alert-danger">Only issued invoices can receive payments.</div>', status=400)

        amount_str = (request.POST.get("amount") or "").strip()
        payment_mode = (request.POST.get("payment_mode") or "").strip()
        payment_date_str = (request.POST.get("payment_date") or "").strip()
        reference = (request.POST.get("reference") or "").strip()

        errors: dict[str, str] = {}
        amount = None
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                errors["amount"] = "Amount must be greater than zero"
        except (InvalidOperation, ValueError, TypeError):
            errors["amount"] = "Enter a valid amount"

        valid_modes = {m[0] for m in InvoicePayment.PAYMENT_MODE_CHOICES}
        if payment_mode not in valid_modes:
            errors["payment_mode"] = "Select a valid payment mode"

        payment_date = parse_date(payment_date_str) if payment_date_str else None
        if not payment_date:
            payment_date = date.today()

        if errors:
            remaining = invoice.grand_total - invoice.amount_received
            return render(request, "invoices_ui/_payment_modal.html", {
                "invoice": invoice,
                "remaining": remaining,
                "payment_modes": InvoicePayment.PAYMENT_MODE_CHOICES,
                "today": payment_date,
                "errors": errors,
            }, status=400)

        try:
            with transaction.atomic():
                InvoicePayment.objects.create(
                    invoice=invoice,
                    amount=amount,
                    payment_mode=payment_mode,
                    payment_date=payment_date,
                    reference=reference,
                    created_by=request.user,
                )

                invoice.amount_received = (invoice.amount_received or Decimal("0")) + amount
                if invoice.amount_received >= invoice.grand_total:
                    invoice.payment_status = "PAID"
                elif invoice.amount_received > 0:
                    invoice.payment_status = "PARTIAL"
                else:
                    invoice.payment_status = "UNPAID"
                invoice.save(update_fields=["amount_received", "payment_status", "updated_at"])

                if invoice.customer_id:
                    CustomerService.update_balance(invoice.customer, amount, "subtract")

            messages.success(request, f"Payment of ₹{amount:,.2f} recorded for {invoice.invoice_number}")
            response = HttpResponse("")
            response["HX-Redirect"] = reverse("invoices_ui:invoice-list")
            return response
        except Exception as exc:
            remaining = invoice.grand_total - invoice.amount_received
            return render(request, "invoices_ui/_payment_modal.html", {
                "invoice": invoice,
                "remaining": remaining,
                "payment_modes": InvoicePayment.PAYMENT_MODE_CHOICES,
                "today": payment_date,
                "error_message": str(exc),
            }, status=500)


@method_decorator(login_required, name="dispatch")
class CustomerQuickCreateView(View):
    """Create a party inline from the invoice form and return JSON."""

    def post(self, request: HttpRequest) -> HttpResponse:
        import re
        from django.http import JsonResponse

        company = request.user.company_profile
        errors: dict[str, str] = {}

        name = (request.POST.get("name") or "").strip()
        display_name = (request.POST.get("display_name") or "").strip()
        party_type = (request.POST.get("party_type") or Customer.PARTY_BUSINESS).strip()
        gstin = (request.POST.get("gstin") or "").strip().upper()
        mobile_primary = (request.POST.get("mobile_primary") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        billing_address_line1 = (request.POST.get("billing_address_line1") or "").strip()
        billing_address_line2 = (request.POST.get("billing_address_line2") or "").strip()
        billing_city = (request.POST.get("billing_city") or "").strip()
        billing_state = (request.POST.get("billing_state") or "").strip()
        billing_state_code = (request.POST.get("billing_state_code") or "").strip()
        billing_pincode = (request.POST.get("billing_pincode") or "").strip()
        billing_country = (request.POST.get("billing_country") or "India").strip() or "India"

        if gstin and not billing_state_code and len(gstin) >= 2:
            billing_state_code = gstin[:2]

        if party_type not in {c[0] for c in Customer.PARTY_TYPE_CHOICES}:
            party_type = Customer.PARTY_BUSINESS

        GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
        SC_RE = re.compile(r"^[0-9]{2}$")

        if not name:
            errors["name"] = "Legal / Trade name is required"
        elif Customer.objects.filter(company=company, name__iexact=name).exists():
            errors["name"] = "A party with this name already exists"

        if gstin and not GSTIN_RE.match(gstin):
            errors["gstin"] = "Enter a valid GSTIN"

        if not mobile_primary:
            errors["mobile_primary"] = "Mobile number is required"
        if not billing_address_line1:
            errors["billing_address_line1"] = "Address line 1 is required"
        if not billing_city:
            errors["billing_city"] = "City is required"
        if not billing_state:
            errors["billing_state"] = "State is required"
        if not billing_state_code:
            errors["billing_state_code"] = "State code is required"
        elif not SC_RE.match(billing_state_code):
            errors["billing_state_code"] = "Must be exactly 2 digits"
        if not billing_pincode:
            errors["billing_pincode"] = "Pincode is required"

        if errors:
            return JsonResponse({"success": False, "errors": errors}, status=400)

        customer = Customer.objects.create(
            company=company,
            name=name,
            display_name=display_name,
            party_type=party_type,
            gstin=gstin,
            mobile_primary=mobile_primary,
            email=email,
            billing_address_line1=billing_address_line1,
            billing_address_line2=billing_address_line2,
            billing_city=billing_city,
            billing_state=billing_state,
            billing_state_code=billing_state_code,
            billing_pincode=billing_pincode,
            billing_country=billing_country,
        )

        return JsonResponse({
            "success": True,
            "customer": {
                "id": str(customer.id),
                "name": customer.name,
                "display_name": customer.display_name or customer.name,
                "gstin": customer.gstin,
                "billing_state": customer.billing_state,
                "billing_state_code": customer.billing_state_code,
                "mobile_primary": customer.mobile_primary,
            },
        })
