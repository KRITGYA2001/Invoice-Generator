from __future__ import annotations

from django.contrib import admin

from products.models import Product, ProductCategory, StockMovement, UnitOfMeasurement


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    """Admin interface for ProductCategory model."""

    list_display = ("name", "company", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active", "created_at")
    readonly_fields = ("id", "created_at", "updated_at")
    list_per_page = 50


@admin.register(UnitOfMeasurement)
class UnitOfMeasurementAdmin(admin.ModelAdmin):
    """Admin interface for UnitOfMeasurement model."""

    list_display = ("name", "short_name", "company", "is_active", "created_at")
    search_fields = ("name", "short_name")
    list_filter = ("is_active", "created_at")
    readonly_fields = ("id", "created_at")
    list_per_page = 50


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin interface for Product model."""

    list_display = (
        "name",
        "sku",
        "hsn_code",
        "category",
        "unit",
        "selling_price",
        "gst_rate",
        "current_stock",
        "is_active",
        "is_low_stock",
    )
    search_fields = ("name", "sku", "hsn_code")
    list_filter = ("category", "gst_rate", "is_active", "is_service", "track_inventory", "created_at")
    readonly_fields = ("id", "current_stock", "created_at", "updated_at")
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "company",
                    "name",
                    "description",
                    "category",
                    "sku",
                )
            },
        ),
        (
            "Classification",
            {
                "fields": (
                    "hsn_code",
                    "is_service",
                    "unit",
                )
            },
        ),
        (
            "Pricing & Tax",
            {
                "fields": (
                    "selling_price",
                    "purchase_price",
                    "gst_rate",
                    "cess_rate",
                )
            },
        ),
        (
            "Inventory",
            {
                "fields": (
                    "track_inventory",
                    "current_stock",
                    "minimum_stock",
                    "maximum_stock",
                    "opening_stock",
                )
            },
        ),
        (
            "Status",
            {
                "fields": ("is_active",)
            },
        ),
        (
            "Media",
            {
                "fields": ("image",)
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    list_per_page = 50


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Admin interface for StockMovement model."""

    list_display = (
        "product",
        "movement_type",
        "quantity",
        "stock_before",
        "stock_after",
        "reference_type",
        "created_by",
        "created_at",
    )
    search_fields = ("product__name", "reference_type")
    list_filter = ("movement_type", "reference_type", "created_at")
    readonly_fields = (
        "id",
        "product",
        "movement_type",
        "quantity",
        "stock_before",
        "stock_after",
        "reference_type",
        "reference_id",
        "notes",
        "created_by",
        "created_at",
    )
    list_per_page = 50

    def has_add_permission(self, request):
        """Prevent adding movements from admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing movements."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting movements."""
        return False
