from __future__ import annotations

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def initials(user) -> str:
    """Return initials from first_name and last_name, fallback to email first letter."""
    if not user:
        return ""
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    if first or last:
        return f"{first[:1]}{last[:1]}".upper()
    email = (getattr(user, "email", "") or "").strip()
    return email[:1].upper()


def _indian_comma(number_str: str) -> str:
    if len(number_str) <= 3:
        return number_str
    last3 = number_str[-3:]
    remaining = number_str[:-3]
    parts = []
    while len(remaining) > 2:
        parts.insert(0, remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        parts.insert(0, remaining)
    return ",".join(parts + [last3])


@register.filter
def indian_rupee(value) -> str:
    """Format value as Indian rupee currency string."""
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        amount = Decimal("0.00")
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    whole, frac = f"{amount:.2f}".split(".")
    return f"{sign}₹{_indian_comma(whole)}.{frac}"


@register.filter
def short_number(value) -> str:
    """Return compact Indian-style short number units."""
    try:
        number = Decimal(str(value or 0))
    except Exception:
        number = Decimal("0")
    abs_number = abs(number)
    if abs_number >= Decimal("10000000"):
        compact = (number / Decimal("10000000")).quantize(Decimal("0.01")).normalize()
        return f"{compact}Cr"
    if abs_number >= Decimal("100000"):
        compact = (number / Decimal("100000")).quantize(Decimal("0.01")).normalize()
        return f"{compact}L"
    if abs_number >= Decimal("1000"):
        compact = (number / Decimal("1000")).quantize(Decimal("0.01")).normalize()
        return f"{compact}K"
    return str(number.quantize(Decimal("1")) if number == number.to_integral() else number)


@register.simple_tag
def active_nav(request, url_name: str) -> str:
    """Return active class when current route name equals url_name."""
    current = getattr(getattr(request, "resolver_match", None), "url_name", None)
    return "active" if current == url_name else ""


@register.simple_tag
def active_nav_contains(request, keyword: str) -> str:
    """Return active class when current route name contains keyword."""
    current = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    return "active" if keyword in current else ""
