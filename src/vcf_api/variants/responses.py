from math import ceil

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from vcf_api.http.content_negotiation import MediaType
from vcf_api.http.xml import to_xml
from vcf_api.variants.context import VariantListContext, page_etag
from vcf_api.variants.models import PageResult
from vcf_api.variants.schemas import Pagination, VariantPage, VariantResponse


def not_modified_response(context: VariantListContext) -> Response:
    return Response(
        status_code=status.HTTP_304_NOT_MODIFIED,
        headers={"ETag": context.etag, "Vary": "Accept"},
    )


def variant_page_response(
    request: Request,
    result: PageResult,
    context: VariantListContext,
) -> Response:
    query = context.query
    pages = ceil(result.total / query.page_size) if result.total else 0
    payload = VariantPage(
        items=[VariantResponse(**item.model_dump()) for item in result.items],
        pagination=Pagination(
            page=query.page,
            page_size=query.page_size,
            total=result.total,
            pages=pages,
            previous=_page_url(request, query.page - 1, query.page_size)
            if query.page > 1
            else None,
            next=_page_url(request, query.page + 1, query.page_size)
            if query.page < pages
            else None,
        ),
    ).model_dump(by_alias=True)
    headers = {
        "ETag": page_etag(query, context.media_type, context.url, result.revision),
        "Vary": "Accept",
    }
    if context.media_type is MediaType.XML:
        return Response(content=to_xml(payload), media_type=MediaType.XML, headers=headers)
    return JSONResponse(content=payload, headers=headers)


def _page_url(request: Request, page: int, page_size: int) -> str:
    return str(request.url.include_query_params(page=page, page_size=page_size))
