from __future__ import annotations

from django_filters import (
    BooleanFilter,
    CharFilter,
    ChoiceFilter,
    DateFilter,
    FilterSet,
    NumberFilter,
    UUIDFilter,
)

from django.db import models
from products.models import Product, StockMovement


class ProductFilter(FilterSet):
    name = CharFilter(field_name="name", lookup_expr="icontains")
    sku = CharFilter(field_name="sku", lookup_expr="icontains")
    hsn_code = CharFilter(field_name="hsn_code", lookup_expr="icontains")
    category = UUIDFilter(field_name="category__id")
    gst_rate = NumberFilter(field_name="gst_rate", lookup_expr="exact")
    is_active = BooleanFilter(field_name="is_active")
    is_service = BooleanFilter(field_name="is_service")
    is_low_stock = BooleanFilter(method="filter_is_low_stock")
    min_price = NumberFilter(field_name="selling_price", lookup_expr="gte")
    max_price = NumberFilter(field_name="selling_price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "hsn_code",
            "category",
            "gst_rate",
            "is_active",
            "is_service",
            "is_low_stock",
            "min_price",
            "max_price",
        ]

    @staticmethod
    def filter_is_low_stock(queryset, name, value):
        if value:
            return queryset.filter(track_inventory=True).filter(
                current_stock__lte=models.F("minimum_stock")
            )
        return queryset


class StockMovementFilter(FilterSet):
    product = UUIDFilter(field_name="product__id")
    movement_type = ChoiceFilter(field_name="movement_type", choices=StockMovement.MOVEMENT_TYPE_CHOICES)
    date_from = DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = DateFilter(field_name="created_at", lookup_expr="lte")
    reference_type = CharFilter(field_name="reference_type", lookup_expr="exact")

    class Meta:
        model = StockMovement
        fields = ["product", "movement_type", "date_from", "date_to", "reference_type"]
