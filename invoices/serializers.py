from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from customers.models import Customer
from invoices.models import Invoice, InvoiceLineItem


class InvoiceLineItemReadSerializer(serializers.ModelSerializer):
    """Read-only serializer for invoice line items."""

    class Meta:
        model = InvoiceLineItem
        fields = [
            "id",
            "invoice",
            "product",
            "sr_no",
            "product_name",
            "hsn_code",
            "description",
            "quantity",
            "unit",
            "unit_price",
            "discount_percent",
            "discount_amount",
            "taxable_amount",
            "gst_rate",
            "cgst_rate",
            "sgst_rate",
            "igst_rate",
            "cess_rate",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "cess_amount",
            "total_tax",
            "line_total",
        ]
        read_only_fields = fields


class InvoiceLineItemWriteSerializer(serializers.Serializer):
    """Input serializer for creating invoice line items."""

    product = serializers.UUIDField(required=False, allow_null=True)
    product_name = serializers.CharField(required=False, allow_blank=True)
    hsn_code = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    cess_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)

    def validate_quantity(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value

    def validate_unit_price(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative")
        return value

    def validate_discount_percent(self, value: Decimal) -> Decimal:
        if value < 0 or value > 100:
            raise serializers.ValidationError("Discount percent must be between 0 and 100")
        return value

    def validate_gst_rate(self, value: Decimal) -> Decimal:
        allowed_rates = {Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")}
        if value not in allowed_rates:
            raise serializers.ValidationError("GST rate must be one of 0, 5, 12, 18, 28")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        product = attrs.get("product")
        product_name = attrs.get("product_name")
        hsn_code = attrs.get("hsn_code")
        if not product and not product_name:
            raise serializers.ValidationError({"product_name": "Product name is required when product is not provided"})
        if not product and not hsn_code:
            raise serializers.ValidationError({"hsn_code": "HSN/SAC code is required when product is not provided"})
        return attrs


class InvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for invoice lists."""

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "invoice_date",
            "due_date",
            "customer_name",
            "customer_gstin",
            "status",
            "subtotal",
            "total_tax",
            "grand_total",
            "is_interstate",
            "created_at",
        ]
        read_only_fields = fields


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """Full invoice serializer with nested line items."""

    line_items = InvoiceLineItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "company",
            "customer",
            "invoice_number",
            "invoice_date",
            "due_date",
            "financial_year",
            "status",
            "place_of_supply",
            "place_of_supply_code",
            "reverse_charge",
            "is_interstate",
            "transport_mode",
            "vehicle_number",
            "station",
            "eway_bill_number",
            "po_number",
            "po_date",
            "customer_name",
            "customer_address",
            "customer_gstin",
            "customer_state",
            "customer_state_code",
            "customer_mobile",
            "customer_email",
            "shipping_name",
            "shipping_address",
            "shipping_state",
            "shipping_state_code",
            "subtotal",
            "total_cgst",
            "total_sgst",
            "total_igst",
            "total_cess",
            "total_tax",
            "round_off",
            "grand_total",
            "amount_in_words",
            "bank_name",
            "bank_account_number",
            "bank_ifsc",
            "bank_branch",
            "bank_upi_id",
            "terms_and_conditions",
            "notes",
            "irn",
            "irn_generated_at",
            "created_by",
            "updated_by",
            "issued_at",
            "cancelled_at",
            "cancellation_reason",
            "created_at",
            "updated_at",
            "line_items",
        ]
        read_only_fields = fields


class InvoiceCreateSerializer(serializers.Serializer):
    """Input serializer for creating invoices."""

    customer = serializers.UUIDField(required=False, allow_null=True)
    invoice_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    place_of_supply = serializers.CharField()
    place_of_supply_code = serializers.CharField(max_length=5)
    reverse_charge = serializers.BooleanField(default=False)
    transport_mode = serializers.CharField(required=False, allow_blank=True)
    vehicle_number = serializers.CharField(required=False, allow_blank=True)
    station = serializers.CharField(required=False, allow_blank=True)
    eway_bill_number = serializers.CharField(required=False, allow_blank=True)
    po_number = serializers.CharField(required=False, allow_blank=True)
    po_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    terms_and_conditions = serializers.CharField(required=False, allow_blank=True)
    line_items = InvoiceLineItemWriteSerializer(many=True)
    apply_round_off = serializers.BooleanField(default=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    customer_gstin = serializers.CharField(required=False, allow_blank=True)
    customer_state = serializers.CharField(required=False, allow_blank=True)
    customer_state_code = serializers.CharField(required=False, allow_blank=True)
    customer_mobile = serializers.CharField(required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_address = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("line_items"):
            raise serializers.ValidationError({"line_items": "At least one line item is required"})
        customer = attrs.get("customer")
        if customer is None and not attrs.get("customer_name"):
            raise serializers.ValidationError({"customer_name": "Customer name is required when customer is not provided"})
        return attrs


class InvoiceUpdateSerializer(InvoiceCreateSerializer):
    """Input serializer for replacing a draft invoice."""

    pass


class InvoiceCancelSerializer(serializers.Serializer):
    """Input serializer for invoice cancellation."""

    cancellation_reason = serializers.CharField(min_length=10)


class InvoiceSummarySerializer(serializers.Serializer):
    """Serializer for invoice dashboard summary metrics."""

    total_invoices = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_tax_collected = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_draft = serializers.IntegerField()
    total_cancelled = serializers.IntegerField()
    monthly_breakdown = serializers.ListField()
