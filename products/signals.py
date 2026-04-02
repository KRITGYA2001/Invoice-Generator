from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from company.models import CompanyProfile
from products.models import ProductCategory, UnitOfMeasurement


DEFAULT_UNITS = [
    ("Pieces", "Pcs"),
    ("Kilograms", "Kg"),
    ("Tonnes", "Ton"),
    ("Bags", "Bag"),
    ("Metres", "Mtr"),
    ("Sq. Feet", "Sqft"),
    ("Sq. Metres", "Sqmtr"),
    ("Running Ft", "Rft"),
    ("Litres", "Ltr"),
    ("Box", "Box"),
    ("Bundle", "Bundle"),
    ("Sheet", "Sheet"),
    ("Set", "Set"),
    ("Numbers", "Nos"),
]

DEFAULT_CATEGORIES = [
    "Safety",
    "Steel",
    "Cement",
    "Aggregate",
    "Masonry",
    "Plumbing",
    "Timber",
    "Electrical",
    "Paint",
    "Hardware",
]


@receiver(post_save, sender=CompanyProfile)
def seed_default_units(sender, instance, created, **kwargs):
    """
    Seed default units and categories when a new company is created.

    Args:
        sender: The model class being saved
        instance: The actual instance being saved
        created: Boolean indicating if a new instance was created
        **kwargs: Additional keyword arguments
    """
    if not created:
        return

    company = instance

    # Create default units
    for unit_name, short_name in DEFAULT_UNITS:
        UnitOfMeasurement.objects.get_or_create(
            company=company,
            short_name=short_name,
            defaults={"name": unit_name},
        )

    # Create default categories
    for category_name in DEFAULT_CATEGORIES:
        ProductCategory.objects.get_or_create(
            company=company,
            name=category_name,
        )
