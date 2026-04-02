from __future__ import annotations


def company_context(request):
    """Expose company context to templates for global UI rendering."""
    if request.user.is_authenticated:
        try:
            company = request.user.company_profile
            return {
                "company": company,
                "has_company": True,
            }
        except Exception:
            return {
                "company": None,
                "has_company": False,
            }
    return {
        "company": None,
        "has_company": False,
    }
