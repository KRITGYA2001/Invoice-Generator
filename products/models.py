from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


hsn_code_validator = RegexValidator(
	regex=r"^[0-9]{4,8}$",
	message="HSN/SAC code must be 4-8 digit numeric string",
)


class ProductCategory(models.Model):
	"""
	Product category model for organizing products within a company.
	Each company can have multiple categories.
	"""

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	company = models.ForeignKey(
		"company.CompanyProfile", on_delete=models.CASCADE, related_name="product_categories"
	)
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("company", "name")
		ordering = ["name"]
		verbose_name = "Product Category"
		verbose_name_plural = "Product Categories"

	def __str__(self) -> str:
		return self.name


class UnitOfMeasurement(models.Model):
	"""
	Units of measurement for products (e.g., Pieces, Kilograms, Metres).
	Seeded with defaults on company creation.
	"""

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	company = models.ForeignKey(
		"company.CompanyProfile", on_delete=models.CASCADE, related_name="units"
	)
	name = models.CharField(max_length=50)
	short_name = models.CharField(max_length=10)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ("company", "short_name")
		ordering = ["name"]
		verbose_name = "Unit of Measurement"
		verbose_name_plural = "Units of Measurement"

	def __str__(self) -> str:
		return f"{self.name} ({self.short_name})"


class Product(models.Model):
	"""
	Product model representing items that can be invoiced.
	Supports both goods (with HSN) and services (with SAC).
	"""

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	company = models.ForeignKey(
		"company.CompanyProfile", on_delete=models.CASCADE, related_name="products"
	)
	category = models.ForeignKey(
		ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
	)
	name = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	sku = models.CharField(max_length=100, blank=True)
	hsn_code = models.CharField(
		max_length=10, validators=[hsn_code_validator], help_text="HSN for goods, SAC for services"
	)
	unit = models.ForeignKey(
		UnitOfMeasurement, on_delete=models.SET_NULL, null=True, related_name="products"
	)
	selling_price = models.DecimalField(max_digits=12, decimal_places=2)
	purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
	cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	is_service = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	track_inventory = models.BooleanField(default=True)
	current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
	minimum_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
	maximum_stock = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
	opening_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
	image = models.ImageField(upload_to="products/images/", null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("company", "name")
		ordering = ["name"]
		verbose_name = "Product"
		verbose_name_plural = "Products"

	def __str__(self) -> str:
		return self.name

	@property
	def is_low_stock(self) -> bool:
		"""Check if product is low on stock."""
		return self.track_inventory and self.current_stock <= self.minimum_stock

	@property
	def stock_value(self) -> Decimal:
		"""Calculate total stock value using purchase price or selling price."""
		price = self.purchase_price or self.selling_price
		return self.current_stock * price

	@property
	def gst_amount(self) -> Decimal:
		"""Calculate GST amount on selling price."""
		return self.selling_price * (self.gst_rate / 100)


class StockMovement(models.Model):
	"""
	Record of all stock movements for a product.
	Immutable log of inventory changes.
	"""

	MOVEMENT_TYPE_CHOICES = [
		("IN", "Stock In"),
		("OUT", "Stock Out"),
		("ADJUST", "Adjustment"),
		("OPENING", "Opening Stock"),
		("RETURN", "Return"),
	]

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	product = models.ForeignKey(
		Product, on_delete=models.CASCADE, related_name="stock_movements"
	)
	movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
	quantity = models.DecimalField(max_digits=12, decimal_places=3)
	stock_before = models.DecimalField(max_digits=12, decimal_places=3)
	stock_after = models.DecimalField(max_digits=12, decimal_places=3)
	reference_type = models.CharField(max_length=50, blank=True)
	reference_id = models.UUIDField(null=True, blank=True)
	notes = models.TextField(blank=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="stock_movements"
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "Stock Movement"
		verbose_name_plural = "Stock Movements"

	def __str__(self) -> str:
		return f"{self.get_movement_type_display()} - {self.product.name} - {self.quantity}"
