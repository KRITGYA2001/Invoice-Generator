from __future__ import annotations

from datetime import timedelta
from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from company.permissions import HasCompanyProfile
from reports.serializers import (
	DateRangeSerializer,
	FinancialYearSerializer,
	SalesReportQuerySerializer,
	StockMovementQuerySerializer,
)
from reports.services import (
	DashboardService,
	GSTReportService,
	InventoryReportService,
	OutstandingReportService,
	SalesReportService,
)


def success_response(message: str, data: Any, status_code: int = status.HTTP_200_OK) -> Response:
	"""Return a consistent success payload."""
	return Response({"success": True, "message": message, "data": data}, status=status_code)


def error_response(message: str, errors: Any, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
	"""Return a consistent error payload."""
	return Response({"success": False, "message": message, "errors": errors}, status=status_code)


class BaseReportView(APIView):
	"""Base class applying JWT authentication and company scoping permissions."""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]


class DashboardOverviewView(BaseReportView):
	"""Return dashboard overview metrics."""

	def get(self, request: Request) -> Response:
		serializer = FinancialYearSerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)
		data = DashboardService.get_overview(request.user.company_profile, serializer.validated_data.get("financial_year"))
		return success_response("Dashboard overview retrieved successfully", data)


class MonthlyTrendView(BaseReportView):
	"""Return monthly trend metrics for a financial year."""

	def get(self, request: Request) -> Response:
		serializer = FinancialYearSerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)
		data = DashboardService.get_monthly_trend(request.user.company_profile, serializer.validated_data.get("financial_year"))
		return success_response("Monthly trend retrieved successfully", data)


class GSTSummaryView(BaseReportView):
	"""Return GST summary for a date range."""

	def get(self, request: Request) -> Response:
		serializer = DateRangeSerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)
		data = GSTReportService.get_gst_summary(request.user.company_profile, serializer.validated_data["date_from"], serializer.validated_data["date_to"])
		return success_response("GST summary retrieved successfully", data)


class GSTR1InvoiceListView(BaseReportView):
	"""Return paginated GSTR-1 invoice list for a date range."""

	def get(self, request: Request) -> Response:
		serializer = DateRangeSerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)

		page = max(int(request.query_params.get("page", 1)), 1)
		page_size = int(request.query_params.get("page_size", 100))
		page_size = min(max(page_size, 1), 500)

		raw_data = GSTReportService.get_gstr1_invoice_list(
			request.user.company_profile,
			serializer.validated_data["date_from"],
			serializer.validated_data["date_to"],
		)
		invoices = raw_data["invoices"]
		total_count = len(invoices)
		start = (page - 1) * page_size
		end = start + page_size
		raw_data["invoices"] = invoices[start:end]
		raw_data["total_count"] = total_count
		raw_data["pagination"] = {
			"page": page,
			"page_size": page_size,
			"total": total_count,
			"total_pages": (total_count + page_size - 1) // page_size,
		}
		return success_response("GSTR-1 invoice list retrieved successfully", raw_data)


class HSNSummaryView(BaseReportView):
	"""Return HSN summary for a date range."""

	def get(self, request: Request) -> Response:
		serializer = DateRangeSerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)
		data = GSTReportService.get_hsn_summary(request.user.company_profile, serializer.validated_data["date_from"], serializer.validated_data["date_to"])
		return success_response("HSN summary retrieved successfully", data)


class SalesByCustomerView(BaseReportView):
	"""Return top customers by revenue."""

	def get(self, request: Request) -> Response:
		serializer = SalesReportQuerySerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)
		data = SalesReportService.get_sales_by_customer(
			request.user.company_profile,
			serializer.validated_data["date_from"],
			serializer.validated_data["date_to"],
			serializer.validated_data["limit"],
		)
		return success_response("Sales by customer retrieved successfully", data)


class SalesByProductView(BaseReportView):
	"""Return top products by revenue."""

	def get(self, request: Request) -> Response:
		serializer = SalesReportQuerySerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)
		data = SalesReportService.get_sales_by_product(
			request.user.company_profile,
			serializer.validated_data["date_from"],
			serializer.validated_data["date_to"],
			serializer.validated_data["limit"],
		)
		return success_response("Sales by product retrieved successfully", data)


class SalesByCategoryView(BaseReportView):
	"""Return sales grouped by category."""

	def get(self, request: Request) -> Response:
		serializer = DateRangeSerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)
		data = SalesReportService.get_sales_by_category(
			request.user.company_profile,
			serializer.validated_data["date_from"],
			serializer.validated_data["date_to"],
		)
		return success_response("Sales by category retrieved successfully", data)


class DailySalesView(BaseReportView):
	"""Return date-wise sales data with zero-filled missing days."""

	def get(self, request: Request) -> Response:
		serializer = DateRangeSerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)

		date_from = serializer.validated_data["date_from"]
		date_to = serializer.validated_data["date_to"]
		if (date_to - date_from) > timedelta(days=90):
			return error_response("Validation failed", {"date_to": "Daily report range cannot exceed 90 days"})

		data = SalesReportService.get_daily_sales(request.user.company_profile, date_from, date_to)
		return success_response("Daily sales retrieved successfully", data)


class StockValuationView(BaseReportView):
	"""Return inventory valuation report."""

	def get(self, request: Request) -> Response:
		data = InventoryReportService.get_stock_valuation(request.user.company_profile)
		return success_response("Stock valuation retrieved successfully", data)


class StockMovementReportView(BaseReportView):
	"""Return stock movement report for a date range."""

	def get(self, request: Request) -> Response:
		serializer = StockMovementQuerySerializer(data=request.query_params)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors)

		data = InventoryReportService.get_stock_movement_report(
			request.user.company_profile,
			serializer.validated_data["date_from"],
			serializer.validated_data["date_to"],
			serializer.validated_data.get("product_id"),
		)
		return success_response("Stock movement report retrieved successfully", data)


class LowStockReportView(BaseReportView):
	"""Return low stock products."""

	def get(self, request: Request) -> Response:
		data = InventoryReportService.get_low_stock_report(request.user.company_profile)
		return success_response("Low stock report retrieved successfully", data)


class OutstandingSummaryView(BaseReportView):
	"""Return outstanding customer balances."""

	def get(self, request: Request) -> Response:
		data = OutstandingReportService.get_outstanding_summary(request.user.company_profile)
		return success_response("Outstanding summary retrieved successfully", data)


class AgeingReportView(BaseReportView):
	"""Return ageing buckets and overdue invoice list."""

	def get(self, request: Request) -> Response:
		data = OutstandingReportService.get_ageing_report(request.user.company_profile)
		return success_response("Ageing report retrieved successfully", data)
