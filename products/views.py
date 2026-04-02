from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from company.permissions import HasCompanyProfile
from products.filters import ProductFilter, StockMovementFilter
from products.models import Product, ProductCategory, StockMovement, UnitOfMeasurement
from products.serializers import (
	BulkProductUploadSerializer,
	ProductCategorySerializer,
	ProductDetailSerializer,
	ProductListSerializer,
	StockAdjustSerializer,
	StockMovementSerializer,
	UnitOfMeasurementSerializer,
)
from products.services import StockService


def success_response(message: str, data: dict[str, Any], status_code: int) -> Response:
	"""Build consistent success response."""
	return Response({"success": True, "message": message, "data": data}, status=status_code)


def error_response(message: str, errors: dict[str, Any], status_code: int) -> Response:
	"""Build consistent error response."""
	return Response({"success": False, "message": message, "errors": errors}, status=status_code)


class ProductCategoryListCreateView(ListCreateAPIView):
	"""
	GET /api/products/categories/ - List categories for authenticated user's company
	POST /api/products/categories/ - Create new category
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = ProductCategorySerializer

	def get_queryset(self):
		"""Filter categories by user's company."""
		company = self.request.user.company_profile
		return ProductCategory.objects.filter(company=company)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""List categories with optional is_active filter."""
		is_active = request.query_params.get("is_active", None)
		queryset = self.get_queryset()

		if is_active is not None:
			is_active_bool = is_active.lower() in ["true", "1", "yes"]
			queryset = queryset.filter(is_active=is_active_bool)

		serializer = self.get_serializer(queryset, many=True)
		return success_response("Categories retrieved successfully", {"categories": serializer.data}, status.HTTP_200_OK)

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Create new category."""
		serializer = self.get_serializer(data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		company = request.user.company_profile
		serializer.save(company=company)
		return success_response("Category created successfully", serializer.data, status.HTTP_201_CREATED)


class ProductCategoryDetailView(RetrieveUpdateDestroyAPIView):
	"""
	GET /api/products/categories/<uuid:pk>/ - Retrieve category
	PUT /api/products/categories/<uuid:pk>/ - Update category
	PATCH /api/products/categories/<uuid:pk>/ - Partial update
	DELETE /api/products/categories/<uuid:pk>/ - Soft delete category
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = ProductCategorySerializer

	def get_queryset(self):
		"""Filter by user's company."""
		company = self.request.user.company_profile
		return ProductCategory.objects.filter(company=company)

	def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Soft delete - set is_active=False."""
		instance = self.get_object()

		# Check if any products use this category
		if instance.products.filter(is_active=True).exists():
			return error_response(
				"Cannot delete category",
				{"detail": "Category is in use by active products"},
				status.HTTP_400_BAD_REQUEST,
			)

		instance.is_active = False
		instance.save(update_fields=["is_active"])
		return success_response("Category deleted successfully", {}, status.HTTP_204_NO_CONTENT)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance)
		return success_response("Category retrieved", serializer.data, status.HTTP_200_OK)

	def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		serializer.save()
		return success_response("Category updated successfully", serializer.data, status.HTTP_200_OK)

	def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data, partial=True)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		serializer.save()
		return success_response("Category updated successfully", serializer.data, status.HTTP_200_OK)


class UnitListCreateView(ListCreateAPIView):
	"""
	GET /api/products/units/ - List units
	POST /api/products/units/ - Create new unit
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = UnitOfMeasurementSerializer

	def get_queryset(self):
		"""Filter units by user's company."""
		company = self.request.user.company_profile
		return UnitOfMeasurement.objects.filter(company=company)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		queryset = self.get_queryset()
		serializer = self.get_serializer(queryset, many=True)
		return success_response("Units retrieved successfully", {"units": serializer.data}, status.HTTP_200_OK)

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		serializer = self.get_serializer(data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		company = request.user.company_profile
		serializer.save(company=company)
		return success_response("Unit created successfully", serializer.data, status.HTTP_201_CREATED)


class UnitDetailView(RetrieveUpdateDestroyAPIView):
	"""
	GET /api/products/units/<uuid:pk>/ - Retrieve unit
	PUT /api/products/units/<uuid:pk>/ - Update unit
	PATCH /api/products/units/<uuid:pk>/ - Partial update
	DELETE /api/products/units/<uuid:pk>/ - Delete unit
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = UnitOfMeasurementSerializer

	def get_queryset(self):
		company = self.request.user.company_profile
		return UnitOfMeasurement.objects.filter(company=company)

	def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Prevent deletion if products use this unit."""
		instance = self.get_object()

		if instance.products.exists():
			return error_response(
				"Cannot delete unit",
				{"detail": "Unit is in use by products"},
				status.HTTP_400_BAD_REQUEST,
			)

		instance.delete()
		return success_response("Unit deleted successfully", {}, status.HTTP_204_NO_CONTENT)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance)
		return success_response("Unit retrieved", serializer.data, status.HTTP_200_OK)

	def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		serializer.save()
		return success_response("Unit updated successfully", serializer.data, status.HTTP_200_OK)

	def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data, partial=True)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		serializer.save()
		return success_response("Unit updated successfully", serializer.data, status.HTTP_200_OK)


class ProductListCreateView(ListCreateAPIView):
	"""
	GET /api/products/ - Paginated list with filters and sorting
	POST /api/products/ - Create new product
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	filterset_class = ProductFilter
	pagination_class = None

	def get_queryset(self):
		"""Filter products by user's company."""
		company = self.request.user.company_profile
		return Product.objects.filter(company=company)

	def get_serializer_class(self):
		"""Use list serializer for GET, detail for POST."""
		if self.request.method == "POST":
			return ProductDetailSerializer
		return ProductListSerializer

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""List products with pagination and filtering."""
		queryset = self.get_queryset()

		# Apply filters
		filterset = ProductFilter(request.query_params, queryset=queryset)
		queryset = filterset.qs

		# Apply ordering
		ordering = request.query_params.get("ordering", "name")
		allowed_orderings = ["name", "-name", "selling_price", "-selling_price", "current_stock", "-current_stock", "created_at", "-created_at"]
		if ordering in allowed_orderings:
			queryset = queryset.order_by(ordering)

		# Paginate
		page_size = int(request.query_params.get("page_size", 20))
		page_num = int(request.query_params.get("page", 1))
		start = (page_num - 1) * page_size
		total = queryset.count()
		items = queryset[start : start + page_size]

		serializer = ProductListSerializer(items, many=True, context={"request": request})

		# Get stock summary
		summary = StockService.get_stock_summary(request.user.company_profile)

		data = {
			"products": serializer.data,
			"pagination": {
				"page": page_num,
				"page_size": page_size,
				"total": total,
				"total_pages": (total + page_size - 1) // page_size,
			},
			"summary": summary,
		}

		return success_response("Products retrieved successfully", data, status.HTTP_200_OK)

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Create new product."""
		serializer = ProductDetailSerializer(data=request.data, context={"request": request})
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		serializer.save()
		return success_response("Product created successfully", serializer.data, status.HTTP_201_CREATED)


class ProductDetailView(RetrieveUpdateDestroyAPIView):
	"""
	GET /api/products/<uuid:pk>/ - Retrieve product
	PUT /api/products/<uuid:pk>/ - Update product
	PATCH /api/products/<uuid:pk>/ - Partial update
	DELETE /api/products/<uuid:pk>/ - Soft delete product
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = ProductDetailSerializer

	def get_queryset(self):
		company = self.request.user.company_profile
		return Product.objects.filter(company=company)

	def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Soft delete product."""
		instance = self.get_object()

		# Check if used in invoices (would check when invoice module is created)
		# For now, just soft delete
		instance.is_active = False
		instance.save(update_fields=["is_active"])

		return success_response("Product deleted successfully", {}, status.HTTP_204_NO_CONTENT)

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance, context={"request": request})
		return success_response("Product retrieved", serializer.data, status.HTTP_200_OK)

	def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data, context={"request": request})
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		serializer.save()
		return success_response("Product updated successfully", serializer.data, status.HTTP_200_OK)

	def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data, partial=True, context={"request": request})
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)
		serializer.save()
		return success_response("Product updated successfully", serializer.data, status.HTTP_200_OK)


class ProductStockView(GenericAPIView):
	"""
	POST /api/products/<uuid:pk>/stock/ - Adjust stock (IN, ADJUST, RETURN)
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = StockAdjustSerializer

	def get_queryset(self):
		company = self.request.user.company_profile
		return Product.objects.filter(company=company)

	def get_object(self):
		"""Get product by pk."""
		return self.get_queryset().get(pk=self.kwargs["pk"])

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Adjust stock based on movement type."""
		product = self.get_object()
		serializer = self.get_serializer(data=request.data)

		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		movement_type = serializer.validated_data["movement_type"]
		quantity = serializer.validated_data["quantity"]
		notes = serializer.validated_data.get("notes", "")

		try:
			if movement_type == "IN":
				movement = StockService.add_stock(
					product,
					quantity,
					reference_type="manual",
					notes=notes,
					created_by=request.user,
				)
			elif movement_type == "ADJUST":
				movement = StockService.adjust_stock(
					product,
					quantity,
					notes=notes,
					created_by=request.user,
				)
			elif movement_type == "RETURN":
				movement = StockService.add_stock(
					product,
					quantity,
					reference_type="return",
					notes=notes,
					created_by=request.user,
				)

			# Refresh product to get updated stock
			product.refresh_from_db()
			product_data = ProductDetailSerializer(product, context={"request": request}).data

			data = {
				"product": product_data,
				"movement": StockMovementSerializer(movement).data,
			}

			return success_response("Stock adjusted successfully", data, status.HTTP_200_OK)

		except ValueError as e:
			return error_response("Stock adjustment failed", {"detail": str(e)}, status.HTTP_400_BAD_REQUEST)


class ProductStockHistoryView(ListCreateAPIView):
	"""
	GET /api/products/<uuid:pk>/stock/history/ - Paginated stock movement history
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = StockMovementSerializer
	filterset_class = StockMovementFilter
	pagination_class = None

	def get_queryset(self):
		"""Get stock movements for specific product."""
		pk = self.kwargs.get("pk")
		company = self.request.user.company_profile

		# Verify product belongs to company
		if not Product.objects.filter(id=pk, company=company).exists():
			return StockMovement.objects.none()

		return StockMovement.objects.filter(product__id=pk).order_by("-created_at")

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""List stock movements with pagination."""
		queryset = self.get_queryset()

		# Apply filters
		filterset = StockMovementFilter(request.query_params, queryset=queryset)
		queryset = filterset.qs

		# Paginate
		page_size = int(request.query_params.get("page_size", 50))
		page_num = int(request.query_params.get("page", 1))
		start = (page_num - 1) * page_size
		total = queryset.count()
		items = queryset[start : start + page_size]

		serializer = self.get_serializer(items, many=True)

		data = {
			"movements": serializer.data,
			"pagination": {
				"page": page_num,
				"page_size": page_size,
				"total": total,
				"total_pages": (total + page_size - 1) // page_size,
			},
		}

		return success_response("Stock history retrieved", data, status.HTTP_200_OK)


class StockSummaryView(GenericAPIView):
	"""
	GET /api/products/stock/summary/ - Get stock summary for company
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]

	def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Get stock summary."""
		company = request.user.company_profile
		summary = StockService.get_stock_summary(company)
		return success_response("Stock summary retrieved", summary, status.HTTP_200_OK)


class BulkProductUploadView(GenericAPIView):
	"""
	POST /api/products/bulk-upload/ - Upload multiple products
	"""

	authentication_classes = [JWTAuthentication]
	permission_classes = [IsAuthenticated, HasCompanyProfile]
	serializer_class = BulkProductUploadSerializer

	def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
		"""Bulk upload products."""
		serializer = self.get_serializer(data=request.data)
		if not serializer.is_valid():
			return error_response("Validation failed", serializer.errors, status.HTTP_400_BAD_REQUEST)

		products_data = serializer.validated_data["products"]
		company = request.user.company_profile

		created_ids = []
		errors = []

		try:
			with transaction.atomic():
				for idx, product_data in enumerate(products_data):
					try:
						category_name = product_data.pop("category_name", None)
						unit_short_name = product_data.pop("unit_short_name", None)

						category = None
						if category_name:
							category, _ = ProductCategory.objects.get_or_create(
								company=company, name=category_name
							)

						unit = None
						if unit_short_name:
							try:
								unit = UnitOfMeasurement.objects.get(
									company=company, short_name=unit_short_name
								)
							except UnitOfMeasurement.DoesNotExist:
								errors.append({"row": idx, "error": f"Unit {unit_short_name} not found"})
								continue

						product = Product.objects.create(
							company=company,
							category=category,
							unit=unit,
							**product_data,
						)

						created_ids.append(str(product.id))

					except Exception as e:
						errors.append({"row": idx, "error": str(e)})

		except Exception as e:
			return error_response(
				"Bulk upload failed",
				{"detail": str(e)},
				status.HTTP_400_BAD_REQUEST,
			)

		data = {
			"created_count": len(created_ids),
			"created_ids": created_ids,
			"errors": errors,
		}

		status_code = status.HTTP_201_CREATED if not errors else status.HTTP_207_MULTI_STATUS

		return success_response("Bulk upload completed", data, status_code)
