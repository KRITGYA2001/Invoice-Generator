from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from customers.models import Customer, CustomerContact, CustomerNote, gstin_validator, pan_validator, state_code_validator


class CustomerContactSerializer(serializers.ModelSerializer):
    """Serializer for party contacts."""

    class Meta:
        model = CustomerContact
        fields = ["id", "name", "designation", "mobile", "email", "is_primary", "created_at"]
        read_only_fields = ["id", "created_at"]


class CustomerNoteSerializer(serializers.ModelSerializer):
    """Serializer for internal party notes."""

    created_by = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = CustomerNote
        fields = ["id", "note", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]


class CustomerListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for party lists."""

    is_over_credit_limit = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "display_name",
            "party_type",
            "gstin",
            "mobile_primary",
            "email",
            "billing_city",
            "billing_state",
            "billing_state_code",
            "current_balance",
            "credit_limit",
            "is_active",
            "is_over_credit_limit",
            "created_at",
        ]
        read_only_fields = fields

    def get_is_over_credit_limit(self, obj: Customer) -> bool:
        return obj.is_over_credit_limit


class CustomerDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for party create/retrieve/update."""

    contacts = CustomerContactSerializer(many=True, read_only=True)
    full_billing_address = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "company",
            "party_type",
            "name",
            "display_name",
            "gstin",
            "pan",
            "mobile_primary",
            "mobile_secondary",
            "email",
            "website",
            "billing_address_line1",
            "billing_address_line2",
            "billing_city",
            "billing_state",
            "billing_state_code",
            "billing_pincode",
            "billing_country",
            "credit_limit",
            "payment_terms_days",
            "opening_balance",
            "current_balance",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
            "contacts",
            "full_billing_address",
        ]
        read_only_fields = ["id", "company", "current_balance", "created_at", "updated_at", "contacts"]

    def validate_gstin(self, value: str) -> str:
        if value:
            gstin_validator(value)
        return value

    def validate_pan(self, value: str) -> str:
        if value:
            pan_validator(value)
        return value

    def validate_billing_state_code(self, value: str) -> str:
        if value:
            state_code_validator(value)
        return value

    def get_full_billing_address(self, obj: Customer) -> str:
        return obj.full_billing_address


class CustomerCreateUpdateSerializer(CustomerDetailSerializer):
    """Serializer for party write operations."""

    class Meta(CustomerDetailSerializer.Meta):
        fields = [field for field in CustomerDetailSerializer.Meta.fields if field != "contacts"]

    def create(self, validated_data: dict[str, Any]) -> Customer:
        request = self.context.get("request")
        if request is None:
            raise serializers.ValidationError("Request context is required")

        company = request.user.company_profile
        validated_data["company"] = company
        if not validated_data.get("display_name"):
            validated_data["display_name"] = validated_data["name"]
        return Customer.objects.create(**validated_data)

    def update(self, instance: Customer, validated_data: dict[str, Any]) -> Customer:
        validated_data.pop("current_balance", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if not instance.display_name:
            instance.display_name = instance.name
        instance.save()
        return instance


class CustomerStatementSerializer(serializers.Serializer):
    """Serializer for party statement payloads."""

    customer = serializers.DictField()
    opening_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    transactions = serializers.ListField()
    closing_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
