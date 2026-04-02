from __future__ import annotations

import re
from typing import Any

from django.contrib.auth import authenticate
from rest_framework import serializers

from accounts.models import User


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise serializers.ValidationError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise serializers.ValidationError("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        raise serializers.ValidationError("Password must contain at least one digit")


class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "phone", "password", "confirm_password")

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email is already registered")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate registration payload values."""
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})

        validate_password_strength(password)
        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        """Create a user while excluding confirm_password from persistence."""
        validated_data.pop("confirm_password", None)
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate user credentials and account status."""
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(request=self.context.get("request"), email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        if not user.is_active:
            raise serializers.ValidationError("Account is inactive")

        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "phone", "date_joined", "updated_at")
        read_only_fields = ("id", "email", "date_joined", "updated_at")


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate new password confirmation and strength."""
        new_password = attrs.get("new_password")
        confirm_new_password = attrs.get("confirm_new_password")

        if new_password != confirm_new_password:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match"})

        validate_password_strength(new_password)
        return attrs
