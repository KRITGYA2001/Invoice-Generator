from django.urls import path

from reports.views import (
    AgeingReportView,
    DashboardOverviewView,
    DailySalesView,
    GSTR1InvoiceListView,
    GSTSummaryView,
    HSNSummaryView,
    LowStockReportView,
    MonthlyTrendView,
    OutstandingSummaryView,
    SalesByCategoryView,
    SalesByCustomerView,
    SalesByProductView,
    StockMovementReportView,
    StockValuationView,
)


urlpatterns = [
    path("dashboard/", DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("dashboard/trend/", MonthlyTrendView.as_view(), name="dashboard-trend"),
    path("gst/summary/", GSTSummaryView.as_view(), name="gst-summary"),
    path("gst/gstr1/", GSTR1InvoiceListView.as_view(), name="gstr1-list"),
    path("gst/hsn-summary/", HSNSummaryView.as_view(), name="hsn-summary"),
    path("sales/by-customer/", SalesByCustomerView.as_view(), name="sales-by-customer"),
    path("sales/by-product/", SalesByProductView.as_view(), name="sales-by-product"),
    path("sales/by-category/", SalesByCategoryView.as_view(), name="sales-by-category"),
    path("sales/daily/", DailySalesView.as_view(), name="sales-daily"),
    path("inventory/valuation/", StockValuationView.as_view(), name="stock-valuation"),
    path("inventory/movements/", StockMovementReportView.as_view(), name="stock-movements"),
    path("inventory/low-stock/", LowStockReportView.as_view(), name="low-stock"),
    path("outstanding/", OutstandingSummaryView.as_view(), name="outstanding-summary"),
    path("outstanding/ageing/", AgeingReportView.as_view(), name="ageing-report"),
]
