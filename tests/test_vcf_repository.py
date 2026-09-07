import gzip
from pathlib import Path

import pytest

from vcf_api.variants.exceptions import InvalidVcfError
from vcf_api.variants.models import PageRequest
from vcf_api.variants.schemas import VariantInput
from vcf_api.variants.vcf_repository import VcfFileRepository


def test_repository_reads_and_mutates_gzipped_vcf(tmp_path: Path) -> None:
    path = tmp_path / "input.vcf.gz"
    with gzip.open(path, "wt") as target:
        target.write(
            "##fileformat=VCFv4.2\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "chr1\t1\trs1\tA\tC\t.\tPASS\t.\n"
        )
    repository = VcfFileRepository(path)
    variant = VariantInput(CHROM="chrM", POS=2, ID="rs2", REF="G", ALT="T")

    repository.validate_source()
    repository.create(variant.to_record())
    result = repository.list(PageRequest(page=1, page_size=10))

    assert result.total == 2
    assert result.items[-1].id == "rs2"
    assert repository.delete_by_id("rs1") == 1
    assert repository.list(PageRequest(page=1, page_size=10)).total == 1


def test_repository_rejects_missing_vcf_header(tmp_path: Path) -> None:
    path = tmp_path / "invalid.vcf"
    path.write_text("chr1\t1\trs1\tA\tC\n")

    with pytest.raises(InvalidVcfError):
        VcfFileRepository(path).validate_source()
