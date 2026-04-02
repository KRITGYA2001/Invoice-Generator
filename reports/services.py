from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db.models import Avg, Case, Count, DecimalField, ExpressionWrapper, F, Max, Min, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone


def money(value: Any) -> str:
    """Return a 2-decimal monetary string for JSON responses."""
    decimal_value = Decimal(value or 0)
    return str(decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def ratio(value: Any) -> str:
    """Return a 2-decimal ratio string for percentages."""
    decimal_value = Decimal(value or 0)
    return str(decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class DashboardService:
    """Dashboard-oriented aggregate metrics."""

    @staticmethod
    def get_current_financial_year() -> str:
        """Return Indian financial year in YY-YY format."""
        today = timezone.localdate()
        start_year = today.year if today.month >= 4 else today.year - 1
        end_year = start_year + 1
        return f"{str(start_year)[-2:]}-{str(end_year)[-2:]}"

    @staticmethod
    def _financial_year_bounds(financial_year: str) -> tuple[date, date]:
        """Convert YY-YY financial year to concrete dates."""
        start_yy, end_yy = financial_year.split("-")
        start_year = int(f"20{start_yy}")
        end_year = int(f"20{end_yy}")
        return date(start_year, 4, 1), date(end_year, 3, 31)

    @staticmethod
    def get_overview(company, financial_year: str | None = None) -> dict[str, Any]:
        """Return top-level dashboard overview metrics."""
        from customers.models import Customer
        from invoices.models import Invoice
        from products.models import Product

        fy = financial_year or DashboardService.get_current_financial_year()
        fy_start, fy_end = DashboardService._financial_year_bounds(fy)

        invoice_counts = (
            Invoice.objects.filter(company=company, invoice_date__gte=fy_start, invoice_date__lte=fy_end)
            .aggregate(
                total=Count("id"),
                issued=Count("id", filter=Q(status=Invoice.StatusChoices.ISSUED)),
                draft=Count("id", filter=Q(status=Invoice.StatusChoices.DRAFT)),
                cancelled=Count("id", filter=Q(status=Invoice.StatusChoices.CANCELLED)),
            )
        )

        issued_queryset = Invoice.objects.filter(
            company=company,
            status=Invoice.StatusChoices.ISSUED,
            invoice_date__gte=fy_start,
            invoice_date__lte=fy_end,
        )
        revenue_aggregate = issued_queryset.aggregate(
            total_taxable=Coalesce(Sum("subtotal"), Decimal("0.00")),
            total_tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
            total_revenue=Coalesce(Sum("grand_total"), Decimal("0.00")),
            average_invoice=Coalesce(Avg("grand_total"), Decimal("0.00")),
            total_cgst=Coalesce(Sum("total_cgst"), Decimal("0.00")),
            total_sgst=Coalesce(Sum("total_sgst"), Decimal("0.00")),
            total_igst=Coalesce(Sum("total_igst"), Decimal("0.00")),
            total_cess=Coalesce(Sum("total_cess"), Decimal("0.00")),
        )

        month_start = timezone.localdate().replace(day=1)
        customers_aggregate = Customer.objects.filter(company=company).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            new_this_month=Count("id", filter=Q(created_at__date__gte=month_start)),
        )

        products_aggregate = Product.objects.filter(company=company).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            low_stock=Count("id", filter=Q(is_active=True, track_inventory=True, current_stock__lt=F("minimum_stock"))),
            out_of_stock=Count("id", filter=Q(is_active=True, track_inventory=True, current_stock__lte=Decimal("0"))),
        )

        recent_invoices = list(
            issued_queryset.values("id", "invoice_number", "customer_name", "invoice_date", "grand_total", "status")
            .order_by("-invoice_date", "-created_at")[:5]
        )

        top_customers = list(
            issued_queryset.values("customer", "customer_name")
            .annotate(invoice_count=Count("id"), total_revenue=Coalesce(Sum("grand_total"), Decimal("0.00")))
            .order_by("-total_revenue", "customer_name")[:5]
        )

        low_stock_alerts = list(
            Product.objects.filter(
                company=company,
                is_active=True,
                track_inventory=True,
                current_stock__lt=F("minimum_stock"),
            )
            .values("id", "name", "current_stock", "minimum_stock", "unit__short_name")
            .order_by("current_stock", "name")[:10]
        )

        return {
            "financial_year": fy,
            "invoices": {
                "total": int(invoice_counts.get("total") or 0),
                "issued": int(invoice_counts.get("issued") or 0),
                "draft": int(invoice_counts.get("draft") or 0),
                "cancelled": int(invoice_counts.get("cancelled") or 0),
            },
            "revenue": {
                "total_taxable": money(revenue_aggregate.get("total_taxable")),
                "total_tax": money(revenue_aggregate.get("total_tax")),
                "total_revenue": money(revenue_aggregate.get("total_revenue")),
                "average_invoice": money(revenue_aggregate.get("average_invoice")),
            },
            "gst": {
                "total_cgst": money(revenue_aggregate.get("total_cgst")),
                "total_sgst": money(revenue_aggregate.get("total_sgst")),
                "total_igst": money(revenue_aggregate.get("total_igst")),
                "total_cess": money(revenue_aggregate.get("total_cess")),
                "total_tax_collected": money(revenue_aggregate.get("total_tax")),
            },
            "customers": {
                "total": int(customers_aggregate.get("total") or 0),
                "active": int(customers_aggregate.get("active") or 0),
                "new_this_month": int(customers_aggregate.get("new_this_month") or 0),
            },
            "products": {
                "total": int(products_aggregate.get("total") or 0),
                "active": int(products_aggregate.get("active") or 0),
                "low_stock": int(products_aggregate.get("low_stock") or 0),
                "out_of_stock": int(products_aggregate.get("out_of_stock") or 0),
            },
            "recent_invoices": [
                {
                    "id": str(row["id"]),
                    "invoice_number": row["invoice_number"],
                    "customer_name": row["customer_name"],
                    "invoice_date": row["invoice_date"].isoformat() if row["invoice_date"] else None,
                    "grand_total": money(row["grand_total"]),
                    "status": row["status"],
                }
                for row in recent_invoices
            ],
            "top_customers": [
                {
                    "customer_id": str(row["customer"]) if row["customer"] else None,
                    "customer_name": row["customer_name"],
                    "invoice_count": int(row["invoice_count"]),
                    "total_revenue": money(row["total_revenue"]),
                }
                for row in top_customers
            ],
            "low_stock_alerts": [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "current_stock": money(row["current_stock"]),
                    "minimum_stock": money(row["minimum_stock"]),
                    "unit": row["unit__short_name"] or "",
                }
                for row in low_stock_alerts
            ],
        }

    @staticmethod
    def get_monthly_trend(company, financial_year: str | None = None) -> dict[str, Any]:
        """Return month-wise revenue trend for a financial year."""
        from invoices.models import Invoice

        fy = financial_year or DashboardService.get_current_financial_year()
        fy_start, fy_end = DashboardService._financial_year_bounds(fy)

        rows = list(
            Invoice.objects.filter(
                company=company,
                status=Invoice.StatusChoices.ISSUED,
                invoice_date__gte=fy_start,
                invoice_date__lte=fy_end,
            )
            .annotate(month_date=TruncMonth("invoice_date"))
            .values("month_date")
            .annotate(
                invoice_count=Count("id"),
                taxable_amount=Coalesce(Sum("subtotal"), Decimal("0.00")),
                tax_amount=Coalesce(Sum("total_tax"), Decimal("0.00")),
                revenue=Coalesce(Sum("grand_total"), Decimal("0.00")),
            )
            .order_by("month_date")
        )
        by_month = {row["month_date"]: row for row in rows}

        months = []
        current = fy_start
        for _ in range(12):
            month_key = current.replace(day=1)
            row = by_month.get(month_key)
            months.append(
                {
                    "month": month_key.strftime("%b %Y"),
                    "month_number": month_key.month,
                    "year": month_key.year,
                    "invoice_count": int((row or {}).get("invoice_count") or 0),
                    "taxable_amount": money((row or {}).get("taxable_amount")),
                    "tax_amount": money((row or {}).get("tax_amount")),
                    "revenue": money((row or {}).get("revenue")),
                }
            )
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

        return {"financial_year": fy, "months": months}


class GSTReportService:
    """GST-focused reports for filing and reconciliation."""

    @staticmethod
    def get_gst_summary(company, date_from: date, date_to: date) -> dict[str, Any]:
        """Return GSTR-1 style summary for a date period."""
        from invoices.models import Invoice, InvoiceLineItem

        invoices = Invoice.objects.filter(
            company=company,
            status=Invoice.StatusChoices.ISSUED,
            invoice_date__gte=date_from,
            invoice_date__lte=date_to,
        )

        summary = invoices.aggregate(
            total_invoices=Count("id"),
            total_taxable=Coalesce(Sum("subtotal"), Decimal("0.00")),
            total_cgst=Coalesce(Sum("total_cgst"), Decimal("0.00")),
            total_sgst=Coalesce(Sum("total_sgst"), Decimal("0.00")),
            total_igst=Coalesce(Sum("total_igst"), Decimal("0.00")),
            total_cess=Coalesce(Sum("total_cess"), Decimal("0.00")),
            total_tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
            grand_total=Coalesce(Sum("grand_total"), Decimal("0.00")),
        )

        interstate = invoices.filter(is_interstate=True).aggregate(
            invoice_count=Count("id"),
            taxable_amount=Coalesce(Sum("subtotal"), Decimal("0.00")),
            igst=Coalesce(Sum("total_igst"), Decimal("0.00")),
        )

        intrastate = invoices.filter(is_interstate=False).aggregate(
            invoice_count=Count("id"),
            taxable_amount=Coalesce(Sum("subtotal"), Decimal("0.00")),
            cgst=Coalesce(Sum("total_cgst"), Decimal("0.00")),
            sgst=Coalesce(Sum("total_sgst"), Decimal("0.00")),
        )

        rate_rows = list(
            InvoiceLineItem.objects.filter(
                invoice__company=company,
                invoice__status=Invoice.StatusChoices.ISSUED,
                invoice__invoice_date__gte=date_from,
                invoice__invoice_date__lte=date_to,
            )
            .values("gst_rate")
            .annotate(
                invoice_count=Count("invoice_id", distinct=True),
                taxable_amount=Coalesce(Sum("taxable_amount"), Decimal("0.00")),
                cgst_amount=Coalesce(Sum("cgst_amount"), Decimal("0.00")),
                sgst_amount=Coalesce(Sum("sgst_amount"), Decimal("0.00")),
                igst_amount=Coalesce(Sum("igst_amount"), Decimal("0.00")),
                total_tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
            )
            .order_by("gst_rate")
        )

        reverse_charge = invoices.filter(reverse_charge=True).aggregate(
            invoice_count=Count("id"),
            taxable_amount=Coalesce(Sum("subtotal"), Decimal("0.00")),
            total_tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
        )

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "summary": {
                "total_invoices": int(summary.get("total_invoices") or 0),
                "total_taxable": money(summary.get("total_taxable")),
                "total_cgst": money(summary.get("total_cgst")),
                "total_sgst": money(summary.get("total_sgst")),
                "total_igst": money(summary.get("total_igst")),
                "total_cess": money(summary.get("total_cess")),
                "total_tax": money(summary.get("total_tax")),
                "grand_total": money(summary.get("grand_total")),
            },
            "interstate_summary": {
                "invoice_count": int(interstate.get("invoice_count") or 0),
                "taxable_amount": money(interstate.get("taxable_amount")),
                "igst": money(interstate.get("igst")),
            },
            "intrastate_summary": {
                "invoice_count": int(intrastate.get("invoice_count") or 0),
                "taxable_amount": money(intrastate.get("taxable_amount")),
                "cgst": money(intrastate.get("cgst")),
                "sgst": money(intrastate.get("sgst")),
            },
            "rate_wise_summary": [
                {
                    "gst_rate": money(row["gst_rate"]),
                    "invoice_count": int(row["invoice_count"]),
                    "taxable_amount": money(row["taxable_amount"]),
                    "cgst_amount": money(row["cgst_amount"]),
                    "sgst_amount": money(row["sgst_amount"]),
                    "igst_amount": money(row["igst_amount"]),
                    "total_tax": money(row["total_tax"]),
                }
                for row in rate_rows
            ],
            "reverse_charge_summary": {
                "invoice_count": int(reverse_charge.get("invoice_count") or 0),
                "taxable_amount": money(reverse_charge.get("taxable_amount")),
                "total_tax": money(reverse_charge.get("total_tax")),
            },
        }

    @staticmethod
    def get_gstr1_invoice_list(company, date_from: date, date_to: date) -> dict[str, Any]:
        """Return detailed GSTR-1 invoice list with line-level tax breakup."""
        from invoices.models import Invoice, InvoiceLineItem

        invoice_rows = list(
            Invoice.objects.filter(
                company=company,
                status=Invoice.StatusChoices.ISSUED,
                invoice_date__gte=date_from,
                invoice_date__lte=date_to,
            )
            .values(
                "id",
                "invoice_number",
                "invoice_date",
                "customer_name",
                "customer_gstin",
                "customer_state",
                "place_of_supply",
                "is_interstate",
                "reverse_charge",
                "subtotal",
                "total_cgst",
                "total_sgst",
                "total_igst",
                "total_cess",
                "total_tax",
                "grand_total",
            )
            .order_by("invoice_date", "invoice_number")
        )

        line_rows = list(
            InvoiceLineItem.objects.filter(
                invoice__company=company,
                invoice__status=Invoice.StatusChoices.ISSUED,
                invoice__invoice_date__gte=date_from,
                invoice__invoice_date__lte=date_to,
            )
            .values(
                "invoice_id",
                "hsn_code",
                "gst_rate",
                "taxable_amount",
                "cgst_amount",
                "sgst_amount",
                "igst_amount",
            )
            .order_by("invoice_id", "gst_rate", "hsn_code")
        )

        rate_map: dict[Any, list[dict[str, str]]] = {}
        for row in line_rows:
            rate_map.setdefault(row["invoice_id"], []).append(
                {
                    "hsn_code": row["hsn_code"],
                    "gst_rate": money(row["gst_rate"]),
                    "taxable": money(row["taxable_amount"]),
                    "cgst": money(row["cgst_amount"]),
                    "sgst": money(row["sgst_amount"]),
                    "igst": money(row["igst_amount"]),
                }
            )

        invoices = [
            {
                "invoice_number": row["invoice_number"],
                "invoice_date": row["invoice_date"].strftime("%d-%m-%Y") if row["invoice_date"] else "",
                "customer_name": row["customer_name"],
                "customer_gstin": row["customer_gstin"],
                "customer_state": row["customer_state"],
                "place_of_supply": row["place_of_supply"],
                "is_interstate": bool(row["is_interstate"]),
                "reverse_charge": bool(row["reverse_charge"]),
                "taxable_amount": money(row["subtotal"]),
                "cgst": money(row["total_cgst"]),
                "sgst": money(row["total_sgst"]),
                "igst": money(row["total_igst"]),
                "cess": money(row["total_cess"]),
                "total_tax": money(row["total_tax"]),
                "grand_total": money(row["grand_total"]),
                "rate_wise": rate_map.get(row["id"], []),
            }
            for row in invoice_rows
        ]

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "invoices": invoices,
            "total_count": len(invoices),
        }

    @staticmethod
    def get_hsn_summary(company, date_from: date, date_to: date) -> dict[str, Any]:
        """Return HSN summary for GSTR-1 table 12."""
        from invoices.models import Invoice, InvoiceLineItem

        base = InvoiceLineItem.objects.filter(
            invoice__company=company,
            invoice__status=Invoice.StatusChoices.ISSUED,
            invoice__invoice_date__gte=date_from,
            invoice__invoice_date__lte=date_to,
        )

        summary_rows = list(
            base.values("hsn_code", "gst_rate")
            .annotate(
                total_quantity=Coalesce(Sum("quantity"), Decimal("0.00")),
                total_taxable=Coalesce(Sum("taxable_amount"), Decimal("0.00")),
                cgst_amount=Coalesce(Sum("cgst_amount"), Decimal("0.00")),
                sgst_amount=Coalesce(Sum("sgst_amount"), Decimal("0.00")),
                igst_amount=Coalesce(Sum("igst_amount"), Decimal("0.00")),
                total_tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
            )
            .order_by("hsn_code", "gst_rate")
        )

        description_rows = list(
            base.values("hsn_code", "gst_rate", "product_name")
            .annotate(freq=Count("id"))
            .order_by("hsn_code", "gst_rate", "-freq", "product_name")
        )
        unit_rows = list(
            base.values("hsn_code", "gst_rate", "unit")
            .annotate(freq=Count("id"))
            .order_by("hsn_code", "gst_rate", "-freq", "unit")
        )

        description_map: dict[tuple[Any, Any], str] = {}
        for row in description_rows:
            key = (row["hsn_code"], row["gst_rate"])
            description_map.setdefault(key, row["product_name"])

        unit_map: dict[tuple[Any, Any], str] = {}
        for row in unit_rows:
            key = (row["hsn_code"], row["gst_rate"])
            unit_map.setdefault(key, row["unit"])

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "hsn_summary": [
                {
                    "hsn_code": row["hsn_code"],
                    "description": description_map.get((row["hsn_code"], row["gst_rate"]), ""),
                    "uqc": unit_map.get((row["hsn_code"], row["gst_rate"]), ""),
                    "total_quantity": money(row["total_quantity"]),
                    "total_taxable": money(row["total_taxable"]),
                    "gst_rate": money(row["gst_rate"]),
                    "cgst_amount": money(row["cgst_amount"]),
                    "sgst_amount": money(row["sgst_amount"]),
                    "igst_amount": money(row["igst_amount"]),
                    "total_tax": money(row["total_tax"]),
                }
                for row in summary_rows
            ],
        }


class SalesReportService:
    """Sales analytics across customer, product, category and day."""

    @staticmethod
    def _issued_invoice_queryset(company, date_from: date, date_to: date):
        """Base issued-invoice queryset scoped by company and invoice_date."""
        from invoices.models import Invoice

        return Invoice.objects.filter(
            company=company,
            status=Invoice.StatusChoices.ISSUED,
            invoice_date__gte=date_from,
            invoice_date__lte=date_to,
        )

    @staticmethod
    def get_sales_by_customer(company, date_from: date, date_to: date, limit: int = 10) -> dict[str, Any]:
        """Return top customers by revenue share."""
        invoices = SalesReportService._issued_invoice_queryset(company, date_from, date_to)
        total_revenue = invoices.aggregate(total=Coalesce(Sum("grand_total"), Decimal("0.00")))["total"]

        rows = list(
            invoices.values("customer", "customer_name", "customer_gstin")
            .annotate(
                invoice_count=Count("id"),
                taxable_amount=Coalesce(Sum("subtotal"), Decimal("0.00")),
                total_tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
                grand_total=Coalesce(Sum("grand_total"), Decimal("0.00")),
            )
            .order_by("-grand_total", "customer_name")[:limit]
        )

        total_revenue_decimal = Decimal(total_revenue or 0)
        customers = []
        for row in rows:
            share = Decimal("0.00")
            if total_revenue_decimal > 0:
                share = (Decimal(row["grand_total"]) * Decimal("100")) / total_revenue_decimal
            customers.append(
                {
                    "customer_id": str(row["customer"]) if row["customer"] else None,
                    "customer_name": row["customer_name"],
                    "customer_gstin": row["customer_gstin"],
                    "invoice_count": int(row["invoice_count"]),
                    "taxable_amount": money(row["taxable_amount"]),
                    "total_tax": money(row["total_tax"]),
                    "grand_total": money(row["grand_total"]),
                    "percentage": ratio(share),
                }
            )

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "customers": customers,
            "total_revenue": money(total_revenue_decimal),
        }

    @staticmethod
    def get_sales_by_product(company, date_from: date, date_to: date, limit: int = 10) -> dict[str, Any]:
        """Return top products by revenue share."""
        from invoices.models import Invoice, InvoiceLineItem

        line_items = InvoiceLineItem.objects.filter(
            invoice__company=company,
            invoice__status=Invoice.StatusChoices.ISSUED,
            invoice__invoice_date__gte=date_from,
            invoice__invoice_date__lte=date_to,
        )

        total_revenue = line_items.aggregate(total=Coalesce(Sum("line_total"), Decimal("0.00")))["total"]

        rows = list(
            line_items.values("product", "product_name", "hsn_code", "unit")
            .annotate(
                total_quantity=Coalesce(Sum("quantity"), Decimal("0.00")),
                taxable_amount=Coalesce(Sum("taxable_amount"), Decimal("0.00")),
                total_tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
                line_total=Coalesce(Sum("line_total"), Decimal("0.00")),
                invoice_count=Count("invoice_id", distinct=True),
            )
            .order_by("-line_total", "product_name")[:limit]
        )

        total_revenue_decimal = Decimal(total_revenue or 0)
        products = []
        for row in rows:
            share = Decimal("0.00")
            if total_revenue_decimal > 0:
                share = (Decimal(row["line_total"]) * Decimal("100")) / total_revenue_decimal
            products.append(
                {
                    "product_id": str(row["product"]) if row["product"] else None,
                    "product_name": row["product_name"],
                    "hsn_code": row["hsn_code"],
                    "total_quantity": money(row["total_quantity"]),
                    "unit": row["unit"],
                    "taxable_amount": money(row["taxable_amount"]),
                    "total_tax": money(row["total_tax"]),
                    "line_total": money(row["line_total"]),
                    "invoice_count": int(row["invoice_count"]),
                    "percentage": ratio(share),
                }
            )

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "products": products,
            "total_revenue": money(total_revenue_decimal),
        }

    @staticmethod
    def get_sales_by_category(company, date_from: date, date_to: date) -> dict[str, Any]:
        """Return sales breakup by product category."""
        from invoices.models import Invoice, InvoiceLineItem

        line_items = InvoiceLineItem.objects.filter(
            invoice__company=company,
            invoice__status=Invoice.StatusChoices.ISSUED,
            invoice__invoice_date__gte=date_from,
            invoice__invoice_date__lte=date_to,
        )

        total_taxable = line_items.aggregate(total=Coalesce(Sum("taxable_amount"), Decimal("0.00")))["total"]

        rows = list(
            line_items.values(category_name=Coalesce("product__category__name", Value("Uncategorized")))
            .annotate(
                product_count=Count("product", distinct=True),
                invoice_count=Count("invoice_id", distinct=True),
                taxable_amount=Coalesce(Sum("taxable_amount"), Decimal("0.00")),
            )
            .order_by("-taxable_amount", "category_name")
        )

        total_taxable_decimal = Decimal(total_taxable or 0)
        categories = []
        for row in rows:
            share = Decimal("0.00")
            if total_taxable_decimal > 0:
                share = (Decimal(row["taxable_amount"]) * Decimal("100")) / total_taxable_decimal
            categories.append(
                {
                    "category_name": row["category_name"],
                    "product_count": int(row["product_count"]),
                    "invoice_count": int(row["invoice_count"]),
                    "taxable_amount": money(row["taxable_amount"]),
                    "percentage": ratio(share),
                }
            )

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "categories": categories,
        }

    @staticmethod
    def get_daily_sales(company, date_from: date, date_to: date) -> dict[str, Any]:
        """Return day-wise sales with zero-filled dates."""
        invoices = SalesReportService._issued_invoice_queryset(company, date_from, date_to)

        rows = list(
            invoices.annotate(sales_date=TruncDate("invoice_date"))
            .values("sales_date")
            .annotate(
                invoice_count=Count("id"),
                revenue=Coalesce(Sum("grand_total"), Decimal("0.00")),
                tax=Coalesce(Sum("total_tax"), Decimal("0.00")),
            )
            .order_by("sales_date")
        )

        by_date = {row["sales_date"]: row for row in rows}
        output = []
        current = date_from
        while current <= date_to:
            row = by_date.get(current)
            output.append(
                {
                    "date": current.isoformat(),
                    "invoice_count": int((row or {}).get("invoice_count") or 0),
                    "revenue": money((row or {}).get("revenue")),
                    "tax": money((row or {}).get("tax")),
                }
            )
            current += timedelta(days=1)

        return {"period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}, "daily": output}


class InventoryReportService:
    """Inventory valuation and movement reporting."""

    @staticmethod
    def get_stock_valuation(company) -> dict[str, Any]:
        """Return overall stock valuation and per-product details."""
        from products.models import Product

        purchase_price_expr = Coalesce(F("purchase_price"), F("selling_price"))
        stock_value_expr = ExpressionWrapper(F("current_stock") * purchase_price_expr, output_field=DecimalField(max_digits=16, decimal_places=2))
        selling_value_expr = ExpressionWrapper(F("current_stock") * F("selling_price"), output_field=DecimalField(max_digits=16, decimal_places=2))

        product_base = Product.objects.filter(company=company, is_active=True)

        summary = product_base.aggregate(
            total_products=Count("id"),
            total_stock_value=Coalesce(Sum(stock_value_expr), Decimal("0.00")),
            total_selling_value=Coalesce(Sum(selling_value_expr), Decimal("0.00")),
        )
        potential_profit = Decimal(summary["total_selling_value"] or 0) - Decimal(summary["total_stock_value"] or 0)

        by_category_rows = list(
            product_base.values(category_name=Coalesce("category__name", Value("Uncategorized")))
            .annotate(
                product_count=Count("id"),
                stock_value=Coalesce(Sum(stock_value_expr), Decimal("0.00")),
            )
            .order_by("-stock_value", "category_name")
        )

        product_rows = list(
            product_base.values(
                "id",
                "name",
                "sku",
                "category__name",
                "unit__short_name",
                "current_stock",
                "minimum_stock",
                "purchase_price",
                "selling_price",
                "track_inventory",
            )
            .annotate(
                stock_value=Coalesce(stock_value_expr, Decimal("0.00")),
                selling_value=Coalesce(selling_value_expr, Decimal("0.00")),
            )
            .order_by("-stock_value", "name")
        )

        return {
            "generated_at": timezone.now().isoformat(),
            "summary": {
                "total_products": int(summary.get("total_products") or 0),
                "total_stock_value": money(summary.get("total_stock_value")),
                "total_selling_value": money(summary.get("total_selling_value")),
                "potential_profit": money(potential_profit),
            },
            "by_category": [
                {
                    "category_name": row["category_name"],
                    "product_count": int(row["product_count"]),
                    "stock_value": money(row["stock_value"]),
                }
                for row in by_category_rows
            ],
            "products": [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "sku": row["sku"],
                    "category": row["category__name"] or "Uncategorized",
                    "unit": row["unit__short_name"] or "",
                    "current_stock": money(row["current_stock"]),
                    "purchase_price": money(row["purchase_price"]),
                    "selling_price": money(row["selling_price"]),
                    "stock_value": money(row["stock_value"]),
                    "selling_value": money(row["selling_value"]),
                    "is_low_stock": bool(
                        row["track_inventory"] and Decimal(row["current_stock"] or 0) <= Decimal(row["minimum_stock"] or 0)
                    ),
                }
                for row in product_rows
            ],
        }

    @staticmethod
    def get_stock_movement_report(company, date_from: date, date_to: date, product_id=None) -> dict[str, Any]:
        """Return stock movement totals and rows."""
        from products.models import StockMovement

        filters = {
            "product__company": company,
            "created_at__date__gte": date_from,
            "created_at__date__lte": date_to,
        }
        if product_id:
            filters["product_id"] = product_id

        queryset = StockMovement.objects.filter(**filters)

        summary = queryset.aggregate(
            total_in=Coalesce(
                Sum("quantity", filter=Q(movement_type__in=["IN", "RETURN", "OPENING"])),
                Decimal("0.00"),
            ),
            total_out=Coalesce(Sum("quantity", filter=Q(movement_type="OUT")), Decimal("0.00")),
        )

        movement_rows = list(
            queryset.select_related("product", "created_by")
            .values(
                "created_at",
                "product__name",
                "movement_type",
                "quantity",
                "stock_before",
                "stock_after",
                "reference_type",
                "notes",
                "created_by__email",
            )
            .order_by("-created_at")
        )

        total_in = Decimal(summary.get("total_in") or 0)
        total_out = Decimal(summary.get("total_out") or 0)

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "summary": {
                "total_in": money(total_in),
                "total_out": money(total_out),
                "net_movement": money(total_in - total_out),
            },
            "movements": [
                {
                    "date": row["created_at"].date().isoformat() if row["created_at"] else "",
                    "product_name": row["product__name"],
                    "movement_type": row["movement_type"],
                    "quantity": money(row["quantity"]),
                    "stock_before": money(row["stock_before"]),
                    "stock_after": money(row["stock_after"]),
                    "reference_type": row["reference_type"],
                    "notes": row["notes"],
                    "created_by": row["created_by__email"] or "",
                }
                for row in movement_rows
            ],
        }

    @staticmethod
    def get_low_stock_report(company) -> dict[str, Any]:
        """Return products at or below minimum stock."""
        from products.models import Product

        rows = list(
            Product.objects.filter(
                company=company,
                is_active=True,
                track_inventory=True,
                current_stock__lte=F("minimum_stock"),
            )
            .values(
                "id",
                "name",
                "sku",
                "category__name",
                "unit__short_name",
                "current_stock",
                "minimum_stock",
                "selling_price",
            )
            .annotate(shortage=ExpressionWrapper(F("minimum_stock") - F("current_stock"), output_field=DecimalField(max_digits=14, decimal_places=3)))
            .order_by("-shortage", "name")
        )

        return {
            "generated_at": timezone.now().isoformat(),
            "count": len(rows),
            "products": [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "sku": row["sku"],
                    "category": row["category__name"] or "Uncategorized",
                    "unit": row["unit__short_name"] or "",
                    "current_stock": money(row["current_stock"]),
                    "minimum_stock": money(row["minimum_stock"]),
                    "shortage": money(row["shortage"]),
                    "selling_price": money(row["selling_price"]),
                }
                for row in rows
            ],
        }


class OutstandingReportService:
    """Receivables and ageing analytics."""

    @staticmethod
    def get_outstanding_summary(company) -> dict[str, Any]:
        """Return customers with positive outstanding balances."""
        from customers.models import Customer

        customers_qs = Customer.objects.filter(company=company, current_balance__gt=Decimal("0.00"))
        summary = customers_qs.aggregate(
            total_outstanding=Coalesce(Sum("current_balance"), Decimal("0.00")),
            customer_count=Count("id"),
            over_credit_limit=Count("id", filter=Q(credit_limit__gt=0, current_balance__gt=F("credit_limit"))),
        )

        rows = list(
            customers_qs.values(
                "id",
                "name",
                "gstin",
                "mobile_primary",
                "credit_limit",
                "current_balance",
            )
            .annotate(
                over_limit=Case(
                    When(credit_limit__gt=0, current_balance__gt=F("credit_limit"), then=Value(True)),
                    default=Value(False),
                ),
                over_limit_by=Case(
                    When(
                        credit_limit__gt=0,
                        current_balance__gt=F("credit_limit"),
                        then=ExpressionWrapper(F("current_balance") - F("credit_limit"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                    ),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
            )
            .order_by("-current_balance", "name")
        )

        return {
            "generated_at": timezone.now().isoformat(),
            "summary": {
                "total_outstanding": money(summary.get("total_outstanding")),
                "customer_count": int(summary.get("customer_count") or 0),
                "over_credit_limit": int(summary.get("over_credit_limit") or 0),
            },
            "customers": [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "gstin": row["gstin"],
                    "mobile": row["mobile_primary"],
                    "credit_limit": money(row["credit_limit"]),
                    "current_balance": money(row["current_balance"]),
                    "over_limit": bool(row["over_limit"]),
                    "over_limit_by": money(row["over_limit_by"]),
                }
                for row in rows
            ],
        }

    @staticmethod
    def get_ageing_report(company) -> dict[str, Any]:
        """Return invoice ageing buckets and overdue invoice list.

        Future payments module should replace grand_total with true outstanding amount.
        """
        from invoices.models import Invoice

        today = timezone.localdate()
        issued = Invoice.objects.filter(
            company=company,
            status=Invoice.StatusChoices.ISSUED,
            due_date__isnull=False,
        )

        d_30 = today - timedelta(days=30)
        d_60 = today - timedelta(days=60)
        d_90 = today - timedelta(days=90)

        bucket_agg = issued.aggregate(
            not_due_count=Count("id", filter=Q(due_date__gte=today)),
            not_due_amount=Coalesce(Sum("grand_total", filter=Q(due_date__gte=today)), Decimal("0.00")),
            d0_30_count=Count("id", filter=Q(due_date__lt=today, due_date__gte=d_30)),
            d0_30_amount=Coalesce(Sum("grand_total", filter=Q(due_date__lt=today, due_date__gte=d_30)), Decimal("0.00")),
            d31_60_count=Count("id", filter=Q(due_date__lt=d_30, due_date__gte=d_60)),
            d31_60_amount=Coalesce(Sum("grand_total", filter=Q(due_date__lt=d_30, due_date__gte=d_60)), Decimal("0.00")),
            d61_90_count=Count("id", filter=Q(due_date__lt=d_60, due_date__gte=d_90)),
            d61_90_amount=Coalesce(Sum("grand_total", filter=Q(due_date__lt=d_60, due_date__gte=d_90)), Decimal("0.00")),
            d90_plus_count=Count("id", filter=Q(due_date__lt=d_90)),
            d90_plus_amount=Coalesce(Sum("grand_total", filter=Q(due_date__lt=d_90)), Decimal("0.00")),
        )

        overdue_rows = list(
            issued.filter(due_date__lt=today)
            .values("invoice_number", "customer_name", "invoice_date", "due_date", "grand_total")
            .order_by("due_date")
        )

        invoices = []
        for row in overdue_rows:
            days_overdue = (today - row["due_date"]).days
            if days_overdue <= 30:
                bucket = "days_0_30"
            elif days_overdue <= 60:
                bucket = "days_31_60"
            elif days_overdue <= 90:
                bucket = "days_61_90"
            else:
                bucket = "days_90_plus"
            invoices.append(
                {
                    "invoice_number": row["invoice_number"],
                    "customer_name": row["customer_name"],
                    "invoice_date": row["invoice_date"].isoformat() if row["invoice_date"] else "",
                    "due_date": row["due_date"].isoformat() if row["due_date"] else "",
                    "days_overdue": days_overdue,
                    "grand_total": money(row["grand_total"]),
                    "bucket": bucket,
                }
            )
        invoices.sort(key=lambda item: item["days_overdue"], reverse=True)

        return {
            "generated_at": timezone.now().isoformat(),
            "as_of_date": today.isoformat(),
            "buckets": {
                "not_due": {
                    "count": int(bucket_agg.get("not_due_count") or 0),
                    "amount": money(bucket_agg.get("not_due_amount")),
                },
                "days_0_30": {
                    "count": int(bucket_agg.get("d0_30_count") or 0),
                    "amount": money(bucket_agg.get("d0_30_amount")),
                },
                "days_31_60": {
                    "count": int(bucket_agg.get("d31_60_count") or 0),
                    "amount": money(bucket_agg.get("d31_60_amount")),
                },
                "days_61_90": {
                    "count": int(bucket_agg.get("d61_90_count") or 0),
                    "amount": money(bucket_agg.get("d61_90_amount")),
                },
                "days_90_plus": {
                    "count": int(bucket_agg.get("d90_plus_count") or 0),
                    "amount": money(bucket_agg.get("d90_plus_amount")),
                },
            },
            "invoices": invoices,
        }
