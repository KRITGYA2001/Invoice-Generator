from django.urls import path

from accounts.views_ui import ChangePasswordView, LoginView, LogoutView, ProfileView, RegisterView

app_name = "accounts_ui"

urlpatterns = [
	path("login/", LoginView.as_view(), name="login"),
	path("logout/", LogoutView.as_view(), name="logout"),
	path("register/", RegisterView.as_view(), name="register"),
	path("profile/", ProfileView.as_view(), name="profile"),
	path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]
