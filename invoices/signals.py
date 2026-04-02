from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from customers.models import Customer
from invoices.models import Invoice


@receiver(post_save, sender=Invoice)
def update_customer_statement(sender, instance: Invoice, **kwargs) -> None:
    """Touch the customer when a posted invoice reaches an active terminal state."""
    if instance.customer_id and instance.status in {Invoice.StatusChoices.ISSUED, Invoice.StatusChoices.CANCELLED}:
        Customer.objects.filter(pk=instance.customer_id).update(updated_at=timezone.now())
