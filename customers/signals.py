from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from customers.models import Customer


@receiver(pre_save, sender=Customer)
def set_display_name(sender, instance: Customer, **kwargs) -> None:
    """Use the party name as display name when none is provided."""
    if not instance.display_name:
        instance.display_name = instance.name


@receiver(post_save, sender=Customer)
def set_opening_balance(sender, instance: Customer, created: bool, **kwargs) -> None:
    """Initialize current balance from opening balance for new parties."""
    if not created or instance.opening_balance == 0:
        return
    Customer.objects.filter(pk=instance.pk).update(current_balance=instance.opening_balance)
