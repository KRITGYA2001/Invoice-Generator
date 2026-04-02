"""URL routes for authentication and profile endpoints."""

from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import ChangePasswordView, LoginView, LogoutView, RegisterView, UserProfileView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("profile/", UserProfileView.as_view(), name="auth-profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("password-reset/", include("django_rest_passwordreset.urls", namespace="password_reset")),
]