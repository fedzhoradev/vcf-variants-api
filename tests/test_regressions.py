import logging
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from test_error_handling_and_logging import _capture_app_logs, _json_logs

from vcf_api.core.config import Settings
from vcf_api.core.security import has_valid_secret
from vcf_api.http.logging import configure_logging
from vcf_api.variants.exceptions import InvalidVcfError
from vcf_api.variants.models import PageRequest
from vcf_api.variants.schemas import VariantInput


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/missing", 404),
        ("PATCH", "/variants", 405),
    ],
)
def test_framework_errors_use_global_envelope(client, method, path, status):
    response = client.request(method, path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == "http_error"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    if status == 405:
        assert "allow" in response.headers


def test_etag_matches_data_when_writer_replaces_file_before_read(client, repository, valid_variant):
    original_list = repository.list

    def replace_then_read(query):
        repository.create(VariantInput(**valid_variant).to_record())
        return original_list(query)

    with patch.object(repository, "list", side_effect=replace_then_read):
        response = client.get("/variants")
    current = client.get("/variants")
    assert response.json() == current.json()
    assert response.headers["etag"] == current.headers["etag"]


def test_etag_includes_origin_used_in_navigation_links(client):
    first = client.get("/variants", headers={"host": "first.example"})
    second = client.get("/variants", headers={"host": "second.example"})
    assert first.json()["pagination"]["next"] != second.json()["pagination"]["next"]
    assert first.headers["etag"] != second.headers["etag"]


def test_post_preserves_sample_column_count(repository, vcf_path, valid_variant):
    vcf_path.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE1\tSAMPLE2\n"
        "chr1\t1\trs1\tA\tT\t.\tPASS\t.\tGT\t0/1\t1/1\n"
    )
    repository.create(VariantInput(**valid_variant).to_record())
    lines = vcf_path.read_text().splitlines()
    assert len(lines[-1].split("\t")) == len(lines[1].split("\t")) == 11
    assert lines[-1].split("\t")[5:] == ["."] * 6


def test_failed_create_leaves_source_unchanged(repository, vcf_path, valid_variant):
    vcf_path.write_text("chr1\t1\trs1\tA\tT\n")
    before = vcf_path.read_bytes()
    with pytest.raises(InvalidVcfError):
        repository.create(VariantInput(**valid_variant).to_record())
    assert vcf_path.read_bytes() == before
    assert not list(vcf_path.parent.glob(".*.tmp"))


def test_open_reader_retains_old_snapshot_after_atomic_replace(repository, valid_variant):
    with repository._open_read() as source:
        repository.create(VariantInput(**valid_variant).to_record())
        assert "rs999" not in source.read()
    assert repository.list(PageRequest(page=1, page_size=10)).total == 6


def test_logs_filter_unknown_query_values_and_exception_messages(client, repository):
    with _capture_app_logs() as stream:
        client.get("/variants?token=private-token&page=1")
        with patch.object(repository, "list", side_effect=InvalidVcfError("private-row")):
            client.get("/variants")
    logs = stream.getvalue()
    assert "private-token" not in logs
    assert "private-row" not in logs
    error_log = next(item for item in _json_logs(logs) if item.get("event") == "request_error")
    assert error_log["exception"]["type"] == "InvalidVcfError"
    assert error_log["exception"]["frames"]


def test_logging_setup_preserves_handlers_and_uvicorn_state():
    logger = logging.getLogger("vcf_api")
    handler = logging.NullHandler()
    logger.addHandler(handler)
    access_disabled = logging.getLogger("uvicorn.access").disabled
    try:
        configure_logging("INFO")
        before = logger.handlers[:]
        configure_logging("INFO")
        assert logger.handlers == before
        assert handler in logger.handlers
        assert logging.getLogger("uvicorn.access").disabled == access_disabled
    finally:
        logger.removeHandler(handler)


def test_unicode_secret_comparison_does_not_raise():
    assert not has_valid_secret("невірний", "secret")
    assert has_valid_secret("секрет", "секрет")


def test_invalid_default_page_size_is_rejected():
    with pytest.raises(ValidationError):
        Settings(default_page_size=10, max_page_size=5)
