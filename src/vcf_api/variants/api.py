from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from vcf_api.variants.dependencies import (
    AuthorizedDependency,
    VariantListDependency,
    VariantServiceDependency,
)
from vcf_api.variants.responses import not_modified_response, variant_page_response
from vcf_api.variants.schemas import MutationResult, VariantInput

router = APIRouter(prefix="/variants", tags=["variants"])
VariantIdQuery = Annotated[str, Query(alias="id", min_length=1)]


@router.get("")
def list_variants(
    request: Request,
    context: VariantListDependency,
    service: VariantServiceDependency,
) -> Response:
    if context.not_modified:
        return not_modified_response(context)
    return variant_page_response(request, service.list(context.query), context)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=VariantInput)
def create_variant(
    variant: VariantInput,
    service: VariantServiceDependency,
    _authorized: AuthorizedDependency,
) -> VariantInput:
    service.create(variant.to_record())
    return variant


@router.put("", response_model=MutationResult)
def update_variant(
    variant: VariantInput,
    variant_id: VariantIdQuery,
    service: VariantServiceDependency,
    _authorized: AuthorizedDependency,
) -> MutationResult:
    return MutationResult(affected=service.update(variant_id, variant.to_record()))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    variant_id: VariantIdQuery,
    service: VariantServiceDependency,
    _authorized: AuthorizedDependency,
) -> Response:
    service.delete(variant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
