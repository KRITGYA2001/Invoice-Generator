from __future__ import annotations

import re
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from company.models import BankDetail, CompanyProfile, InvoiceSettings

GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}


def _step_value(request: HttpRequest) -> int:
    raw = request.GET.get("step") or request.POST.get("step") or "1"
    try:
        step = int(raw)
    except ValueError:
        step = 1
    return min(max(step, 1), 3)


def _onboarding_steps(current_step: int) -> list[dict]:
    labels = [
        (1, "Company Details", "Business identity and contact"),
        (2, "Bank Details", "Where customers should pay"),
        (3, "Invoice Settings", "Numbering and terms"),
    ]
    return [
        {
            "number": number,
            "title": title,
            "description": description,
            "completed": number < current_step,
        }
        for number, title, description in labels
    ]


def _validate_logo_file(file_obj) -> str | None:
    if not file_obj:
        return None
    if file_obj.size > 2 * 1024 * 1024:
        return "Image must be under 2MB"
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    extension = Path(getattr(file_obj, "name", "") or "").suffix.lower()
    if not content_type.startswith("image/") and extension not in IMAGE_EXTENSIONS:
        return "Uploaded file must be an image"
    return None


def _validate_qr_file(file_obj) -> str | None:
    if not file_obj:
        return None
    if file_obj.size > 5 * 1024 * 1024:
        return "QR image must be under 5MB"
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    extension = Path(getattr(file_obj, "name", "") or "").suffix.lower()
    if not content_type.startswith("image/") and extension not in IMAGE_EXTENSIONS:
        return "Uploaded QR must be an image"
    return None


def _onboarding_complete(company: CompanyProfile | None) -> bool:
    if not company:
        return False
    has_profile_data = bool(company.company_name and company.address_line1 and company.mobile_primary)
    return has_profile_data and hasattr(company, "invoice_settings")


@method_decorator(login_required, name="dispatch")
class OnboardingView(View):
    """3-step onboarding wizard for first-time company setup."""

    template_name = "company/onboarding.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)

        # Only redirect to dashboard when arriving fresh (no explicit step in URL).
        # When redirected here with ?step=2 or ?step=3 after saving a previous step,
        # skip the completion check so the next step is shown instead of the dashboard.
        if "step" not in request.GET and _onboarding_complete(company):
            return redirect("core:dashboard")

        current_step = _step_value(request)
        settings_obj = InvoiceSettings.objects.filter(company=company).first() if company else None
        context = {
            "current_step": current_step,
            "steps": _onboarding_steps(current_step),
            "company": company,
            "inv_settings": settings_obj,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        step = _step_value(request)
        if step == 1:
            return self._save_step_one(request)
        if step == 2:
            return self._save_step_two(request)
        return self._save_step_three(request)

    def _save_step_one(self, request: HttpRequest) -> HttpResponse:
        company_name = (request.POST.get("company_name") or "").strip()
        gstin = (request.POST.get("gstin") or "").strip().upper()

        if not company_name:
            messages.error(request, "Company name is required")
            return redirect("/company/onboarding/?step=1")
        if gstin and not GSTIN_REGEX.match(gstin):
            messages.error(request, "GSTIN format is invalid")
            return redirect("/company/onboarding/?step=1")

        defaults = {
            "company_name": company_name,
            "trade_name": (request.POST.get("trade_name") or "").strip(),
            "unit_division": (request.POST.get("unit_division") or "").strip(),
            "address_line1": (request.POST.get("address_line1") or "").strip() or "-",
            "address_line2": (request.POST.get("address_line2") or "").strip(),
            "city": (request.POST.get("city") or "").strip() or "-",
            "state": (request.POST.get("state") or "").strip() or "-",
            "state_code": (request.POST.get("state_code") or "").strip() or "00",
            "pincode": (request.POST.get("pincode") or "").strip() or "000000",
            "pan": (request.POST.get("pan") or "").strip().upper(),
            "gstin": gstin,
            "mobile_primary": (request.POST.get("mobile_primary") or "").strip() or "0000000000",
            "mobile_secondary": (request.POST.get("mobile_secondary") or "").strip(),
            "email": (request.POST.get("email") or "").strip().lower(),
            "logo_text": (request.POST.get("logo_text") or "").strip()[:6],
        }

        company, created = CompanyProfile.objects.get_or_create(user=request.user, defaults=defaults)
        if not created:
            for key, value in defaults.items():
                setattr(company, key, value)
            company.save()

        InvoiceSettings.objects.get_or_create(company=company)
        return redirect("/company/onboarding/?step=2")

    def _save_step_two(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            messages.error(request, "Please complete company details first")
            return redirect("/company/onboarding/?step=1")

        bank_name = (request.POST.get("bank_name") or "").strip()
        branch_name = (request.POST.get("branch_name") or "").strip()
        account_number = (request.POST.get("account_number") or "").strip()
        ifsc_code = (request.POST.get("ifsc_code") or "").strip().upper()
        account_type = (request.POST.get("account_type") or "current").strip().lower()
        upi_id = (request.POST.get("upi_id") or "").strip()

        any_field = any([bank_name, branch_name, account_number, ifsc_code, upi_id])
        if any_field:
            if not bank_name or not account_number or not ifsc_code:
                messages.error(request, "Bank name, account number and IFSC code are required")
                return redirect("/company/onboarding/?step=2")
            if len(account_number) < 9 or len(account_number) > 18 or not account_number.isdigit():
                messages.error(request, "Account number must be 9 to 18 digits")
                return redirect("/company/onboarding/?step=2")
            if not IFSC_REGEX.match(ifsc_code):
                messages.error(request, "Enter a valid IFSC code")
                return redirect("/company/onboarding/?step=2")

            BankDetail.objects.filter(company=company).update(is_primary=False)
            BankDetail.objects.create(
                company=company,
                bank_name=bank_name,
                branch_name=branch_name or "-",
                account_number=account_number,
                ifsc_code=ifsc_code,
                account_type=account_type if account_type in {"current", "savings"} else "current",
                upi_id=upi_id,
                is_primary=True,
                is_active=True,
            )

        return redirect("/company/onboarding/?step=3")

    def _save_step_three(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            messages.error(request, "Please complete company details first")
            return redirect("/company/onboarding/?step=1")

        settings_obj, _ = InvoiceSettings.objects.get_or_create(company=company)
        settings_obj.invoice_prefix = (request.POST.get("invoice_prefix") or settings_obj.invoice_prefix or "INV").strip()
        settings_obj.financial_year = (request.POST.get("financial_year") or settings_obj.financial_year or "25-26").strip()

        counter_raw = (request.POST.get("invoice_counter") or "").strip()
        due_days_raw = (request.POST.get("default_due_days") or "").strip()
        settings_obj.invoice_counter = int(counter_raw) if counter_raw.isdigit() else settings_obj.invoice_counter
        settings_obj.default_due_days = int(due_days_raw) if due_days_raw.isdigit() else settings_obj.default_due_days
        settings_obj.default_transport = (request.POST.get("default_transport") or settings_obj.default_transport or "").strip()
        settings_obj.invoice_terms = (request.POST.get("invoice_terms") or "").strip()
        settings_obj.save()

        messages.success(request, "Setup complete! Welcome to BillMint.")
        return redirect("core:dashboard")


@method_decorator(login_required, name="dispatch")
class CompanyProfileView(View):
    """Company settings page with profile/bank/invoice tabs."""

    template_name = "company/settings.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            return redirect("company_ui:onboarding")

        active_tab = (request.GET.get("tab") or "profile").strip().lower()
        if active_tab not in {"profile", "bank", "invoice"}:
            active_tab = "profile"

        context = {
            "active_tab": active_tab,
            "company": company,
            "bank_details": company.bank_details.all(),
            "inv_settings": InvoiceSettings.objects.get_or_create(company=company)[0],
            "page_title": "Company Settings",
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            return redirect("company_ui:onboarding")

        tab = (request.GET.get("tab") or "profile").strip().lower()
        if tab != "profile":
            return redirect(f"/company/profile/?tab={tab}")

        company.company_name = (request.POST.get("company_name") or company.company_name).strip()
        company.trade_name = (request.POST.get("trade_name") or "").strip()
        company.unit_division = (request.POST.get("unit_division") or "").strip()
        company.address_line1 = (request.POST.get("address_line1") or company.address_line1).strip()
        company.address_line2 = (request.POST.get("address_line2") or "").strip()
        company.city = (request.POST.get("city") or company.city).strip()
        company.state = (request.POST.get("state") or company.state).strip()
        company.state_code = (request.POST.get("state_code") or company.state_code).strip()
        company.pincode = (request.POST.get("pincode") or company.pincode).strip()
        company.country = (request.POST.get("country") or company.country).strip()
        company.pan = (request.POST.get("pan") or "").strip().upper()
        gstin = (request.POST.get("gstin") or "").strip().upper()
        if gstin and not GSTIN_REGEX.match(gstin):
            messages.error(request, "Invalid GSTIN format")
            return redirect("/company/profile/?tab=profile")
        company.gstin = gstin
        company.udyam_number = (request.POST.get("udyam_number") or "").strip()
        company.mobile_primary = (request.POST.get("mobile_primary") or company.mobile_primary).strip()
        company.mobile_secondary = (request.POST.get("mobile_secondary") or "").strip()
        company.email = (request.POST.get("email") or "").strip().lower()
        company.website = (request.POST.get("website") or "").strip()
        company.logo_text = (request.POST.get("logo_text") or "").strip()[:6]
        company.authorised_signatory = (request.POST.get("authorised_signatory") or "").strip()
        company.is_msme = request.POST.get("is_msme") == "on"

        logo_file = request.FILES.get("logo")
        signature_file = request.FILES.get("signature_image")
        logo_error = _validate_logo_file(logo_file)
        signature_error = _validate_logo_file(signature_file)
        if logo_error:
            messages.error(request, f"Logo: {logo_error}")
            return redirect("/company/profile/?tab=profile")
        if signature_error:
            messages.error(request, f"Signature: {signature_error}")
            return redirect("/company/profile/?tab=profile")

        if logo_file:
            company.logo = logo_file
        if signature_file:
            company.signature_image = signature_file

        company.save()
        messages.success(request, "Company profile updated successfully")
        return redirect("/company/profile/?tab=profile")


@method_decorator(login_required, name="dispatch")
class BankDetailListView(View):
    """Render bank accounts list as HTMX partial."""

    def get(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            return HttpResponse("")
        bank_details = company.bank_details.all()
        return render(request, "company/_bank_list.html", {"bank_details": bank_details})


@method_decorator(login_required, name="dispatch")
class BankDetailCreateView(View):
    """Create bank accounts via HTMX modal form."""

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, "company/_bank_form.html", {"bank": None})

    def post(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            response = HttpResponse("")
            response["HX-Trigger"] = "bankListChanged"
            return response

        data, errors = self._validated_data(request)
        qr_code_image = request.FILES.get("qr_code_image")
        qr_error = _validate_qr_file(qr_code_image)
        if qr_error:
            errors["qr_code_image"] = qr_error
        if errors:
            return render(request, "company/_bank_form.html", {"bank": None, "errors": errors, "form_data": request.POST})

        is_first = not company.bank_details.exists()
        if is_first:
            company.bank_details.update(is_primary=False)

        BankDetail.objects.create(
            company=company,
            bank_name=data["bank_name"],
            branch_name=data["branch_name"],
            account_number=data["account_number"],
            ifsc_code=data["ifsc_code"],
            account_type=data["account_type"],
            upi_id=data["upi_id"],
            swift_code=data["swift_code"],
            qr_code_image=qr_code_image,
            is_primary=is_first,
            is_active=True,
        )

        response = HttpResponse("")
        response["HX-Trigger"] = "bankListChanged"
        return response

    @staticmethod
    def _validated_data(request: HttpRequest) -> tuple[dict, dict]:
        account_number_raw = (request.POST.get("account_number") or "").strip()
        account_number = "".join(ch for ch in account_number_raw if ch.isdigit())
        ifsc_code = (request.POST.get("ifsc_code") or "").strip().upper().replace(" ", "")
        data = {
            "bank_name": (request.POST.get("bank_name") or "").strip(),
            "branch_name": (request.POST.get("branch_name") or "").strip() or "-",
            "account_number": account_number,
            "ifsc_code": ifsc_code,
            "account_type": (request.POST.get("account_type") or "current").strip().lower(),
            "upi_id": (request.POST.get("upi_id") or "").strip(),
            "swift_code": (request.POST.get("swift_code") or "").strip(),
        }
        errors: dict[str, str] = {}
        if not data["bank_name"]:
            errors["bank_name"] = "Bank name is required"
        if len(data["account_number"]) < 9 or len(data["account_number"]) > 18 or not data["account_number"].isdigit():
            errors["account_number"] = "Account number must be 9 to 18 digits"
        if not IFSC_REGEX.match(data["ifsc_code"]):
            errors["ifsc_code"] = "Enter valid IFSC code"
        if data["account_type"] not in {"current", "savings"}:
            data["account_type"] = "current"
        return data, errors


@method_decorator(login_required, name="dispatch")
class BankDetailUpdateView(View):
    """Update bank details through modal form."""

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        bank = get_object_or_404(BankDetail, pk=pk, company=company)
        return render(request, "company/_bank_form.html", {"bank": bank})

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        bank = get_object_or_404(BankDetail, pk=pk, company=company)

        data, errors = BankDetailCreateView._validated_data(request)
        qr_code_image = request.FILES.get("qr_code_image")
        qr_error = _validate_qr_file(qr_code_image)
        if qr_error:
            errors["qr_code_image"] = qr_error
        if errors:
            return render(request, "company/_bank_form.html", {"bank": bank, "errors": errors, "form_data": request.POST})

        for field, value in data.items():
            setattr(bank, field, value)
        if qr_code_image:
            bank.qr_code_image = qr_code_image
        bank.save()

        response = HttpResponse("")
        response["HX-Trigger"] = "bankListChanged"
        return response


@method_decorator(login_required, name="dispatch")
class BankDetailDeleteView(View):
    """Delete bank detail via HTMX with safeguards."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        bank = get_object_or_404(BankDetail, pk=pk, company=company)

        if company.bank_details.count() == 1:
            messages.error(request, "Cannot delete the only bank account")
            response = HttpResponse("")
            response["HX-Trigger"] = "bankListChanged"
            return response

        was_primary = bank.is_primary
        bank.delete()

        if was_primary:
            replacement = company.bank_details.order_by("-is_primary", "bank_name").first()
            if replacement:
                company.bank_details.exclude(pk=replacement.pk).update(is_primary=False)
                replacement.is_primary = True
                replacement.save(update_fields=["is_primary", "updated_at"])

        response = HttpResponse("")
        response["HX-Trigger"] = "bankListChanged"
        return response


@method_decorator(login_required, name="dispatch")
class SetPrimaryBankView(View):
    """Set selected bank account as primary."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        bank = get_object_or_404(BankDetail, pk=pk, company=company)
        company.bank_details.exclude(pk=bank.pk).update(is_primary=False)
        bank.is_primary = True
        bank.save(update_fields=["is_primary", "updated_at"])

        response = HttpResponse("")
        response["HX-Trigger"] = "bankListChanged"
        return response


@method_decorator(login_required, name="dispatch")
class InvoiceSettingsView(View):
    """Render and update invoice settings tab/partial."""

    def get(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            return HttpResponse("")
        settings_obj, _ = InvoiceSettings.objects.get_or_create(company=company)
        return render(request, "company/_invoice_settings_form.html", {"inv_settings": settings_obj})

    def post(self, request: HttpRequest) -> HttpResponse:
        company = getattr(request.user, "company_profile", None)
        if not company:
            return HttpResponse("")

        settings_obj, _ = InvoiceSettings.objects.get_or_create(company=company)
        settings_obj.invoice_prefix = (request.POST.get("invoice_prefix") or settings_obj.invoice_prefix).strip()
        settings_obj.financial_year = (request.POST.get("financial_year") or settings_obj.financial_year).strip()
        counter_raw = (request.POST.get("invoice_counter") or "").strip()
        if counter_raw.isdigit() and int(counter_raw) >= 1:
            settings_obj.invoice_counter = int(counter_raw)
        due_days_raw = (request.POST.get("default_due_days") or "").strip()
        settings_obj.default_due_days = int(due_days_raw) if due_days_raw.isdigit() else settings_obj.default_due_days
        settings_obj.default_transport = (request.POST.get("default_transport") or "").strip()
        settings_obj.default_place_of_supply = (request.POST.get("default_place_of_supply") or "").strip()
        settings_obj.reverse_charge_applicable = request.POST.get("reverse_charge_applicable") == "on"
        settings_obj.einvoicing_enabled = request.POST.get("einvoicing_enabled") == "on"
        settings_obj.ewaybill_enabled = request.POST.get("ewaybill_enabled") == "on"
        settings_obj.invoice_terms = (request.POST.get("invoice_terms") or "").strip()
        settings_obj.invoice_notes = (request.POST.get("invoice_notes") or "").strip()
        settings_obj.show_bank_details = request.POST.get("show_bank_details") == "on"
        settings_obj.show_signature = request.POST.get("show_signature") == "on"

        copies_raw = (request.POST.get("number_of_copies") or "").strip()
        if copies_raw in {"1", "2", "3"}:
            settings_obj.number_of_copies = int(copies_raw)

        settings_obj.save()
        messages.success(request, "Invoice settings updated successfully")

        response = render(request, "company/_invoice_settings_form.html", {"inv_settings": settings_obj})
        response["HX-Trigger"] = "invoiceSettingsSaved"
        return response
