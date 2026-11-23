from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    code: str = "SERVICE_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class DuplicateMismatchError(ServiceError):
    code = "DUPLICATE_MISMATCH"
    http_status = 409


class OversellServiceError(ServiceError):
    code = "OVERSELL"
    http_status = 409


class NotFoundError(ServiceError):
    code = "NOT_FOUND"
    http_status = 404


class ValidationServiceError(ServiceError):
    code = "VALIDATION_ERROR"
    http_status = 422
