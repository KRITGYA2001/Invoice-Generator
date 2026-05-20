from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views import View

from core.views import OnboardingCheckMixin
from customers.models import Customer, CustomerContact, CustomerNote
from customers.services import CustomerService

GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
STATE_CODE_REGEX = re.compile(r"^[0-9]{2}$")
ALLOWED_ORDERING = {"name", "-name", "current_balance", "-current_balance", "created_at", "-created_at"}


def _to_bool(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def _current_fy_start(today: date) -> date:
    year = today.year if today.month >= 4 else today.year - 1
    return date(year, 4, 1)


def _default_statement_dates(request: HttpRequest) -> tuple[date, date]:
    today = date.today()
    range_key = (request.GET.get("range") or "").strip().lower()

    if range_key == "this_month":
        return today.replace(day=1), today

    if range_key == "last_fy":
        current_start = _current_fy_start(today)
        prev_start = date(current_start.year - 1, 4, 1)
        prev_end = current_start - timedelta(days=1)
        return prev_start, prev_end

    if range_key == "this_fy":
        return _current_fy_start(today), today

    date_from = parse_date(request.GET.get("date_from") or "")
    date_to = parse_date(request.GET.get("date_to") or "")
    return date_from or _current_fy_start(today), date_to or today


def _parse_decimal(raw: str, field: str, errors: dict[str, str], *, default: Decimal = Decimal("0")) -> Decimal:
    value_raw = (raw or "").strip()
    if value_raw == "":
        return default
    try:
        return Decimal(value_raw)
    except (InvalidOperation, ValueError):
        errors[field] = "Enter a valid number"
        return default


def _parse_non_negative_int(raw: str, field: str, errors: dict[str, str], *, default: int = 0) -> int:
    value_raw = (raw or "").strip()
    if value_raw == "":
        return default
    try:
        value = int(value_raw)
    except ValueError:
        errors[field] = "Enter a valid whole number"
        return default
    if value < 0:
        errors[field] = "Must be 0 or greater"
        return default
    return value


def _customer_form_context(company, *, is_edit: bool, customer: Customer | None = None, form_data=None, form_errors=None) -> dict:
    safe_customer = customer or Customer()
    safe_form_data = form_data or {}
    return {
        "party_types": Customer.PARTY_TYPE_CHOICES,
        "is_edit": is_edit,
        "customer": safe_customer,
        "form_data": safe_form_data,
        "form_errors": form_errors or {},
        "page_title": "Edit Party" if is_edit else "New Party",
    }


def _apply_customer_payload(request: HttpRequest, customer: Customer, *, is_edit: bool) -> tuple[dict, dict]:
    company = request.user.company_profile
    form_data = request.POST.copy()
    errors: dict[str, str] = {}

    name = (request.POST.get("name") or "").strip()
    display_name = (request.POST.get("display_name") or "").strip()
    party_type = (request.POST.get("party_type") or Customer.PARTY_BUSINESS).strip()
    gstin = (request.POST.get("gstin") or "").strip().upper()
    pan = (request.POST.get("pan") or "").strip().upper()

    billing_state_code = (request.POST.get("billing_state_code") or "").strip()
    if gstin and not billing_state_code and len(gstin) >= 2:
        billing_state_code = gstin[:2]
        form_data["billing_state_code"] = billing_state_code

    mobile_primary = (request.POST.get("mobile_primary") or "").strip()
    mobile_secondary = (request.POST.get("mobile_secondary") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    website = (request.POST.get("website") or "").strip()

    billing_address_line1 = (request.POST.get("billing_address_line1") or "").strip()
    billing_address_line2 = (request.POST.get("billing_address_line2") or "").strip()
    billing_city = (request.POST.get("billing_city") or "").strip()
    billing_state = (request.POST.get("billing_state") or "").strip()
    billing_pincode = (request.POST.get("billing_pincode") or "").strip()
    billing_country = (request.POST.get("billing_country") or "India").strip() or "India"

    credit_limit = _parse_decimal(request.POST.get("credit_limit") or "0", "credit_limit", errors)
    payment_terms_days = _parse_non_negative_int(request.POST.get("payment_terms_days") or "0", "payment_terms_days", errors)
    opening_balance = _parse_decimal(request.POST.get("opening_balance") or "0", "opening_balance", errors)
    notes = (request.POST.get("notes") or "").strip()

    if not name:
        errors["name"] = "Legal / Trade name is required"
    else:
        qs = Customer.objects.filter(company=company, name__iexact=name)
        if is_edit:
            qs = qs.exclude(pk=customer.pk)
        if qs.exists():
            errors["name"] = "A party with this name already exists"

    if party_type not in {choice[0] for choice in Customer.PARTY_TYPE_CHOICES}:
        errors["party_type"] = "Select a valid party type"

    if gstin and not GSTIN_REGEX.match(gstin):
        errors["gstin"] = "Enter a valid GSTIN"

    if not billing_address_line1:
        errors["billing_address_line1"] = "Billing address line 1 is required"
    if not billing_city:
        errors["billing_city"] = "Billing city is required"
    if not billing_state:
        errors["billing_state"] = "Billing state is required"
    if not billing_state_code:
        errors["billing_state_code"] = "Billing state code is required"
    elif not STATE_CODE_REGEX.match(billing_state_code):
        errors["billing_state_code"] = "Billing state code must be exactly 2 digits"
    if not billing_pincode:
        errors["billing_pincode"] = "Billing pincode is required"

    if credit_limit < 0:
        errors["credit_limit"] = "Credit limit must be 0 or greater"
    if payment_terms_days < 0:
        errors["payment_terms_days"] = "Payment terms must be 0 or greater"

    if errors:
        return form_data, errors

    customer.name = name
    customer.display_name = display_name
    customer.party_type = party_type
    customer.gstin = gstin
    customer.pan = pan
    customer.mobile_primary = mobile_primary
    customer.mobile_secondary = mobile_secondary
    customer.email = email
    customer.website = website

    customer.billing_address_line1 = billing_address_line1
    customer.billing_address_line2 = billing_address_line2
    customer.billing_city = billing_city
    customer.billing_state = billing_state
    customer.billing_state_code = billing_state_code
    customer.billing_pincode = billing_pincode
    customer.billing_country = billing_country

    customer.credit_limit = credit_limit
    customer.payment_terms_days = payment_terms_days

    if not is_edit:
        customer.opening_balance = opening_balance

    customer.notes = notes
    customer.save()

    return form_data, {}


@method_decorator(login_required, name="dispatch")
class CustomerListView(OnboardingCheckMixin, View):
    template_name = "customers/customer_list.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        queryset = Customer.objects.filter(company=company)

        search = (request.GET.get("search") or "").strip()
        party_type = (request.GET.get("party_type") or "").strip()
        state = (request.GET.get("state") or "").strip()
        is_active = (request.GET.get("is_active") or "").strip()
        over_limit = _to_bool(request.GET.get("over_limit"))
        ordering = (request.GET.get("ordering") or "name").strip()

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(display_name__icontains=search)
                | Q(gstin__icontains=search)
                | Q(mobile_primary__icontains=search)
            )
        if party_type:
            queryset = queryset.filter(party_type=party_type)
        if state:
            queryset = queryset.filter(billing_state__icontains=state)
        if is_active != "false":
            queryset = queryset.filter(is_active=True)
        if over_limit:
            queryset = queryset.filter(credit_limit__gt=0, current_balance__gt=F("credit_limit"))

        if ordering not in ALLOWED_ORDERING:
            ordering = "name"
        queryset = queryset.order_by(ordering)

        page_number = int(request.GET.get("page", 1) or 1)
        paginator = Paginator(queryset, 20)
        page_obj = paginator.get_page(page_number)

        states = (
            Customer.objects.filter(company=company)
            .exclude(billing_state="")
            .values_list("billing_state", flat=True)
            .distinct()
            .order_by("billing_state")
        )

        current_filters = {
            "search": search,
            "party_type": party_type,
            "state": state,
            "is_active": is_active,
            "over_limit": over_limit,
        }

        context = {
            "customers": page_obj.object_list,
            "page_obj": page_obj,
            "party_types": Customer.PARTY_TYPE_CHOICES,
            "states": states,
            "summary": CustomerService.get_customer_summary(company),
            "current_filters": current_filters,
            "ordering": ordering,
            "page_title": "Parties",
        }

        if request.headers.get("HX-Request"):
            return render(request, "customers/_customer_table.html", context)
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class CustomerCreateView(OnboardingCheckMixin, View):
    template_name = "customers/customer_form.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            self.template_name,
            _customer_form_context(request.user.company_profile, is_edit=False),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        customer = Customer(company=company)
        form_data, errors = _apply_customer_payload(request, customer, is_edit=False)

        if errors:
            return render(
                request,
                self.template_name,
                _customer_form_context(company, is_edit=False, customer=customer, form_data=form_data, form_errors=errors),
                status=400,
            )

        messages.success(request, f"Party '{customer.name}' created successfully")
        return redirect("customers_ui:customer-detail", pk=customer.pk)


@method_decorator(login_required, name="dispatch")
class CustomerUpdateView(OnboardingCheckMixin, View):
    template_name = "customers/customer_form.html"

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=pk)
        return render(request, self.template_name, _customer_form_context(company, is_edit=True, customer=customer))

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=pk)

        # Never update opening/current balance from edit form.
        original_opening = customer.opening_balance
        original_current = customer.current_balance

        form_data, errors = _apply_customer_payload(request, customer, is_edit=True)

        if errors:
            customer.opening_balance = original_opening
            customer.current_balance = original_current
            return render(
                request,
                self.template_name,
                _customer_form_context(company, is_edit=True, customer=customer, form_data=form_data, form_errors=errors),
                status=400,
            )

        customer.opening_balance = original_opening
        customer.current_balance = original_current
        customer.save(update_fields=["opening_balance", "current_balance", "updated_at"])

        messages.success(request, "Party updated successfully")
        return redirect("customers_ui:customer-detail", pk=customer.pk)


@method_decorator(login_required, name="dispatch")
class CustomerDetailView(OnboardingCheckMixin, View):
    template_name = "customers/customer_detail.html"

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(
            Customer.objects.prefetch_related("contacts", "customer_notes"),
            company=company,
            pk=pk,
        )

        from invoices.models import Invoice

        recent_invoices = (
            Invoice.objects.filter(company=company, customer=customer)
            .order_by("-invoice_date", "-created_at")[:5]
        )
        invoice_count = Invoice.objects.filter(company=company, customer=customer).count()
        invoice_total = (
            Invoice.objects.filter(company=company, customer=customer, status=Invoice.StatusChoices.ISSUED)
            .aggregate(total=Sum("grand_total"))
            .get("total")
            or Decimal("0")
        )

        context = {
            "customer": customer,
            "contacts": customer.contacts.all(),
            "notes": customer.customer_notes.all(),
            "recent_invoices": recent_invoices,
            "invoice_count": invoice_count,
            "invoice_total": invoice_total,
            "page_title": customer.display_name or customer.name,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class CustomerDeleteView(View):
    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=pk)

        from invoices.models import Invoice

        if Invoice.objects.filter(company=company, customer=customer).exists():
            messages.error(request, "Cannot delete party with existing invoices. Deactivate instead.")
            return redirect("customers_ui:customer-detail", pk=customer.pk)

        customer.is_active = False
        customer.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Party deactivated successfully")
        return redirect("customers_ui:customer-list")


@method_decorator(login_required, name="dispatch")
class CustomerStatementView(View):
    template_name = "customers/customer_statement.html"

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=pk)
        date_from, date_to = _default_statement_dates(request)

        statement = CustomerService.get_customer_statement(customer, date_from=date_from, date_to=date_to)

        context = {
            "customer": customer,
            "statement": statement,
            "date_from": date_from,
            "date_to": date_to,
            "page_title": f"Statement - {customer.display_name or customer.name}",
            "export_mode": (request.GET.get("export") or "").lower() == "pdf",
        }

        response = render(request, self.template_name, context)
        if context["export_mode"]:
            response["Content-Disposition"] = f'inline; filename="statement-{customer.pk}.html"'
        return response


@method_decorator(login_required, name="dispatch")
class ContactCreateView(View):
    def get(self, request: HttpRequest, customer_pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=customer_pk)
        return render(
            request,
            "customers/_contact_list.html",
            {"customer": customer, "contacts": customer.contacts.all()},
        )

    def post(self, request: HttpRequest, customer_pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=customer_pk)

        name = (request.POST.get("name") or "").strip()
        if not name:
            return render(
                request,
                "customers/_contact_list.html",
                {"customer": customer, "contacts": customer.contacts.all(), "contact_error": "Name is required"},
                status=400,
            )

        is_primary = _to_bool(request.POST.get("is_primary"))
        if is_primary:
            customer.contacts.update(is_primary=False)

        CustomerContact.objects.create(
            customer=customer,
            name=name,
            designation=(request.POST.get("designation") or "").strip(),
            mobile=(request.POST.get("mobile") or "").strip(),
            email=(request.POST.get("email") or "").strip().lower(),
            is_primary=is_primary,
        )

        response = render(
            request,
            "customers/_contact_list.html",
            {"customer": customer, "contacts": customer.contacts.all()},
        )
        response["HX-Trigger"] = "contactsChanged"
        return response


@method_decorator(login_required, name="dispatch")
class ContactDeleteView(View):
    def post(self, request: HttpRequest, customer_pk, pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=customer_pk)
        contact = get_object_or_404(CustomerContact, customer=customer, pk=pk)
        contact.delete()

        response = render(
            request,
            "customers/_contact_list.html",
            {"customer": customer, "contacts": customer.contacts.all()},
        )
        response["HX-Trigger"] = "contactsChanged"
        return response


@method_decorator(login_required, name="dispatch")
class NoteCreateView(View):
    def get(self, request: HttpRequest, customer_pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=customer_pk)
        return render(
            request,
            "customers/_note_list.html",
            {"customer": customer, "notes": customer.customer_notes.all()},
        )

    def post(self, request: HttpRequest, customer_pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=customer_pk)

        note_text = (request.POST.get("note") or "").strip()
        if len(note_text) < 3:
            return render(
                request,
                "customers/_note_list.html",
                {"customer": customer, "notes": customer.customer_notes.all(), "note_error": "Note must be at least 3 characters"},
                status=400,
            )

        CustomerNote.objects.create(customer=customer, note=note_text, created_by=request.user)

        response = render(
            request,
            "customers/_note_list.html",
            {"customer": customer, "notes": customer.customer_notes.all()},
        )
        response["HX-Trigger"] = "notesChanged"
        return response


@method_decorator(login_required, name="dispatch")
class NoteDeleteView(View):
    def post(self, request: HttpRequest, customer_pk, pk) -> HttpResponse:
        company = request.user.company_profile
        customer = get_object_or_404(Customer, company=company, pk=customer_pk)
        note = get_object_or_404(CustomerNote, customer=customer, pk=pk)

        if note.created_by_id != request.user.id:
            return HttpResponseForbidden("You can only delete your own note")

        note.delete()

        response = render(
            request,
            "customers/_note_list.html",
            {"customer": customer, "notes": customer.customer_notes.all()},
        )
        response["HX-Trigger"] = "notesChanged"
        return response
