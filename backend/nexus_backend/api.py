"""Shared API conventions: the `{success, data}` / `{success, error}` envelope."""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(exceptions.APIException):
    """An API error carrying an explicit machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "bad_request"
    default_detail = "Bad request."

    def __init__(self, message: str, code: str | None = None, status_code: int | None = None, details=None):
        super().__init__(detail=message, code=code or self.default_code)
        if status_code is not None:
            self.status_code = status_code
        self.error_code = code or self.default_code
        self.details = details


class EnvelopeJSONRenderer(JSONRenderer):
    """Wraps successful payloads as `{"success": true, "data": ...}`."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        already_wrapped = isinstance(data, dict) and "success" in data and ("data" in data or "error" in data)
        if response is not None and response.status_code == 204:
            return b""
        if not already_wrapped:
            if response is not None and response.status_code >= 400:
                data = {"success": False, "error": {"code": "error", "message": str(data)}}
            else:
                data = {"success": True, "data": data}
        return super().render(data, accepted_media_type, renderer_context)


def _flatten_message(detail) -> str:
    if isinstance(detail, list):
        return " ".join(_flatten_message(d) for d in detail)
    if isinstance(detail, dict):
        parts = []
        for key, value in detail.items():
            msg = _flatten_message(value)
            parts.append(msg if key in ("non_field_errors", "detail") else f"{key}: {msg}")
        return " ".join(parts)
    return str(detail)


def envelope_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ApiError):
        code = exc.error_code
        details = exc.details
    elif isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
        details = response.data
    else:
        codes = exc.get_codes() if isinstance(exc, exceptions.APIException) else "error"
        code = codes if isinstance(codes, str) else "error"
        details = None

    detail = response.data
    if isinstance(detail, dict) and set(detail.keys()) <= {"detail", "code", "messages"} and "detail" in detail:
        detail = detail["detail"]
    error = {"code": code, "message": _flatten_message(detail)}
    if details is not None:
        error["details"] = details
    response.data = {"success": False, "error": error}
    return response


def ok(data=None, status_code: int = status.HTTP_200_OK) -> Response:
    return Response(data, status=status_code)
