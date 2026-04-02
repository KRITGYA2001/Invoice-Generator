"""Authentication and user profile API views."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import update_session_auth_hash
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import GenericAPIView

from accounts.serializers import (
	ChangePasswordSerializer,
	LoginSerializer,
	RegisterSerializer,
	UserProfileSerializer,
)


def build_success_response(message: str, data: dict[str, Any], status_code: int) -> Response:
	"""Build a standardized successful API response payload."""
	return Response({"success": True, "message": message, "data": data}, status=status_code)


class RegisterView(GenericAPIView):
	"""Register a new user and return JWT tokens."""

	serializer_class = RegisterSerializer
	permission_classes = [AllowAny]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Handle user registration requests."""
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.save()

		refresh = RefreshToken.for_user(user)
		data = {
			"user": {
				"id": str(user.id),
				"email": user.email,
				"first_name": user.first_name,
				"last_name": user.last_name,
			},
			"tokens": {
				"access": str(refresh.access_token),
				"refresh": str(refresh),
			},
		}
		return build_success_response("Registration successful", data, status.HTTP_201_CREATED)


class LoginView(GenericAPIView):
	"""Authenticate a user and return JWT tokens."""

	serializer_class = LoginSerializer
	permission_classes = [AllowAny]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Handle user login requests."""
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.validated_data["user"]

		refresh = RefreshToken.for_user(user)
		data = {
			"user": {
				"id": str(user.id),
				"email": user.email,
				"first_name": user.first_name,
				"last_name": user.last_name,
			},
			"tokens": {
				"access": str(refresh.access_token),
				"refresh": str(refresh),
			},
		}
		return build_success_response("Login successful", data, status.HTTP_200_OK)


class LogoutView(GenericAPIView):
	"""Invalidate a refresh token by blacklisting it."""

	permission_classes = [IsAuthenticated]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Handle logout and token blacklist requests."""
		token = request.data.get("refresh")
		if not token:
			return Response(
				{
					"success": False,
					"message": "Validation error",
					"errors": {"refresh": "Refresh token is required"},
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		try:
			RefreshToken(token).blacklist()
		except TokenError as exc:
			return Response(
				{
					"success": False,
					"message": "Token error",
					"errors": {"refresh": str(exc)},
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		return build_success_response("Logout successful", {}, status.HTTP_200_OK)


class UserProfileView(GenericAPIView):
	"""Retrieve or partially update authenticated user profile data."""

	serializer_class = UserProfileSerializer
	permission_classes = [IsAuthenticated]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Return the authenticated user's profile."""
		serializer = self.get_serializer(request.user)
		return build_success_response("Profile fetched successfully", serializer.data, status.HTTP_200_OK)

	def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Partially update the authenticated user's profile."""
		serializer = self.get_serializer(request.user, data=request.data, partial=True)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return build_success_response("Profile updated successfully", serializer.data, status.HTTP_200_OK)


class ChangePasswordView(GenericAPIView):
	"""Change the authenticated user's password."""

	serializer_class = ChangePasswordSerializer
	permission_classes = [IsAuthenticated]

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Validate and update user password."""
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		old_password = serializer.validated_data["old_password"]
		new_password = serializer.validated_data["new_password"]

		if not request.user.check_password(old_password):
			return Response(
				{
					"success": False,
					"message": "Validation error",
					"errors": {"old_password": "Incorrect password"},
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		request.user.set_password(new_password)
		request.user.save(update_fields=["password", "updated_at"])
		update_session_auth_hash(request, request.user)

		return build_success_response("Password changed successfully", {}, status.HTTP_200_OK)
