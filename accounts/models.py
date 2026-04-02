from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
	def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
		"""Create and return a regular user with an email and password."""
		if not email:
			raise ValueError("Email is required")
		if not password:
			raise ValueError("Password is required")

		normalized_email = self.normalize_email(email)
		user = self.model(email=normalized_email, **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
		"""Create and return a superuser with required privilege flags."""
		extra_fields.setdefault("is_staff", True)
		extra_fields.setdefault("is_superuser", True)
		extra_fields.setdefault("is_active", True)

		if extra_fields.get("is_staff") is not True:
			raise ValueError("Superuser must have is_staff=True")
		if extra_fields.get("is_superuser") is not True:
			raise ValueError("Superuser must have is_superuser=True")

		return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	email = models.EmailField(unique=True)
	first_name = models.CharField(max_length=150)
	last_name = models.CharField(max_length=150)
	phone = models.CharField(max_length=20, blank=True)
	is_active = models.BooleanField(default=True)
	is_staff = models.BooleanField(default=False)
	groups = models.ManyToManyField(
		"auth.Group",
		related_name="accounts_user_set",
		related_query_name="accounts_user",
		blank=True,
	)
	user_permissions = models.ManyToManyField(
		"auth.Permission",
		related_name="accounts_user_set",
		related_query_name="accounts_user",
		blank=True,
	)
	date_joined = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = UserManager()

	USERNAME_FIELD = "email"
	REQUIRED_FIELDS = ["first_name", "last_name"]

	def __str__(self) -> str:
		return self.email
