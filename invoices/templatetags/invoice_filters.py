from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _to_decimal(value) -> Decimal:
    """Convert a value to Decimal safely."""
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


@register.filter
def indian_currency(value):
    """Format a number using Indian comma separators with two decimals."""
    amount = _to_decimal(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    integer_part, decimal_part = f"{amount:.2f}".split(".")
    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        chunks = []
        while len(remaining) > 2:
            chunks.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            chunks.insert(0, remaining)
        formatted = ",".join(chunks + [last_three])
    return f"{sign}{formatted}.{decimal_part}"


@register.filter
def indian_currency_no_decimal(value):
    """Format a number using Indian comma separators without decimals."""
    amount = int(_to_decimal(value).quantize(Decimal("1")))
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    integer_part = str(amount)
    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        chunks = []
        while len(remaining) > 2:
            chunks.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            chunks.insert(0, remaining)
        formatted = ",".join(chunks + [last_three])
    return f"{sign}{formatted}"


@register.filter
def strip_zeros(value):
    """Strip trailing zeros from decimal values."""
    amount = _to_decimal(value)
    normalized = amount.normalize()
    return format(normalized, "f").rstrip("0").rstrip(".") or "0"


@register.filter
def format_date_indian(value):
    """Format a date as DD-MM-YYYY."""
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d-%m-%Y")
    return str(value)


@register.filter
def split_lines(value):
    """Split multiline text into non-empty lines."""
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]
