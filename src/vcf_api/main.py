from contextlib import asynccontextmanager

from fastapi import FastAPI

from vcf_api.core.config import Settings, get_settings
from vcf_api.http.exception_handlers import register_exception_handlers
from vcf_api.http.logging import configure_logging
from vcf_api.http.middleware import RequestLoggingMiddleware
from vcf_api.variants.api import router as variants_router
from vcf_api.variants.repository import VariantRepository
from vcf_api.variants.service import VariantService
from vcf_api.variants.vcf_repository import VcfFileRepository


def create_app(
    settings: Settings | None = None,
    repository: VariantRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_repository = repository or VcfFileRepository(resolved_settings.vcf_file)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        configure_logging(resolved_settings.log_level)
        resolved_repository.validate_source()
        yield

    application = FastAPI(
        title="VCF Variants API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.variant_repository = resolved_repository
    application.state.variant_service = VariantService(resolved_repository)
    register_exception_handlers(application)
    application.add_middleware(RequestLoggingMiddleware)
    application.include_router(variants_router)

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
