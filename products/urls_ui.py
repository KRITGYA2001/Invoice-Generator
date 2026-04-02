from django.urls import path

from products.views_ui import (
	BulkUploadView,
	CSVTemplateDownloadView,
	ProductCategoryCreateView,
	ProductCategoryDeleteView,
	ProductCategoryListView,
	ProductCreateView,
	ProductDeleteView,
	ProductDetailView,
	ProductListView,
	ProductUpdateView,
	StockAdjustView,
	StockHistoryView,
)

app_name = "products_ui"

urlpatterns = [
	path("", ProductListView.as_view(), name="product-list"),
	path("create/", ProductCreateView.as_view(), name="product-create"),
	path("<uuid:pk>/", ProductDetailView.as_view(), name="product-detail"),
	path("<uuid:pk>/edit/", ProductUpdateView.as_view(), name="product-edit"),
	path("<uuid:pk>/delete/", ProductDeleteView.as_view(), name="product-delete"),
	path("<uuid:pk>/stock/", StockAdjustView.as_view(), name="stock-adjust"),
	path("<uuid:pk>/stock/history/", StockHistoryView.as_view(), name="stock-history"),
	path("categories/", ProductCategoryListView.as_view(), name="category-list"),
	path("categories/create/", ProductCategoryCreateView.as_view(), name="category-create"),
	path("categories/<uuid:pk>/delete/", ProductCategoryDeleteView.as_view(), name="category-delete"),
	path("bulk-upload/", BulkUploadView.as_view(), name="bulk-upload"),
	path("bulk-upload/template/", CSVTemplateDownloadView.as_view(), name="csv-template"),
]
