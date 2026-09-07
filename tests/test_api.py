from unittest.mock import patch
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from vcf_api.variants.vcf_repository import VcfFileRepository


def test_get_returns_default_json_page_with_navigation(client: TestClient) -> None:
    response = client.get("/variants")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["vary"] == "Accept"
    assert "etag" in response.headers
    body = response.json()
    assert [item["ID"] for item in body["items"]] == ["rs1", "rs2"]
    assert body["pagination"]["total"] == 5
    assert body["pagination"]["pages"] == 3
    assert body["pagination"]["previous"] is None
    assert "page=2" in body["pagination"]["next"]


def test_get_second_page_has_previous_and_next(client: TestClient) -> None:
    response = client.get("/variants?page=2&page_size=2")

    pagination = response.json()["pagination"]
    assert [item["ID"] for item in response.json()["items"]] == ["rs2", "."]
    assert "page=1" in pagination["previous"]
    assert "page=3" in pagination["next"]


def test_get_supports_complex_existing_vcf_values(client: TestClient) -> None:
    response = client.get("/variants?page=2&page_size=3")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"CHROM": "chr4", "POS": 400, "ID": ".", "REF": "CAG", "ALT": "C"},
        {"CHROM": "chrX", "POS": 500, "ID": "rs5", "REF": "T", "ALT": "A,C"},
    ]


def test_get_returns_xml(client: TestClient) -> None:
    response = client.get("/variants?page_size=1", headers={"Accept": "application/xml"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    root = ElementTree.fromstring(response.content)
    assert root.findtext("./items/item/ID") == "rs1"
    assert root.findtext("./pagination/total") == "5"


@pytest.mark.parametrize("accept", ["text/html", "application/yaml", "application/json;q=0"])
def test_get_rejects_unsupported_media_type(client: TestClient, accept: str) -> None:
    response = client.get("/variants", headers={"Accept": accept})

    assert response.status_code == 406


def test_get_filters_all_records_by_id(client: TestClient) -> None:
    response = client.get("/variants?id=rs2")

    assert response.status_code == 200
    assert [item["POS"] for item in response.json()["items"]] == [200, 300]
    assert response.json()["pagination"]["total"] == 2


def test_get_unknown_id_returns_404(client: TestClient) -> None:
    response = client.get("/variants?id=rs404")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "variant_not_found"
    assert response.json()["error"]["message"] == "No variants found for id 'rs404'"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_matching_etag_returns_304_without_listing_file(
    client: TestClient, repository: VcfFileRepository
) -> None:
    etag = client.get("/variants?page=1&page_size=2").headers["etag"]

    with patch.object(repository, "list", wraps=repository.list) as list_records:
        response = client.get(
            "/variants?page=1&page_size=2",
            headers={"If-None-Match": etag},
        )

    assert response.status_code == 304
    assert response.content == b""
    list_records.assert_not_called()


def test_etag_changes_after_mutation(client: TestClient, valid_variant: dict) -> None:
    previous_etag = client.get("/variants").headers["etag"]
    client.post("/variants", json=valid_variant, headers={"Authorization": "test-secret"})

    response = client.get("/variants", headers={"If-None-Match": previous_etag})

    assert response.status_code == 200
    assert response.headers["etag"] != previous_etag


def test_post_requires_authorization(client: TestClient, valid_variant: dict) -> None:
    missing = client.post("/variants", json=valid_variant)
    wrong = client.post("/variants", json=valid_variant, headers={"Authorization": "wrong-secret"})

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert missing.json()["error"]["code"] == "permission_denied"


def test_post_creates_variant(client: TestClient, valid_variant: dict) -> None:
    response = client.post(
        "/variants", json=valid_variant, headers={"Authorization": "test-secret"}
    )

    assert response.status_code == 201
    assert response.json() == valid_variant
    assert client.get("/variants?id=rs999").json()["items"] == [valid_variant]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("CHROM", "1"),
        ("CHROM", "chr23"),
        ("POS", 0),
        ("ID", "123"),
        ("REF", "AA"),
        ("ALT", "N"),
    ],
)
def test_post_validates_input(
    client: TestClient, valid_variant: dict, field: str, value: object
) -> None:
    payload = {**valid_variant, field: value}

    response = client.post("/variants", json=payload, headers={"Authorization": "test-secret"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_put_updates_every_matching_record_and_preserves_extra_columns(
    client: TestClient, vcf_path, valid_variant: dict
) -> None:
    response = client.put(
        "/variants?id=rs2",
        json=valid_variant,
        headers={"Authorization": "test-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"affected": 2}
    lines = [line for line in vcf_path.read_text().splitlines() if not line.startswith("#")]
    updated = [line.split("\t") for line in lines if line.split("\t")[2] == "rs999"]
    assert len(updated) == 2
    assert [row[5:] for row in updated] == [
        ["88", "PASS", "DP=20"],
        ["77", "LowQual", "DP=30"],
    ]


def test_put_unknown_id_returns_404_without_changing_file(
    client: TestClient, vcf_path, valid_variant: dict
) -> None:
    before = vcf_path.read_bytes()

    response = client.put(
        "/variants?id=rs404",
        json=valid_variant,
        headers={"Authorization": "test-secret"},
    )

    assert response.status_code == 404
    assert vcf_path.read_bytes() == before


def test_delete_removes_every_matching_record(client: TestClient) -> None:
    response = client.delete("/variants?id=rs2", headers={"Authorization": "test-secret"})

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/variants?id=rs2").status_code == 404
    assert client.get("/variants?page_size=10").json()["pagination"]["total"] == 3


def test_delete_unknown_id_returns_404(client: TestClient) -> None:
    response = client.delete("/variants?id=rs404", headers={"Authorization": "test-secret"})

    assert response.status_code == 404


def test_page_size_cannot_exceed_configured_maximum(client: TestClient) -> None:
    response = client.get("/variants?page_size=11")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pagination"
