from __future__ import annotations

from django.urls import path

from products.views import (
    BulkProductUploadView,
    ProductCategoryDetailView,
    ProductCategoryListCreateView,
    ProductDetailView,
    ProductListCreateView,
    ProductStockHistoryView,
    ProductStockView,
    StockSummaryView,
    UnitDetailView,
    UnitListCreateView,
)

urlpatterns = [
    path("categories/", ProductCategoryListCreateView.as_view(), name="category-list"),
    path("categories/<uuid:pk>/", ProductCategoryDetailView.as_view(), name="category-detail"),
    path("units/", UnitListCreateView.as_view(), name="unit-list"),
    path("units/<uuid:pk>/", UnitDetailView.as_view(), name="unit-detail"),
    path("", ProductListCreateView.as_view(), name="product-list"),
    path("<uuid:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("<uuid:pk>/stock/", ProductStockView.as_view(), name="product-stock"),
    path("<uuid:pk>/stock/history/", ProductStockHistoryView.as_view(), name="product-stock-history"),
    path("stock/summary/", StockSummaryView.as_view(), name="stock-summary"),
    path("bulk-upload/", BulkProductUploadView.as_view(), name="bulk-upload"),
]
