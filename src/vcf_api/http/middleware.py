import logging
from time import perf_counter
from urllib.parse import urlencode
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from vcf_api.http.exception_handlers import unexpected_error_handler

logger = logging.getLogger("vcf_api.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid4().hex
        request.state.request_id = request_id
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception as error:
            response = await unexpected_error_handler(request, error)

        response.headers["X-Request-ID"] = request_id
        context = self._context(
            request,
            request_id,
            started_at,
            status_code=response.status_code,
        )
        log = logger.info
        if response.status_code >= 500:
            log = logger.error
        elif response.status_code >= 400:
            log = logger.warning
        log("HTTP request completed", extra=context)
        return response

    @staticmethod
    def _context(
        request: Request,
        request_id: str,
        started_at: float,
        status_code: int,
    ) -> dict[str, object]:
        client_ip = request.client.host if request.client else "unknown"
        context: dict[str, object] = {
            "event": "http_request",
            "operation": RequestLoggingMiddleware._operation(request),
            "request_id": request_id,
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent", "unknown")[:300],
            "method": request.method,
            "path": request.url.path,
            "query": urlencode(
                [
                    (key, value[:200])
                    for key, value in request.query_params.multi_items()
                    if key in {"page", "page_size", "id"}
                ]
            )[:1000],
            "authenticated": getattr(request.state, "authenticated", False),
            "error_reason": getattr(request.state, "error_reason", None),
            "status_code": status_code,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        }
        target_id = request.query_params.get("id")
        if target_id:
            context["target_id"] = target_id[:200]
        return context

    @staticmethod
    def _operation(request: Request) -> str:
        route = request.scope.get("route")
        return getattr(route, "name", "http_request")
