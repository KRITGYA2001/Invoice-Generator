from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from PIL import Image
from rest_framework import serializers

from products.models import Product, ProductCategory, StockMovement, UnitOfMeasurement


def _validate_image_file(image_file) -> None:
    """
    Validate image file size and content type.
    Max 2MB, allowed types: jpeg, png, webp
    """
    if not image_file:
        return

    max_size = 2 * 1024 * 1024  # 2MB
    if image_file.size > max_size:
        raise serializers.ValidationError(f"Image size must not exceed 2MB. Current: {image_file.size / (1024 * 1024):.2f}MB")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image_file.content_type not in allowed_types:
        raise serializers.ValidationError(
            f"Unsupported image format. Allowed: JPEG, PNG, WebP. Got: {image_file.content_type}"
        )

    try:
        img = Image.open(image_file)
        img.verify()
    except Exception as e:
        raise serializers.ValidationError(f"Invalid image file: {str(e)}")


def _absolute_file_url(request, image_file) -> Optional[str]:
    """Build absolute URL for image file."""
    if not image_file:
        return None
    return request.build_absolute_uri(image_file.url)


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "name", "description", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class UnitOfMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasurement
        fields = ["id", "name", "short_name", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True, required=False)
    unit = serializers.CharField(source="unit.short_name", read_only=True, required=False)
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "hsn_code",
            "category",
            "unit",
            "selling_price",
            "gst_rate",
            "current_stock",
            "minimum_stock",
            "is_active",
            "is_low_stock",
            "is_service",
            "track_inventory",
        ]
        read_only_fields = fields

    def get_is_low_stock(self, obj: Product) -> bool:
        return obj.is_low_stock


class ProductDetailSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    unit = UnitOfMeasurementSerializer(read_only=True)
    unit_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    image = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    stock_value = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "sku",
            "hsn_code",
            "category",
            "category_id",
            "unit",
            "unit_id",
            "selling_price",
            "purchase_price",
            "gst_rate",
            "cess_rate",
            "is_service",
            "is_active",
            "track_inventory",
            "current_stock",
            "minimum_stock",
            "maximum_stock",
            "opening_stock",
            "image",
            "is_low_stock",
            "stock_value",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "current_stock",
            "created_at",
            "updated_at",
        ]

    def validate_gst_rate(self, value: Decimal) -> Decimal:
        allowed_rates = [Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")]
        if value not in allowed_rates:
            raise serializers.ValidationError(f"GST rate must be one of {allowed_rates}")
        return value

    def validate_hsn_code(self, value: str) -> str:
        if not value or not value.isdigit() or not (4 <= len(value) <= 8):
            raise serializers.ValidationError(
                "HSN/SAC code must be 4-8 digit numeric string"
            )
        return value

    def validate_image(self, value) -> Any:
        if value:
            _validate_image_file(value)
        return value

    def get_image(self, obj: Product) -> str | None:
        if not obj.image:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def get_is_low_stock(self, obj: Product) -> bool:
        return obj.is_low_stock

    def get_stock_value(self, obj: Product) -> float:
        return float(obj.stock_value)

    def create(self, validated_data: dict) -> Product:
        request = self.context.get("request")
        if request is None:
            raise serializers.ValidationError("Request context is required")

        company = getattr(request.user, "company_profile", None)
        if not company:
            raise serializers.ValidationError("User does not have a company profile")

        category_id = validated_data.pop("category_id", None)
        unit_id = validated_data.pop("unit_id", None)

        if category_id:
            try:
                category = ProductCategory.objects.get(id=category_id, company=company)
                validated_data["category"] = category
            except ProductCategory.DoesNotExist:
                raise serializers.ValidationError("Category not found")

        if unit_id:
            try:
                unit = UnitOfMeasurement.objects.get(id=unit_id, company=company)
                validated_data["unit"] = unit
            except UnitOfMeasurement.DoesNotExist:
                raise serializers.ValidationError("Unit not found")

        validated_data["company"] = company
        product = Product.objects.create(**validated_data)

        if product.opening_stock > 0:
            from products.services import StockService
            StockService.set_opening_stock(product, product.opening_stock, created_by=request.user)

        return product

    def update(self, instance: Product, validated_data: dict) -> Product:
        request = self.context.get("request")
        if request is None:
            raise serializers.ValidationError("Request context is required")

        company = request.user.company_profile

        category_id = validated_data.pop("category_id", None)
        unit_id = validated_data.pop("unit_id", None)

        if category_id is not None:
            try:
                category = ProductCategory.objects.get(id=category_id, company=company)
                instance.category = category
            except ProductCategory.DoesNotExist:
                raise serializers.ValidationError("Category not found")

        if unit_id is not None:
            try:
                unit = UnitOfMeasurement.objects.get(id=unit_id, company=company)
                instance.unit = unit
            except UnitOfMeasurement.DoesNotExist:
                raise serializers.ValidationError("Unit not found")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class StockMovementSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product.name", read_only=True)
    created_by = serializers.CharField(source="created_by.email", read_only=True, required=False)
    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product",
            "movement_type",
            "movement_type_display",
            "quantity",
            "stock_before",
            "stock_after",
            "reference_type",
            "reference_id",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class StockAdjustSerializer(serializers.Serializer):
    MOVEMENT_TYPE_CHOICES = [
        ("IN", "Stock In"),
        ("ADJUST", "Adjustment"),
        ("RETURN", "Return"),
    ]

    movement_type = serializers.ChoiceField(choices=MOVEMENT_TYPE_CHOICES)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_quantity(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value


class BulkProductUploadSerializer(serializers.Serializer):
    products = serializers.ListField(child=serializers.DictField(), max_length=200)
    update_existing = serializers.BooleanField(default=False, required=False)

    def validate_products(self, value: list) -> list:
        if not value:
            raise serializers.ValidationError("Products list cannot be empty")

        names_seen = set()
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f"Item {idx} is not a dictionary")

            required_fields = ["name", "hsn_code", "selling_price", "gst_rate"]
            for field in required_fields:
                if field not in item:
                    raise serializers.ValidationError(f"Item {idx} missing required field: {field}")

            name = item.get("name")
            if name in names_seen:
                raise serializers.ValidationError(f"Duplicate product name in batch: {name}")
            names_seen.add(name)

        return value
