from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging_config import get_logger
from app.schemas.errors import ErrorBody
from app.services.exceptions import ServiceError

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
        body = ErrorBody(code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(status_code=exc.http_status, content=jsonable_encoder(body))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
        body = ErrorBody(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
        )
        return JSONResponse(status_code=422, content=body.model_dump())

