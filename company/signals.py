from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from company.models import BankDetail, CompanyProfile, InvoiceSettings


@receiver(post_save, sender=CompanyProfile)
def auto_create_invoice_settings(sender, instance: CompanyProfile, created: bool, **kwargs) -> None:
    if created:
        InvoiceSettings.objects.get_or_create(company=instance)


@receiver(pre_save, sender=BankDetail)
def ensure_single_primary_bank(sender, instance: BankDetail, **kwargs) -> None:
    company = getattr(instance, "company", None)
    if instance.is_primary and company is not None:
        BankDetail.objects.filter(company=company).exclude(pk=instance.pk).update(is_primary=False)