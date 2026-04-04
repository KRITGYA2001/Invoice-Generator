from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from core.views import OnboardingCheckMixin
from products.models import Product, ProductCategory, StockMovement, UnitOfMeasurement
from products.services import StockService

HSN_REGEX = re.compile(r"^[0-9]{4,8}$")
ALLOWED_GST = {Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")}


def _to_bool(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def _validate_image(file_obj) -> str | None:
    if not file_obj:
        return None
    if file_obj.size > 2 * 1024 * 1024:
        return "Image must be under 2MB"
    if not (getattr(file_obj, "content_type", "") or "").startswith("image/"):
        return "Uploaded file must be an image"
    return None


def _product_base_context(company) -> dict:
    return {
        "categories": ProductCategory.objects.filter(company=company, is_active=True).order_by("name"),
        "units": UnitOfMeasurement.objects.filter(company=company, is_active=True).order_by("name"),
        "gst_rates": [0, 5, 12, 18, 28],
    }


@method_decorator(login_required, name="dispatch")
class ProductListView(OnboardingCheckMixin, View):
    """List products with filtering, sorting, and pagination."""

    template_name = "products/product_list.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        queryset = Product.objects.filter(company=company).select_related("category", "unit")

        search = (request.GET.get("search") or "").strip()
        category = (request.GET.get("category") or "").strip()
        gst_rate = (request.GET.get("gst_rate") or "").strip()
        is_active = (request.GET.get("is_active") or "").strip()
        low_stock = _to_bool(request.GET.get("low_stock"))
        ordering = (request.GET.get("ordering") or "name").strip()

        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(hsn_code__icontains=search))
        if category:
            queryset = queryset.filter(category_id=category)
        if gst_rate:
            queryset = queryset.filter(gst_rate=gst_rate)
        if is_active != "false":
            queryset = queryset.filter(is_active=True)
        if low_stock:
            queryset = queryset.filter(track_inventory=True, current_stock__lte=F("minimum_stock"))

        allowed_ordering = {"name", "-name", "selling_price", "-selling_price", "current_stock", "-current_stock"}
        if ordering not in allowed_ordering:
            ordering = "name"
        queryset = queryset.order_by(ordering)

        page_number = int(request.GET.get("page", 1) or 1)
        paginator = Paginator(queryset, 20)
        page_obj = paginator.get_page(page_number)

        query_without_sort = request.GET.copy()
        query_without_sort.pop("ordering", None)
        query_without_sort.pop("page", None)

        stock_summary = StockService.get_stock_summary(company)
        current_filters = {
            "search": search,
            "category": category,
            "gst_rate": gst_rate,
            "is_active": is_active,
            "low_stock": low_stock,
        }

        pagination = {
            "page": page_obj.number,
            "page_size": 20,
            "total": paginator.count,
            "total_pages": paginator.num_pages,
        }

        context = {
            "products": page_obj.object_list,
            "page_obj": page_obj,
            "categories": ProductCategory.objects.filter(company=company, is_active=True).order_by("name"),
            "gst_rates": [0, 5, 12, 18, 28],
            "stock_summary": stock_summary,
            "current_filters": current_filters,
            "ordering": ordering,
            "query_string": urlencode(query_without_sort, doseq=True),
            "pagination": pagination,
            "page_title": "Products",
        }

        if request.headers.get("HX-Request"):
            return render(request, "products/_product_table.html", context)
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class ProductCreateView(OnboardingCheckMixin, View):
    """Create products with optional opening stock setup."""

    template_name = "products/product_form.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        context = {
            **_product_base_context(request.user.company_profile),
            "is_edit": False,
            "form_data": {},
            "form_errors": {},
            "page_title": "New Product",
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        form_data = request.POST.copy()
        errors: dict[str, str] = {}

        name = (request.POST.get("name") or "").strip()
        hsn_code = (request.POST.get("hsn_code") or "").strip()
        sku = (request.POST.get("sku") or "").strip()
        description = (request.POST.get("description") or "").strip()
        category_id = (request.POST.get("category") or "").strip()
        unit_id = (request.POST.get("unit") or "").strip()
        gst_raw = (request.POST.get("gst_rate") or "").strip()
        selling_raw = (request.POST.get("selling_price") or "").strip()
        purchase_raw = (request.POST.get("purchase_price") or "").strip()
        cess_raw = (request.POST.get("cess_rate") or "0").strip()
        minimum_raw = (request.POST.get("minimum_stock") or "0").strip()
        maximum_raw = (request.POST.get("maximum_stock") or "").strip()
        opening_raw = (request.POST.get("opening_stock") or "0").strip()

        is_service = _to_bool(request.POST.get("is_service"))
        track_inventory = _to_bool(request.POST.get("track_inventory"))

        if not name:
            errors["name"] = "Name is required"
        elif Product.objects.filter(company=company, name__iexact=name).exists():
            errors["name"] = "Product name must be unique"

        if not hsn_code or not HSN_REGEX.match(hsn_code):
            errors["hsn_code"] = "HSN/SAC code must be 4-8 digits"

        try:
            selling_price = Decimal(selling_raw)
            if selling_price < 0:
                raise InvalidOperation
        except Exception:
            errors["selling_price"] = "Selling price must be a valid non-negative number"
            selling_price = Decimal("0")

        try:
            gst_rate = Decimal(gst_raw)
            if gst_rate not in ALLOWED_GST:
                raise InvalidOperation
        except Exception:
            errors["gst_rate"] = "GST rate must be one of 0, 5, 12, 18, 28"
            gst_rate = Decimal("0")

        try:
            purchase_price = Decimal(purchase_raw) if purchase_raw else None
            if purchase_price is not None and purchase_price < 0:
                raise InvalidOperation
        except Exception:
            errors["purchase_price"] = "Purchase price must be a valid non-negative number"
            purchase_price = None

        try:
            cess_rate = Decimal(cess_raw or "0")
            if cess_rate < 0:
                raise InvalidOperation
        except Exception:
            errors["cess_rate"] = "Cess rate must be non-negative"
            cess_rate = Decimal("0")

        try:
            minimum_stock = Decimal(minimum_raw or "0")
            if minimum_stock < 0:
                raise InvalidOperation
        except Exception:
            errors["minimum_stock"] = "Minimum stock must be non-negative"
            minimum_stock = Decimal("0")

        try:
            maximum_stock = Decimal(maximum_raw) if maximum_raw else None
            if maximum_stock is not None and maximum_stock < 0:
                raise InvalidOperation
        except Exception:
            errors["maximum_stock"] = "Maximum stock must be non-negative"
            maximum_stock = None

        try:
            opening_stock = Decimal(opening_raw or "0")
            if opening_stock < 0:
                raise InvalidOperation
        except Exception:
            errors["opening_stock"] = "Opening stock must be non-negative"
            opening_stock = Decimal("0")

        category = None
        if category_id:
            category = ProductCategory.objects.filter(company=company, id=category_id, is_active=True).first()

        unit = UnitOfMeasurement.objects.filter(company=company, id=unit_id, is_active=True).first()
        if not unit:
            errors["unit"] = "Unit is required"

        image_file = request.FILES.get("image")
        image_error = _validate_image(image_file)
        if image_error:
            errors["image"] = image_error

        if errors:
            context = {
                **_product_base_context(company),
                "is_edit": False,
                "form_data": form_data,
                "form_errors": errors,
                "page_title": "New Product",
            }
            for message_text in errors.values():
                messages.error(request, message_text)
            return render(request, self.template_name, context, status=400)

        with transaction.atomic():
            product = Product.objects.create(
                company=company,
                category=category,
                unit=unit,
                name=name,
                description=description,
                sku=sku,
                hsn_code=hsn_code,
                selling_price=selling_price,
                purchase_price=purchase_price,
                gst_rate=gst_rate,
                cess_rate=cess_rate,
                is_service=is_service,
                track_inventory=track_inventory,
                minimum_stock=minimum_stock,
                maximum_stock=maximum_stock,
            )
            if image_file:
                product.image = image_file
                product.save(update_fields=["image", "updated_at"])

            if track_inventory and opening_stock > 0:
                StockService.set_opening_stock(product, opening_stock, request.user)

        messages.success(request, f"Product '{name}' created successfully")
        return redirect("products_ui:product-list")


@method_decorator(login_required, name="dispatch")
class ProductUpdateView(OnboardingCheckMixin, View):
    """Update editable product fields except current stock."""

    template_name = "products/product_form.html"

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        product = get_object_or_404(Product.objects.select_related("category", "unit"), company=company, pk=pk)
        context = {
            **_product_base_context(company),
            "is_edit": True,
            "product": product,
            "form_data": {
                "category": str(product.category_id) if product.category_id else "",
                "unit": str(product.unit_id) if product.unit_id else "",
                "gst_rate": str(int(product.gst_rate)),
            },
            "form_errors": {},
            "page_title": f"Edit {product.name}",
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        product = get_object_or_404(Product, company=company, pk=pk)
        form_data = request.POST.copy()
        errors: dict[str, str] = {}

        name = (request.POST.get("name") or "").strip()
        hsn_code = (request.POST.get("hsn_code") or "").strip()
        unit_id = (request.POST.get("unit") or "").strip()
        category_id = (request.POST.get("category") or "").strip()
        gst_raw = (request.POST.get("gst_rate") or "").strip()
        selling_raw = (request.POST.get("selling_price") or "").strip()
        purchase_raw = (request.POST.get("purchase_price") or "").strip()
        cess_raw = (request.POST.get("cess_rate") or "0").strip()
        minimum_raw = (request.POST.get("minimum_stock") or "0").strip()
        maximum_raw = (request.POST.get("maximum_stock") or "").strip()

        if not name:
            errors["name"] = "Name is required"
        elif Product.objects.filter(company=company, name__iexact=name).exclude(pk=product.pk).exists():
            errors["name"] = "Product name must be unique"

        if not hsn_code or not HSN_REGEX.match(hsn_code):
            errors["hsn_code"] = "HSN/SAC code must be 4-8 digits"

        try:
            selling_price = Decimal(selling_raw)
            if selling_price < 0:
                raise InvalidOperation
        except Exception:
            errors["selling_price"] = "Selling price must be a valid non-negative number"
            selling_price = product.selling_price

        try:
            purchase_price = Decimal(purchase_raw) if purchase_raw else None
            if purchase_price is not None and purchase_price < 0:
                raise InvalidOperation
        except Exception:
            errors["purchase_price"] = "Purchase price must be a valid non-negative number"
            purchase_price = product.purchase_price

        try:
            gst_rate = Decimal(gst_raw)
            if gst_rate not in ALLOWED_GST:
                raise InvalidOperation
        except Exception:
            errors["gst_rate"] = "GST rate must be one of 0, 5, 12, 18, 28"
            gst_rate = product.gst_rate

        try:
            cess_rate = Decimal(cess_raw or "0")
            if cess_rate < 0:
                raise InvalidOperation
        except Exception:
            errors["cess_rate"] = "Cess rate must be non-negative"
            cess_rate = product.cess_rate

        try:
            minimum_stock = Decimal(minimum_raw or "0")
            if minimum_stock < 0:
                raise InvalidOperation
        except Exception:
            errors["minimum_stock"] = "Minimum stock must be non-negative"
            minimum_stock = product.minimum_stock

        try:
            maximum_stock = Decimal(maximum_raw) if maximum_raw else None
            if maximum_stock is not None and maximum_stock < 0:
                raise InvalidOperation
        except Exception:
            errors["maximum_stock"] = "Maximum stock must be non-negative"
            maximum_stock = product.maximum_stock

        unit = UnitOfMeasurement.objects.filter(company=company, id=unit_id, is_active=True).first()
        if not unit:
            errors["unit"] = "Unit is required"

        category = None
        if category_id:
            category = ProductCategory.objects.filter(company=company, id=category_id, is_active=True).first()

        image_file = request.FILES.get("image")
        image_error = _validate_image(image_file)
        if image_error:
            errors["image"] = image_error

        if errors:
            context = {
                **_product_base_context(company),
                "is_edit": True,
                "product": product,
                "form_data": form_data,
                "form_errors": errors,
                "page_title": f"Edit {product.name}",
            }
            for message_text in errors.values():
                messages.error(request, message_text)
            return render(request, self.template_name, context, status=400)

        product.name = name
        product.description = (request.POST.get("description") or "").strip()
        product.sku = (request.POST.get("sku") or "").strip()
        product.hsn_code = hsn_code
        product.category = category
        product.unit = unit
        product.selling_price = selling_price
        product.purchase_price = purchase_price
        product.gst_rate = gst_rate
        product.cess_rate = cess_rate
        product.is_service = _to_bool(request.POST.get("is_service"))
        product.track_inventory = _to_bool(request.POST.get("track_inventory"))
        product.minimum_stock = minimum_stock
        product.maximum_stock = maximum_stock
        if image_file:
            product.image = image_file
        product.save()

        messages.success(request, "Product updated successfully")
        return redirect("products_ui:product-detail", pk=product.pk)


@method_decorator(login_required, name="dispatch")
class ProductDetailView(OnboardingCheckMixin, View):
    """Detailed product view with stock history and invoice references."""

    template_name = "products/product_detail.html"

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        product = get_object_or_404(Product.objects.select_related("category", "unit"), company=company, pk=pk)

        movements = product.stock_movements.select_related("created_by").order_by("-created_at")[:10]
        movement_summary = product.stock_movements.aggregate(
            total_in=Sum("quantity", filter=Q(movement_type__in=["IN", "RETURN", "OPENING"])),
            total_out=Sum("quantity", filter=Q(movement_type="OUT")),
        )
        total_in = movement_summary.get("total_in") or Decimal("0")
        total_out = movement_summary.get("total_out") or Decimal("0")

        from invoices.models import InvoiceLineItem

        recent_invoices = (
            InvoiceLineItem.objects.filter(product=product)
            .select_related("invoice")
            .order_by("-invoice__invoice_date", "-invoice__created_at")[:5]
        )
        invoice_usage_count = InvoiceLineItem.objects.filter(product=product).count()

        context = {
            "product": product,
            "movements": movements,
            "stock_movements": movements,
            "stock_summary": {
                "total_in": total_in,
                "total_out": total_out,
                "net_movement": total_in - total_out,
            },
            "recent_invoices": recent_invoices,
            "invoice_usage_count": invoice_usage_count,
            "page_title": product.name,
            "pagination": None,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class ProductDeleteView(View):
    """Soft-delete product by marking it inactive."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        product = get_object_or_404(Product, company=company, pk=pk)

        from invoices.models import InvoiceLineItem

        has_invoice_lines = InvoiceLineItem.objects.filter(product=product).exists()
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])

        if has_invoice_lines:
            messages.warning(request, "Product deactivated. It is referenced in existing invoices.")
        else:
            messages.success(request, "Product deleted successfully")

        if request.headers.get("HX-Request"):
            return HttpResponse("")
        return redirect("products_ui:product-list")


@method_decorator(login_required, name="dispatch")
class StockAdjustView(View):
    """Adjust stock via HTMX modal and StockService."""

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        product = get_object_or_404(Product.objects.select_related("unit"), company=company, pk=pk)
        return render(
            request,
            "products/_stock_modal.html",
            {"product": product, "movement_types": ["IN", "ADJUST", "RETURN"]},
        )

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        product = get_object_or_404(Product, company=company, pk=pk)

        movement_type = (request.POST.get("movement_type") or "").strip().upper()
        action = (request.POST.get("action") or "").strip().lower()
        reason = (request.POST.get("reason") or "").strip()
        notes = (request.POST.get("notes") or "").strip()
        quantity_raw = (request.POST.get("quantity") or "").strip()

        if not movement_type:
            movement_type = {
                "add": "IN",
                "subtract": "OUT",
                "set": "ADJUST",
            }.get(action, "IN")

        try:
            quantity = Decimal(quantity_raw)
            if quantity <= 0:
                raise InvalidOperation
        except Exception:
            messages.error(request, "Quantity must be greater than zero")
            response = render(request, "products/_stock_modal.html", {"product": product}, status=400)
            return response

        notes_with_reason = f"{reason}: {notes}" if reason and notes else (reason or notes)

        try:
            if movement_type == "IN":
                StockService.add_stock(
                    product,
                    quantity,
                    reference_type="manual",
                    notes=notes_with_reason,
                    movement_type="IN",
                    created_by=request.user,
                )
            elif movement_type == "RETURN":
                StockService.add_stock(
                    product,
                    quantity,
                    reference_type="return",
                    notes=notes_with_reason,
                    movement_type="RETURN",
                    created_by=request.user,
                )
            elif movement_type == "OUT":
                StockService.deduct_stock(
                    product,
                    quantity,
                    reference_type="manual",
                    notes=notes_with_reason,
                    created_by=request.user,
                )
            else:
                StockService.adjust_stock(product, quantity, notes=notes_with_reason, created_by=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            response = render(request, "products/_stock_modal.html", {"product": product}, status=400)
            return response

        product.refresh_from_db(fields=["current_stock"])
        messages.success(request, f"Stock updated. New stock: {product.current_stock}")
        response = HttpResponse("")
        response["HX-Trigger"] = "stockUpdated"
        return response


@method_decorator(login_required, name="dispatch")
class StockHistoryView(View):
    """Paginated stock movement history partial for a product."""

    def get(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        product = get_object_or_404(Product, company=company, pk=pk)

        movement_type = (request.GET.get("movement_type") or "").strip().upper()
        queryset = StockMovement.objects.filter(product=product).select_related("created_by").order_by("-created_at")
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)

        paginator = Paginator(queryset, 20)
        page_obj = paginator.get_page(int(request.GET.get("page", 1) or 1))

        pagination = {
            "page": page_obj.number,
            "page_size": 20,
            "total": paginator.count,
            "total_pages": paginator.num_pages,
        }
        return render(
            request,
            "products/_stock_history.html",
            {"movements": page_obj.object_list, "page_obj": page_obj, "pagination": pagination, "product": product},
        )


@method_decorator(login_required, name="dispatch")
class ProductCategoryListView(View):
    """List categories partial for HTMX settings modal."""

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        categories = ProductCategory.objects.filter(company=company, is_active=True).order_by("name")
        return render(request, "products/_category_list.html", {"categories": categories})


@method_decorator(login_required, name="dispatch")
class ProductCategoryCreateView(View):
    """Create a category through HTMX."""

    def post(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()

        if not name:
            messages.error(request, "Category name is required")
        elif ProductCategory.objects.filter(company=company, name__iexact=name, is_active=True).exists():
            messages.error(request, "Category already exists")
        else:
            ProductCategory.objects.create(company=company, name=name, description=description, is_active=True)
            messages.success(request, "Category created successfully")

        categories = ProductCategory.objects.filter(company=company, is_active=True).order_by("name")
        response = render(request, "products/_category_list.html", {"categories": categories})
        response["HX-Trigger"] = "categoryListChanged"
        return response


@method_decorator(login_required, name="dispatch")
class ProductCategoryDeleteView(View):
    """Soft-delete a category."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        company = request.user.company_profile
        category = get_object_or_404(ProductCategory, company=company, pk=pk)
        category.is_active = False
        category.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Category deleted")

        categories = ProductCategory.objects.filter(company=company, is_active=True).order_by("name")
        response = render(request, "products/_category_list.html", {"categories": categories})
        response["HX-Trigger"] = "categoryListChanged"
        return response


@method_decorator(login_required, name="dispatch")
class BulkUploadView(OnboardingCheckMixin, View):
    """Bulk import products from CSV in a single transaction."""

    template_name = "products/bulk_upload.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        units = UnitOfMeasurement.objects.filter(company=company, is_active=True).order_by("short_name")
        return render(request, self.template_name, {"units": units, "row_errors": [], "page_title": "Bulk Upload"})

    def post(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        units = UnitOfMeasurement.objects.filter(company=company, is_active=True).order_by("short_name")

        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            messages.error(request, "Please upload a CSV file")
            return render(request, self.template_name, {"units": units, "row_errors": [{"row_num": 0, "field": "csv_file", "error": "Missing file"}]}, status=400)

        try:
            content = csv_file.read().decode("utf-8-sig")
        except Exception:
            messages.error(request, "Unable to read CSV file")
            return render(request, self.template_name, {"units": units, "row_errors": [{"row_num": 0, "field": "csv_file", "error": "Invalid encoding"}]}, status=400)

        reader = csv.DictReader(io.StringIO(content))
        fieldnames = [((name or "").strip().lower()) for name in (reader.fieldnames or [])]
        required = {"name", "hsn_code", "unit", "selling_price", "gst_rate"}
        if not required.issubset(set(fieldnames)):
            messages.error(request, "CSV headers are invalid")
            return render(
                request,
                self.template_name,
                {
                    "units": units,
                    "row_errors": [{"row_num": 0, "field": "headers", "error": "Required columns are missing: name, hsn_code, unit, selling_price, gst_rate"}],
                },
                status=400,
            )

        # Normalize row keys so CSV headers like "Name" or " selling_price " are accepted.
        normalized_rows = []
        for raw_row in reader:
            normalized_rows.append({((key or "").strip().lower()): value for key, value in raw_row.items()})

        row_errors: list[dict] = []
        prepared_rows: list[dict] = []
        csv_names_seen: set[str] = set()

        for idx, row in enumerate(normalized_rows, start=2):
            name = (row.get("name") or "").strip()
            hsn_code = (row.get("hsn_code") or "").strip()
            unit_short = (row.get("unit") or "").strip()
            selling_raw = (row.get("selling_price") or "").strip()
            gst_raw = (row.get("gst_rate") or "").strip()
            category_name = (row.get("category") or "").strip()
            current_raw = (row.get("current_stock") or "0").strip()
            minimum_raw = (row.get("minimum_stock") or "0").strip()
            sku = (row.get("sku") or "").strip()
            purchase_raw = (row.get("purchase_price") or "").strip()
            description = (row.get("description") or "").strip()

            if not name:
                row_errors.append({"row_num": idx, "field": "name", "error": "Name is required"})
                continue
            if name.lower() in csv_names_seen:
                row_errors.append({"row_num": idx, "field": "name", "error": "Duplicate product name in CSV"})
                continue
            csv_names_seen.add(name.lower())

            if Product.objects.filter(company=company, name__iexact=name).exists():
                row_errors.append({"row_num": idx, "field": "name", "error": "Product name already exists"})
                continue

            if not HSN_REGEX.match(hsn_code):
                row_errors.append({"row_num": idx, "field": "hsn_code", "error": "HSN must be 4-8 digits"})
                continue

            unit = UnitOfMeasurement.objects.filter(company=company, short_name__iexact=unit_short, is_active=True).first()
            if not unit:
                row_errors.append({"row_num": idx, "field": "unit", "error": f"Unit '{unit_short}' not found"})
                continue

            try:
                selling_price = Decimal(selling_raw)
                if selling_price < 0:
                    raise InvalidOperation
            except Exception:
                row_errors.append({"row_num": idx, "field": "selling_price", "error": "Invalid selling price"})
                continue

            try:
                gst_rate = Decimal(gst_raw)
                if gst_rate not in ALLOWED_GST:
                    raise InvalidOperation
            except Exception:
                row_errors.append({"row_num": idx, "field": "gst_rate", "error": "GST must be one of 0, 5, 12, 18, 28"})
                continue

            try:
                current_stock = Decimal(current_raw or "0")
                if current_stock < 0:
                    raise InvalidOperation
            except Exception:
                row_errors.append({"row_num": idx, "field": "current_stock", "error": "Invalid current stock"})
                continue

            try:
                minimum_stock = Decimal(minimum_raw or "0")
                if minimum_stock < 0:
                    raise InvalidOperation
            except Exception:
                row_errors.append({"row_num": idx, "field": "minimum_stock", "error": "Invalid minimum stock"})
                continue

            try:
                purchase_price = Decimal(purchase_raw) if purchase_raw else None
                if purchase_price is not None and purchase_price < 0:
                    raise InvalidOperation
            except Exception:
                row_errors.append({"row_num": idx, "field": "purchase_price", "error": "Invalid purchase price"})
                continue

            prepared_rows.append(
                {
                    "name": name,
                    "hsn_code": hsn_code,
                    "unit": unit,
                    "selling_price": selling_price,
                    "gst_rate": gst_rate,
                    "category_name": category_name,
                    "current_stock": current_stock,
                    "minimum_stock": minimum_stock,
                    "sku": sku,
                    "purchase_price": purchase_price,
                    "description": description,
                }
            )

        if row_errors:
            messages.error(request, "Import failed. Fix errors and try again.")
            return render(request, self.template_name, {"units": units, "row_errors": row_errors}, status=400)

        created_count = 0
        try:
            with transaction.atomic():
                for row in prepared_rows:
                    category = None
                    if row["category_name"]:
                        category, _ = ProductCategory.objects.get_or_create(
                            company=company,
                            name=row["category_name"],
                            defaults={"description": "", "is_active": True},
                        )
                        if not category.is_active:
                            category.is_active = True
                            category.save(update_fields=["is_active", "updated_at"])

                    product = Product.objects.create(
                        company=company,
                        category=category,
                        unit=row["unit"],
                        name=row["name"],
                        description=row["description"],
                        sku=row["sku"],
                        hsn_code=row["hsn_code"],
                        selling_price=row["selling_price"],
                        purchase_price=row["purchase_price"],
                        gst_rate=row["gst_rate"],
                        cess_rate=Decimal("0"),
                        is_service=False,
                        track_inventory=True,
                        minimum_stock=row["minimum_stock"],
                    )
                    if row["current_stock"] > 0:
                        StockService.set_opening_stock(product, row["current_stock"], request.user)
                    created_count += 1
        except Exception as exc:
            messages.error(request, f"Import failed: {exc}")
            return render(
                request,
                self.template_name,
                {"units": units, "row_errors": [{"row_num": 0, "field": "import", "error": str(exc)}]},
                status=400,
            )

        messages.success(request, f"{created_count} products imported successfully")
        return redirect("products_ui:product-list")


@method_decorator(login_required, name="dispatch")
class CSVTemplateDownloadView(View):
    """Download sample CSV template for bulk product import."""

    def get(self, request: HttpRequest) -> HttpResponse:
        content = io.StringIO()
        writer = csv.writer(content)
        writer.writerow([
            "name",
            "hsn_code",
            "unit",
            "selling_price",
            "gst_rate",
            "category",
            "current_stock",
            "minimum_stock",
            "sku",
            "purchase_price",
            "description",
        ])
        writer.writerow([
            "OPC Cement 53 Grade",
            "2523",
            "BAG",
            "385.00",
            "28",
            "Cement",
            "120",
            "25",
            "CEM-OPC-53",
            "340.00",
            "High strength ordinary Portland cement",
        ])
        writer.writerow([
            "TMT Bar 12mm",
            "7214",
            "KG",
            "62.50",
            "18",
            "Steel",
            "5000",
            "1000",
            "TMT-12",
            "56.00",
            "Fe500 grade reinforcement steel bar",
        ])

        response = HttpResponse(content.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="product_template.csv"'
        return response
