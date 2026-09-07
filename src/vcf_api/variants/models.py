from pydantic import BaseModel, Field


class VariantRecord(BaseModel):
    chrom: str = Field(min_length=1)
    pos: int = Field(gt=0)
    id: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    alt: str = Field(min_length=1)


class PageRequest(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    variant_id: str | None = None


class PageResult(BaseModel):
    items: list[VariantRecord]
    total: int
    revision: str
