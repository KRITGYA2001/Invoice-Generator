from django.apps import AppConfig


class InvoicesConfig(AppConfig):
    """Application configuration for the invoices app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "invoices"

    def ready(self) -> None:
        """Register invoice signals when the app boots."""
        import invoices.signals  # noqa: F401
