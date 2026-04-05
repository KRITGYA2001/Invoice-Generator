from __future__ import annotations

import re
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.decorators import method_decorator
from django.views import View

from accounts.models import User


def _company_onboarding_url() -> str:
    """Return onboarding URL for UI; fallback to reserved UI path if route is not available yet."""
    try:
        return reverse("company_ui:onboarding")
    except NoReverseMatch:
        return "/company/onboarding/"


def _password_strength_error(password: str) -> str | None:
    """Return password rule violation if any."""
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return "Password must include at least one uppercase letter"
    if not re.search(r"\d", password):
        return "Password must include at least one digit"
    return None


class LoginView(View):
    """Session-based login view for the UI."""

    template_name = "accounts/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("/")
        return render(request, self.template_name, {"form_email": "", "next_url": request.GET.get("next", "")})

    def post(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("/")

        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        remember_me = request.POST.get("remember_me") == "on"
        next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
        user = authenticate(request, username=email, password=password)

        if not user or not user.is_active:
            messages.error(request, "Invalid email or password")
            return render(
                request,
                self.template_name,
                {
                    "form_email": email,
                    "next_url": next_url,
                },
                status=400,
            )

        login(request, user)
        request.session.set_expiry(1209600 if remember_me else 0)
        return redirect(next_url or "/")


class LogoutView(View):
    """Session-based logout view for the UI."""

    def get(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        messages.success(request, "You have been logged out")
        return redirect("accounts_ui:login")

    def post(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        messages.success(request, "You have been logged out")
        return redirect("accounts_ui:login")


class RegisterView(View):
    """Create a user account and sign them in for onboarding."""

    template_name = "accounts/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("/")
        return render(request, self.template_name, {"form_data": {}})

    def post(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("/")

        form_data = {
            "first_name": (request.POST.get("first_name") or "").strip(),
            "last_name": (request.POST.get("last_name") or "").strip(),
            "email": (request.POST.get("email") or "").strip().lower(),
            "terms": request.POST.get("terms") == "on",
        }
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        errors: dict[str, str] = {}

        if not form_data["first_name"]:
            errors["first_name"] = "First name is required"
        if not form_data["last_name"]:
            errors["last_name"] = "Last name is required"
        if not form_data["email"]:
            errors["email"] = "Email is required"
        elif User.objects.filter(email__iexact=form_data["email"]).exists():
            errors["email"] = "Email is already registered"

        password_error = _password_strength_error(password)
        if password_error:
            errors["password"] = password_error
        if password != confirm_password:
            errors["confirm_password"] = "Passwords do not match"
        if not form_data["terms"]:
            errors["terms"] = "You must agree to the Terms of Service"

        if errors:
            for message_text in errors.values():
                messages.error(request, message_text)
            return render(
                request,
                self.template_name,
                {
                    "form_data": form_data,
                    "form_errors": errors,
                },
                status=400,
            )

        user = User(
            email=form_data["email"],
            first_name=form_data["first_name"],
            last_name=form_data["last_name"],
        )
        user.set_password(password)
        user.save()
        login(request, user)
        messages.success(request, "Welcome! Please set up your company profile to get started.")
        return redirect(_company_onboarding_url())


@method_decorator(login_required, name="dispatch")
class ProfileView(View):
    """View and edit current user's personal information."""

    template_name = "accounts/profile.html"

    @staticmethod
    def _context(request: HttpRequest) -> dict:
        user = request.user
        if not isinstance(user, User):
            return {"user_obj": user, "member_since_days": 0}
        return {
            "user_obj": user,
            "member_since_days": max((datetime.now().date() - user.date_joined.date()).days, 0),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, self._context(request))

    def post(self, request: HttpRequest) -> HttpResponse:
        user = request.user
        if not isinstance(user, User):
            return redirect("accounts_ui:login")
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()

        if not first_name or not last_name:
            messages.error(request, "First name and last name are required")
        else:
            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone
            user.save()
            messages.success(request, "Profile updated successfully")

        context = self._context(request)
        if request.headers.get("HX-Request"):
            return render(request, "accounts/partials/profile_form_inner.html", context)
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class ChangePasswordView(View):
    """Allow a logged-in user to update their password."""

    template_name = "accounts/change_password.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        if not isinstance(request.user, User):
            return redirect("accounts_ui:login")

        old_password = request.POST.get("old_password") or ""
        new_password = request.POST.get("new_password") or ""
        confirm_new_password = request.POST.get("confirm_new_password") or ""

        if not request.user.check_password(old_password):
            messages.error(request, "Current password is incorrect")
            return render(request, self.template_name, status=400)

        password_error = _password_strength_error(new_password)
        if password_error:
            messages.error(request, password_error)
            return render(request, self.template_name, status=400)

        if new_password != confirm_new_password:
            messages.error(request, "New password and confirmation do not match")
            return render(request, self.template_name, status=400)

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, "Password changed successfully")
        return redirect("accounts_ui:profile")
