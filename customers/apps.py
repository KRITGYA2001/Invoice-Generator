from django.apps import AppConfig


class CustomersConfig(AppConfig):
    """Application configuration for the customers app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "customers"

    def ready(self) -> None:
        """Register signal handlers when the app boots."""
        import customers.signals  # noqa: F401
