from __future__ import annotations

import re
from datetime import timedelta

from rest_framework import serializers


class DateRangeSerializer(serializers.Serializer):
    """Validate a generic report date range."""

    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)

    def validate(self, attrs: dict) -> dict:
        date_from = attrs["date_from"]
        date_to = attrs["date_to"]
        if date_from > date_to:
            raise serializers.ValidationError({"date_to": "date_to must be greater than or equal to date_from"})
        if (date_to - date_from) > timedelta(days=366):
            raise serializers.ValidationError({"date_to": "Date range cannot exceed 366 days"})
        return attrs


class FinancialYearSerializer(serializers.Serializer):
    """Validate optional financial year input in YY-YY format."""

    financial_year = serializers.CharField(required=False, allow_blank=False)

    def validate_financial_year(self, value: str) -> str:
        if not re.match(r"^\d{2}-\d{2}$", value):
            raise serializers.ValidationError("financial_year must be in format YY-YY")
        return value


class SalesReportQuerySerializer(serializers.Serializer):
    """Validate sales report range and top-N limit."""

    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)

    def validate(self, attrs: dict) -> dict:
        date_from = attrs["date_from"]
        date_to = attrs["date_to"]
        if date_from > date_to:
            raise serializers.ValidationError({"date_to": "date_to must be greater than or equal to date_from"})
        if (date_to - date_from) > timedelta(days=366):
            raise serializers.ValidationError({"date_to": "Date range cannot exceed 366 days"})
        return attrs


class StockMovementQuerySerializer(serializers.Serializer):
    """Validate inventory movement range and optional product filter."""

    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)
    product_id = serializers.UUIDField(required=False)

    def validate(self, attrs: dict) -> dict:
        date_from = attrs["date_from"]
        date_to = attrs["date_to"]
        if date_from > date_to:
            raise serializers.ValidationError({"date_to": "date_to must be greater than or equal to date_from"})
        if (date_to - date_from) > timedelta(days=366):
            raise serializers.ValidationError({"date_to": "Date range cannot exceed 366 days"})
        return attrs
