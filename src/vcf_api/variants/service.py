from vcf_api.variants.exceptions import VariantNotFoundError
from vcf_api.variants.models import PageRequest, PageResult, VariantRecord
from vcf_api.variants.repository import VariantRepository


class VariantService:
    def __init__(self, repository: VariantRepository) -> None:
        self._repository = repository

    def revision(self) -> str:
        return self._repository.revision()

    def list(self, request: PageRequest) -> PageResult:
        result = self._repository.list(request)
        if request.variant_id is not None and result.total == 0:
            raise VariantNotFoundError(request.variant_id)
        return result

    def create(self, variant: VariantRecord) -> None:
        self._repository.create(variant)

    def update(self, variant_id: str, variant: VariantRecord) -> int:
        affected = self._repository.update_by_id(variant_id, variant)
        if affected == 0:
            raise VariantNotFoundError(variant_id)
        return affected

    def delete(self, variant_id: str) -> int:
        affected = self._repository.delete_by_id(variant_id)
        if affected == 0:
            raise VariantNotFoundError(variant_id)
        return affected
