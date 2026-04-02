from django.urls import path

from .views_ui import (
	AgeingReportView,
	DailySalesView,
	GSTGSTR1View,
	GSTHSNView,
	GSTReportView,
	InventoryReportView,
	LowStockReportView,
	OutstandingReportView,
	SalesByCustomerView,
	SalesByProductView,
	SalesReportView,
	StockMovementView,
)

app_name = "reports_ui"

urlpatterns = [
	path("gst/", GSTReportView.as_view(), name="gst-report"),
	path("gst/gstr1/", GSTGSTR1View.as_view(), name="gst-gstr1"),
	path("gst/hsn/", GSTHSNView.as_view(), name="gst-hsn"),
	path("sales/", SalesReportView.as_view(), name="sales-report"),
	path("sales/customers/", SalesByCustomerView.as_view(), name="sales-by-customer"),
	path("sales/products/", SalesByProductView.as_view(), name="sales-by-product"),
	path("sales/daily/", DailySalesView.as_view(), name="sales-daily"),
	path("inventory/", InventoryReportView.as_view(), name="inventory-report"),
	path("inventory/movement/", StockMovementView.as_view(), name="stock-movement"),
	path("inventory/low-stock/", LowStockReportView.as_view(), name="low-stock"),
	path("outstanding/", OutstandingReportView.as_view(), name="outstanding-report"),
	path("outstanding/ageing/", AgeingReportView.as_view(), name="outstanding-ageing"),
]
