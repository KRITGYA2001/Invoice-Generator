from __future__ import annotations

import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from core.views import OnboardingCheckMixin
from reports.services import (
    DashboardService,
    GSTReportService,
    InventoryReportService,
    SalesReportService,
    OutstandingReportService,
)


DATE_RANGE_OPTIONS = [
    ("fy", "Financial year"),
    ("month", "This month"),
    ("30d", "Last 30 days"),
    ("90d", "Last 90 days"),
    ("quarter", "This quarter"),
    ("ytd", "Year to date"),
    ("custom", "Custom"),
]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _money_to_number(value: str | int | float | None) -> float:
    try:
        return float(str(value or 0).replace(",", ""))
    except ValueError:
        return 0.0


def _financial_year_bounds() -> tuple[str, date, date]:
    financial_year = DashboardService.get_current_financial_year()
    start_date, end_date = DashboardService._financial_year_bounds(financial_year)
    return financial_year, start_date, end_date


def _quarter_bounds(today: date) -> tuple[date, date]:
    quarter_start_month = ((today.month - 1) // 3) * 3 + 1
    start_date = date(today.year, quarter_start_month, 1)
    if quarter_start_month == 10:
        end_date = date(today.year, 12, 31)
    else:
        next_quarter_month = quarter_start_month + 3
        end_date = date(today.year if next_quarter_month <= 12 else today.year + 1, next_quarter_month if next_quarter_month <= 12 else 1, 1) - timedelta(days=1)
    return start_date, end_date


def resolve_date_range(request: HttpRequest, default_range: str = "fy") -> dict[str, object]:
    today = date.today()
    selected_range = request.GET.get("range", default_range)
    financial_year, fy_start, fy_end = _financial_year_bounds()
    date_from = fy_start
    date_to = fy_end
    if selected_range == "30d":
        date_from = today - timedelta(days=29)
        date_to = today
    elif selected_range == "90d":
        date_from = today - timedelta(days=89)
        date_to = today
    elif selected_range == "month":
        date_from = today.replace(day=1)
        date_to = today
    elif selected_range == "quarter":
        date_from, date_to = _quarter_bounds(today)
    elif selected_range == "ytd":
        date_from = date(today.year, 1, 1)
        date_to = today
    elif selected_range == "custom":
        custom_from = _parse_date(request.GET.get("date_from"))
        custom_to = _parse_date(request.GET.get("date_to"))
        if custom_from and custom_to and custom_from <= custom_to:
            date_from, date_to = custom_from, custom_to
        else:
            selected_range = default_range
    if selected_range == "fy":
        year_value = request.GET.get("financial_year")
        if year_value:
            try:
                date_from, date_to = DashboardService._financial_year_bounds(year_value)
                financial_year = year_value
            except Exception:
                pass
    return {
        "selected_range": selected_range,
        "financial_year": financial_year,
        "date_from": date_from,
        "date_to": date_to,
        "date_from_str": date_from.isoformat(),
        "date_to_str": date_to.isoformat(),
        "period_label": f"{date_from.strftime('%d %b %Y')} - {date_to.strftime('%d %b %Y')}",
    }


class ReportBaseView(LoginRequiredMixin, OnboardingCheckMixin, View):
    login_url = "/accounts/login/"
    template_name = ""
    page_title = "Reports"
    default_range = "fy"

    def build_context(self, request: HttpRequest, **kwargs):
        period = resolve_date_range(request, self.default_range)
        context = {
            "company": request.user.company_profile,
            "page_title": self.page_title,
            "date_range_options": DATE_RANGE_OPTIONS,
            **period,
            **kwargs,
        }
        return context

    def render_report(self, request: HttpRequest, context: dict[str, object]) -> HttpResponse:
        return render(request, self.template_name, context)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class GSTReportView(ReportBaseView):
    template_name = "reports_ui/gst_report.html"
    page_title = "GST Reports"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, "fy")
        summary = GSTReportService.get_gst_summary(request.user.company_profile, period["date_from"], period["date_to"])
        context = self.build_context(
            request,
            gst_summary=summary,
            gst_rate_labels=json.dumps([row["gst_rate"] for row in summary["rate_wise_summary"]]),
            gst_rate_tax=json.dumps([_money_to_number(row["total_tax"]) for row in summary["rate_wise_summary"]]),
            gst_rate_taxable=json.dumps([_money_to_number(row["taxable_amount"]) for row in summary["rate_wise_summary"]]),
            gst_split_values=json.dumps([
                _money_to_number(summary["interstate_summary"]["taxable_amount"]),
                _money_to_number(summary["intrastate_summary"]["taxable_amount"]),
            ]),
        )
        return self.render_report(request, context)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class GSTGSTR1View(ReportBaseView):
    template_name = "reports_ui/gstr1_report.html"
    page_title = "GSTR-1 Summary"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, "fy")
        summary = GSTReportService.get_gstr1_invoice_list(request.user.company_profile, period["date_from"], period["date_to"])
        context = self.build_context(request, gstr1_report=summary)
        return self.render_report(request, context)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class GSTHSNView(ReportBaseView):
    template_name = "reports_ui/hsn_report.html"
    page_title = "HSN Summary"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, "fy")
        summary = GSTReportService.get_hsn_summary(request.user.company_profile, period["date_from"], period["date_to"])
        context = self.build_context(request, hsn_report=summary)
        return self.render_report(request, context)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class SalesReportView(ReportBaseView):
    template_name = "reports_ui/sales_report.html"
    page_title = "Sales Reports"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, "fy")
        company = request.user.company_profile
        by_customer = SalesReportService.get_sales_by_customer(company, period["date_from"], period["date_to"])
        by_product = SalesReportService.get_sales_by_product(company, period["date_from"], period["date_to"])
        by_category = SalesReportService.get_sales_by_category(company, period["date_from"], period["date_to"])
        daily = SalesReportService.get_daily_sales(company, period["date_from"], period["date_to"])
        context = self.build_context(
            request,
            sales_by_customer=by_customer,
            sales_by_product=by_product,
            sales_by_category=by_category,
            daily_sales=daily,
            sales_customer_labels=json.dumps([row["customer_name"] for row in by_customer["customers"]]),
            sales_customer_values=json.dumps([_money_to_number(row["grand_total"]) for row in by_customer["customers"]]),
            sales_product_labels=json.dumps([row["product_name"] for row in by_product["products"]]),
            sales_product_values=json.dumps([_money_to_number(row["line_total"]) for row in by_product["products"]]),
            daily_labels=json.dumps([row["date"] for row in daily["daily"]]),
            daily_revenue=json.dumps([_money_to_number(row["revenue"]) for row in daily["daily"]]),
        )
        return self.render_report(request, context)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class SalesByCustomerView(ReportBaseView):
    template_name = "reports_ui/sales_by_customer.html"
    page_title = "Sales by Customer"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, "fy")
        report = SalesReportService.get_sales_by_customer(request.user.company_profile, period["date_from"], period["date_to"], limit=25)
        return self.render_report(request, self.build_context(request, sales_by_customer=report))


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class SalesByProductView(ReportBaseView):
    template_name = "reports_ui/sales_by_product.html"
    page_title = "Sales by Product"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, "fy")
        report = SalesReportService.get_sales_by_product(request.user.company_profile, period["date_from"], period["date_to"], limit=25)
        return self.render_report(request, self.build_context(request, sales_by_product=report))


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class DailySalesView(ReportBaseView):
    template_name = "reports_ui/daily_sales.html"
    page_title = "Daily Sales"
    default_range = "30d"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, self.default_range)
        report = SalesReportService.get_daily_sales(request.user.company_profile, period["date_from"], period["date_to"])
        context = self.build_context(
            request,
            daily_sales=report,
            daily_labels=json.dumps([row["date"] for row in report["daily"]]),
            daily_revenue=json.dumps([_money_to_number(row["revenue"]) for row in report["daily"]]),
        )
        return self.render_report(request, context)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class InventoryReportView(ReportBaseView):
    template_name = "reports_ui/inventory_report.html"
    page_title = "Inventory Reports"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        valuation = InventoryReportService.get_stock_valuation(company)
        low_stock = InventoryReportService.get_low_stock_report(company)
        context = self.build_context(
            request,
            inventory_valuation=valuation,
            low_stock_report=low_stock,
            inventory_category_labels=json.dumps([row["category_name"] for row in valuation["by_category"]]),
            inventory_category_values=json.dumps([_money_to_number(row["stock_value"]) for row in valuation["by_category"]]),
        )
        return self.render_report(request, context)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class StockMovementView(ReportBaseView):
    template_name = "reports_ui/stock_movement.html"
    page_title = "Stock Movement"

    def get(self, request: HttpRequest) -> HttpResponse:
        period = resolve_date_range(request, "90d")
        report = InventoryReportService.get_stock_movement_report(request.user.company_profile, period["date_from"], period["date_to"])
        return self.render_report(request, self.build_context(request, stock_movement=report))


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class LowStockReportView(ReportBaseView):
    template_name = "reports_ui/low_stock_report.html"
    page_title = "Low Stock Report"

    def get(self, request: HttpRequest) -> HttpResponse:
        report = InventoryReportService.get_low_stock_report(request.user.company_profile)
        return self.render_report(request, self.build_context(request, low_stock_report=report))


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class OutstandingReportView(ReportBaseView):
    template_name = "reports_ui/outstanding_report.html"
    page_title = "Outstanding Reports"

    def get(self, request: HttpRequest) -> HttpResponse:
        report = OutstandingReportService.get_outstanding_summary(request.user.company_profile)
        return self.render_report(request, self.build_context(request, outstanding_report=report))


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class AgeingReportView(ReportBaseView):
    template_name = "reports_ui/ageing_report.html"
    page_title = "Ageing Report"

    def get(self, request: HttpRequest) -> HttpResponse:
        report = OutstandingReportService.get_ageing_report(request.user.company_profile)
        context = self.build_context(
            request,
            ageing_report=report,
            ageing_labels=json.dumps(["Current", "0-30 days", "31-60 days", "61-90 days", "90+ days"]),
            ageing_values=json.dumps([
                _money_to_number(report["buckets"]["not_due"]["amount"]),
                _money_to_number(report["buckets"]["days_0_30"]["amount"]),
                _money_to_number(report["buckets"]["days_31_60"]["amount"]),
                _money_to_number(report["buckets"]["days_61_90"]["amount"]),
                _money_to_number(report["buckets"]["days_90_plus"]["amount"]),
            ]),
        )
        return self.render_report(request, context)
