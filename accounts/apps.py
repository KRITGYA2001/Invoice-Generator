from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Application configuration for accounts module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:
        """Import signal handlers on app initialization."""
        import accounts.signals  # noqa: F401
