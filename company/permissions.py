from __future__ import annotations

from rest_framework.permissions import BasePermission


class HasCompanyProfile(BasePermission):
    message = "Complete company onboarding first"

    def has_permission(self, request, view) -> bool:
        """Return True only when the authenticated user has a company profile."""
        if not getattr(request.user, "is_authenticated", False):
            return False
        return hasattr(request.user, "company_profile")
