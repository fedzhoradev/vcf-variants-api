from dataclasses import dataclass

from vcf_api.http.content_negotiation import MediaType
from vcf_api.http.etag import build_etag
from vcf_api.variants.models import PageRequest


@dataclass(frozen=True, slots=True)
class VariantListContext:
    query: PageRequest
    media_type: MediaType
    url: str
    etag: str
    not_modified: bool


def page_etag(query: PageRequest, media_type: MediaType, url: str, revision: str) -> str:
    return build_etag({**query.model_dump(), "media_type": media_type.value, "url": url}, revision)
