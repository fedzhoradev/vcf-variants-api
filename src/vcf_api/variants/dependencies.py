from typing import Annotated

from fastapi import Depends, Header, Query, Request

from vcf_api.core.exceptions import InvalidPaginationError, PermissionDeniedError
from vcf_api.core.security import has_valid_secret
from vcf_api.http.content_negotiation import MediaType, negotiate_content_type
from vcf_api.http.etag import etag_matches
from vcf_api.variants.context import VariantListContext, page_etag
from vcf_api.variants.models import PageRequest
from vcf_api.variants.service import VariantService


def get_variant_service(request: Request) -> VariantService:
    return request.app.state.variant_service


def get_page_request(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int | None, Query(ge=1)] = None,
    variant_id: Annotated[str | None, Query(alias="id")] = None,
) -> PageRequest:
    settings = request.app.state.settings
    resolved_page_size = page_size or settings.default_page_size
    if resolved_page_size > settings.max_page_size:
        raise InvalidPaginationError(
            f"page_size must be less than or equal to {settings.max_page_size}"
        )
    return PageRequest(page=page, page_size=resolved_page_size, variant_id=variant_id)


def get_media_type(
    accept: Annotated[str | None, Header()] = None,
) -> MediaType:
    return negotiate_content_type(accept)


def get_variant_list_context(
    request: Request,
    query: Annotated[PageRequest, Depends(get_page_request)],
    media_type: Annotated[MediaType, Depends(get_media_type)],
    service: Annotated[VariantService, Depends(get_variant_service)],
    if_none_match: Annotated[str | None, Header()] = None,
) -> VariantListContext:
    url = str(request.url)
    etag = page_etag(query, media_type, url, service.revision())
    return VariantListContext(
        query=query,
        url=url,
        media_type=media_type,
        etag=etag,
        not_modified=etag_matches(if_none_match, etag),
    )


def require_api_secret(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not has_valid_secret(authorization, request.app.state.settings.api_secret):
        raise PermissionDeniedError
    request.state.authenticated = True


VariantServiceDependency = Annotated[VariantService, Depends(get_variant_service)]
VariantListDependency = Annotated[VariantListContext, Depends(get_variant_list_context)]
AuthorizedDependency = Annotated[None, Depends(require_api_secret)]
