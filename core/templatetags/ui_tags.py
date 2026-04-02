from __future__ import annotations

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def initials(user) -> str:
    """Return initials for user/customer/name values."""
    if not user:
        return ""

    if isinstance(user, str):
        chunks = [part for part in user.strip().split() if part]
        if len(chunks) >= 2:
            return f"{chunks[0][:1]}{chunks[1][:1]}".upper()
        return user[:1].upper()

    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    if first or last:
        return f"{first[:1]}{last[:1]}".upper()

    display_name = (getattr(user, "display_name", "") or "").strip()
    name = (getattr(user, "name", "") or "").strip()
    value = display_name or name
    if value:
        chunks = [part for part in value.split() if part]
        if len(chunks) >= 2:
            return f"{chunks[0][:1]}{chunks[1][:1]}".upper()
        return value[:1].upper()

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
        raw_value = str(value or 0).replace(",", "").replace("₹", "").strip()
        amount = Decimal(raw_value or "0").quantize(Decimal("0.01"))
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


@register.filter
def party_color(letter):
    """Returns a brand color mapped from first letter for avatar variation."""
    colors = ["#1a3a5c", "#2d5986", "#c8832a", "#16a34a", "#2563eb"]
    text = str(letter or "A")
    idx = (ord(text[:1].upper()) - ord("A")) % len(colors)
    return colors[idx]


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Updates query string params while preserving existing ones."""
    request = context["request"]
    updated = request.GET.copy()
    for key, value in kwargs.items():
        updated[key] = value
    return updated.urlencode()


@register.filter
def enumerate_report(iterable):
    """Return enumerate(iterable) for use in templates."""
    return enumerate(iterable)


@register.filter
def get_key(data, key):
    """Safely get a key from a dict in templates."""
    if isinstance(data, dict):
        return data.get(key, {})
    return {}
