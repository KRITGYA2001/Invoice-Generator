from __future__ import annotations

from django.db.models import F
from django_filters import BooleanFilter, CharFilter, ChoiceFilter, FilterSet

import customers.models as customer_models


class CustomerFilter(FilterSet):
    """FilterSet for party list and search endpoints."""

    name = CharFilter(field_name="name", lookup_expr="icontains")
    display_name = CharFilter(field_name="display_name", lookup_expr="icontains")
    gstin = CharFilter(field_name="gstin", lookup_expr="icontains")
    mobile_primary = CharFilter(field_name="mobile_primary", lookup_expr="icontains")
    email = CharFilter(field_name="email", lookup_expr="icontains")
    party_type = ChoiceFilter(field_name="party_type")
    billing_state = CharFilter(field_name="billing_state", lookup_expr="icontains")
    billing_city = CharFilter(field_name="billing_city", lookup_expr="icontains")
    is_active = BooleanFilter(field_name="is_active")
    is_over_limit = BooleanFilter(method="filter_is_over_limit")

    class Meta:
        model = customer_models.Customer
        fields = [
            "name",
            "display_name",
            "gstin",
            "mobile_primary",
            "email",
            "party_type",
            "billing_state",
            "billing_city",
            "is_active",
            "is_over_limit",
        ]

    def filter_is_over_limit(self, queryset, name, value):
        """Filter customers that are above their approved credit limit."""
        if value:
            return queryset.filter(credit_limit__gt=0, current_balance__gt=F("credit_limit"))
        return queryset
