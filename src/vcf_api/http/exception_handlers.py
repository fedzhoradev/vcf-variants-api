import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from vcf_api.core.exceptions import InvalidPaginationError, PermissionDeniedError
from vcf_api.http.content_negotiation import NotAcceptableError
from vcf_api.variants.exceptions import InvalidVcfError, VariantNotFoundError

logger = logging.getLogger("vcf_api.errors")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
    app.add_exception_handler(VariantNotFoundError, variant_not_found_handler)
    app.add_exception_handler(NotAcceptableError, not_acceptable_handler)
    app.add_exception_handler(InvalidPaginationError, invalid_pagination_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(InvalidVcfError, invalid_vcf_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)


async def permission_denied_handler(request: Request, _: PermissionDeniedError) -> JSONResponse:
    return _error_response(
        request,
        status.HTTP_403_FORBIDDEN,
        "permission_denied",
        "Permission denied",
    )


async def variant_not_found_handler(request: Request, error: VariantNotFoundError) -> JSONResponse:
    variant_id = error.variant_id
    return _error_response(
        request,
        status.HTTP_404_NOT_FOUND,
        "variant_not_found",
        f"No variants found for id '{variant_id}'",
    )


async def not_acceptable_handler(request: Request, error: NotAcceptableError) -> JSONResponse:
    return _error_response(
        request,
        status.HTTP_406_NOT_ACCEPTABLE,
        "not_acceptable",
        str(error),
    )


async def invalid_pagination_handler(
    request: Request, error: InvalidPaginationError
) -> JSONResponse:
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "invalid_pagination",
        str(error),
    )


async def validation_error_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed",
        details=jsonable_encoder(error.errors()),
    )


async def invalid_vcf_handler(request: Request, error: InvalidVcfError) -> JSONResponse:
    _log_server_error(request, error)
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "invalid_vcf",
        "The configured VCF contains invalid data",
    )


async def http_exception_handler(request: Request, error: HTTPException) -> JSONResponse:
    return _error_response(
        request,
        error.status_code,
        "http_error",
        str(error.detail),
        headers=error.headers,
    )


async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    _log_server_error(request, error)
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_server_error",
        "An unexpected error occurred",
    )


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request.state.error_reason = code
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    response_headers = dict(headers or {})
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response_headers.setdefault("X-Request-ID", request_id)
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
        headers=response_headers,
    )


def _log_server_error(request: Request, error: Exception) -> None:
    logger.error(
        "Request processing failed",
        extra={
            "event": "request_error",
            "request_id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": request.url.path,
            "error_reason": type(error).__name__,
        },
        exc_info=(type(error), error, error.__traceback__),
    )
