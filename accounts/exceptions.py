"""Custom exception handling for API responses."""

from __future__ import annotations

from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Wrap DRF exceptions in a consistent response shape."""
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    message = "Request failed"
    errors: dict[str, Any] = {}

    if isinstance(detail, dict):
        if "detail" in detail:
            message = str(detail.get("detail"))
            errors = {"detail": detail.get("detail")}
        else:
            message = "Validation error"
            errors = detail
    elif isinstance(detail, list):
        message = str(detail[0]) if detail else "Validation error"
        errors = {"non_field_errors": detail}
    else:
        message = str(detail)
        errors = {"detail": detail}

    response.data = {
        "success": False,
        "message": message,
        "errors": errors,
    }
    return response