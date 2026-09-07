from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vcf_api.core.config import Settings
from vcf_api.main import create_app
from vcf_api.variants.vcf_repository import VcfFileRepository

VCF_CONTENT = """##fileformat=VCFv4.2
##reference=test
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t100\trs1\tA\tG\t99\tPASS\tDP=10
chr2\t200\trs2\tC\tT\t88\tPASS\tDP=20
chr3\t300\trs2\tG\tA\t77\tLowQual\tDP=30
chr4\t400\t.\tCAG\tC\t66\tPASS\tDP=40
chrX\t500\trs5\tT\tA,C\t55\tPASS\tDP=50
"""


@pytest.fixture
def vcf_path(tmp_path: Path) -> Path:
    path = tmp_path / "input.vcf"
    path.write_text(VCF_CONTENT, encoding="utf-8")
    return path


@pytest.fixture
def repository(vcf_path: Path) -> VcfFileRepository:
    return VcfFileRepository(vcf_path)


@pytest.fixture
def client(vcf_path: Path, repository: VcfFileRepository) -> Iterator[TestClient]:
    settings = Settings(
        vcf_file=vcf_path,
        api_secret="test-secret",
        default_page_size=2,
        max_page_size=10,
    )
    with TestClient(create_app(settings=settings, repository=repository)) as test_client:
        yield test_client


@pytest.fixture
def valid_variant() -> dict[str, str | int]:
    return {"CHROM": "chr22", "POS": 999, "ID": "rs999", "REF": "A", "ALT": "T"}
