"""Signals for accounts app side effects."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.dispatch import receiver
from django_rest_passwordreset.signals import reset_password_token_created


@receiver(reset_password_token_created)
def password_reset_token_created(*, sender: object, instance: object, reset_password_token: object, **kwargs: object) -> None:
    """Send a password reset email rendered from an HTML template."""
    reset_key = getattr(reset_password_token, "key")
    email = getattr(getattr(reset_password_token, "user"), "email")

    context = {
        "reset_key": reset_key,
        "email": email,
        "site_name": "Invoice Generator",
    }
    subject = "Password Reset Request - Invoice Generator"
    text_content = render_to_string("accounts/password_reset_email.txt", context)
    html_content = render_to_string("accounts/password_reset_email.html", context)

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send(fail_silently=False)