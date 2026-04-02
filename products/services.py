from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from django.db import transaction

from products.models import Product, StockMovement

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model


class StockService:
    @staticmethod
    def add_stock(
        product: Product,
        quantity: Decimal,
        reference_type: str = "manual",
        reference_id: Optional[str] = None,
        notes: str = "",
        movement_type: str = "IN",
        created_by=None,
    ) -> StockMovement:
        """
        Increase product stock by creating a stock in movement.

        Args:
            product: Product instance to add stock to
            quantity: Positive decimal quantity to add
            reference_type: Type of reference (invoice, purchase_order, manual, etc.)
            reference_id: UUID reference to the triggering document
            notes: Optional notes about the movement
            created_by: User who performed the movement

        Returns:
            StockMovement instance
        """
        with transaction.atomic():
            stock_before = product.current_stock
            product.current_stock += quantity
            product.save(update_fields=["current_stock"])

            movement = StockMovement.objects.create(
                product=product,
                movement_type=movement_type,
                quantity=quantity,
                stock_before=stock_before,
                stock_after=product.current_stock,
                reference_type=reference_type,
                reference_id=reference_id,
                notes=notes,
                created_by=created_by,
            )
            return movement

    @staticmethod
    def deduct_stock(
        product: Product,
        quantity: Decimal,
        reference_type: str = "invoice",
        reference_id: Optional[str] = None,
        notes: str = "",
        created_by=None,
    ) -> StockMovement:
        """
        Decrease product stock by creating a stock out movement.
        Validates sufficient stock if tracking is enabled.

        Args:
            product: Product instance to deduct stock from
            quantity: Positive decimal quantity to deduct
            reference_type: Type of reference (invoice, purchase_order, etc.)
            reference_id: UUID reference to the triggering document
            notes: Optional notes about the movement
            created_by: User who performed the movement

        Returns:
            StockMovement instance

        Raises:
            ValueError: If quantity > current_stock and tracking is enabled
        """
        if product.track_inventory and quantity > product.current_stock:
            raise ValueError(
                f"Insufficient stock for {product.name}. "
                f"Available: {product.current_stock}, Requested: {quantity}"
            )

        with transaction.atomic():
            stock_before = product.current_stock
            product.current_stock -= quantity
            product.save(update_fields=["current_stock"])

            movement = StockMovement.objects.create(
                product=product,
                movement_type="OUT",
                quantity=quantity,
                stock_before=stock_before,
                stock_after=product.current_stock,
                reference_type=reference_type,
                reference_id=reference_id,
                notes=notes,
                created_by=created_by,
            )
            return movement

    @staticmethod
    def adjust_stock(
        product: Product,
        new_quantity: Decimal,
        notes: str = "",
        created_by=None,
    ) -> StockMovement:
        """
        Set stock to a specific value (manual correction).
        Creates adjustment movement with the difference.

        Args:
            product: Product instance to adjust
            new_quantity: Target stock quantity
            notes: Notes about the adjustment
            created_by: User who performed the movement

        Returns:
            StockMovement instance
        """
        with transaction.atomic():
            stock_before = product.current_stock
            difference = abs(new_quantity - stock_before)

            product.current_stock = new_quantity
            product.save(update_fields=["current_stock"])

            movement = StockMovement.objects.create(
                product=product,
                movement_type="ADJUST",
                quantity=difference,
                stock_before=stock_before,
                stock_after=product.current_stock,
                reference_type="manual",
                notes=notes,
                created_by=created_by,
            )
            return movement

    @staticmethod
    def set_opening_stock(
        product: Product,
        quantity: Decimal,
        created_by=None,
    ) -> StockMovement:
        """
        Set opening stock for a product.
        Only allowed if no previous stock movements exist.

        Args:
            product: Product instance
            quantity: Opening stock quantity
            created_by: User who performed the movement

        Returns:
            StockMovement instance

        Raises:
            ValueError: If product already has movements
        """
        if StockMovement.objects.filter(product=product).exists():
            raise ValueError(f"Product {product.name} already has stock movements")

        with transaction.atomic():
            product.current_stock = quantity
            product.opening_stock = quantity
            product.save(update_fields=["current_stock", "opening_stock"])

            movement = StockMovement.objects.create(
                product=product,
                movement_type="OPENING",
                quantity=quantity,
                stock_before=Decimal("0"),
                stock_after=quantity,
                reference_type="opening",
                created_by=created_by,
            )
            return movement

    @staticmethod
    def get_stock_summary(company) -> dict:
        """
        Generate stock summary for a company.

        Args:
            company: CompanyProfile instance

        Returns:
            Dictionary with stock statistics
        """
        products = Product.objects.filter(company=company)
        active_products = products.filter(is_active=True)
        low_stock_products = [p for p in active_products if p.is_low_stock]
        out_of_stock_products = [p for p in active_products if p.current_stock == 0]
        
        total_stock_value = sum((p.stock_value for p in active_products), Decimal("0"))

        return {
            "total_products": products.count(),
            "active_products": active_products.count(),
            "low_stock_count": len(low_stock_products),
            "out_of_stock_count": len(out_of_stock_products),
            "total_stock_value": float(total_stock_value),
            "low_stock_products": [
                {"id": str(p.id), "name": p.name, "current_stock": float(p.current_stock)}
                for p in low_stock_products
            ],
        }
