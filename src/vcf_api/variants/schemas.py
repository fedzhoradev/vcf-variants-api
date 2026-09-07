from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from vcf_api.variants.models import VariantRecord


class VariantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chrom: str = Field(alias="CHROM")
    pos: int = Field(alias="POS")
    id: str = Field(alias="ID")
    ref: str = Field(alias="REF")
    alt: str = Field(alias="ALT")


Chromosome = Annotated[
    str,
    StringConstraints(pattern=r"^chr(?:[1-9]|1[0-9]|2[0-2]|X|Y|M)$"),
]
VariantId = Annotated[str, StringConstraints(pattern=r"^rs[0-9]+$")]
Allele = Annotated[str, StringConstraints(pattern=r"^[ACGT.]$")]


class VariantInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chrom: Chromosome = Field(alias="CHROM")
    pos: int = Field(alias="POS", gt=0)
    id: VariantId = Field(alias="ID")
    ref: Allele = Field(alias="REF")
    alt: Allele = Field(alias="ALT")

    def to_record(self) -> VariantRecord:
        return VariantRecord(**self.model_dump())


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int
    previous: str | None
    next: str | None


class VariantPage(BaseModel):
    items: list[VariantResponse]
    pagination: Pagination


class MutationResult(BaseModel):
    affected: int
