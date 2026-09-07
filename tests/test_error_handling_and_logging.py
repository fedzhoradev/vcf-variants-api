import json
import logging
from contextlib import contextmanager
from io import StringIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from vcf_api.http.logging import JsonFormatter
from vcf_api.variants.exceptions import InvalidVcfError
from vcf_api.variants.vcf_repository import VcfFileRepository


def _json_logs(stderr: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in stderr.splitlines() if line.startswith("{")]


@contextmanager
def _capture_app_logs():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    app_logger = logging.getLogger("vcf_api")
    existing_handlers = app_logger.handlers[:]
    app_logger.handlers = [handler]
    try:
        yield stream
    finally:
        app_logger.handlers = existing_handlers


def test_successful_request_has_request_id_and_structured_access_log(
    client: TestClient,
) -> None:
    with _capture_app_logs() as stream:
        response = client.get(
            "/variants?id=rs1",
            headers={"User-Agent": "vcf-api-test-client"},
        )

    logs = _json_logs(stream.getvalue())
    access_log = logs[-1]
    assert response.status_code == 200
    assert response.headers["x-request-id"] == access_log["request_id"]
    assert access_log["event"] == "http_request"
    assert access_log["operation"] == "list_variants"
    assert access_log["client_ip"] == "testclient"
    assert access_log["user_agent"] == "vcf-api-test-client"
    assert access_log["method"] == "GET"
    assert access_log["path"] == "/variants"
    assert access_log["target_id"] == "rs1"
    assert access_log["status_code"] == 200
    assert isinstance(access_log["duration_ms"], float)


def test_authenticated_mutation_is_marked_without_logging_secret(
    client: TestClient,
    valid_variant: dict,
) -> None:
    with _capture_app_logs() as stream:
        client.post(
            "/variants",
            json=valid_variant,
            headers={"Authorization": "test-secret"},
        )

    raw_logs = stream.getvalue()
    access_log = _json_logs(raw_logs)[-1]
    assert access_log["operation"] == "create_variant"
    assert access_log["authenticated"] is True
    assert "test-secret" not in raw_logs


def test_handled_server_error_uses_safe_response_and_is_logged(
    client: TestClient,
    repository: VcfFileRepository,
) -> None:
    with (
        _capture_app_logs() as stream,
        patch.object(repository, "list", side_effect=InvalidVcfError("sensitive row data")),
    ):
        response = client.get("/variants")

    raw_logs = stream.getvalue()
    logs = _json_logs(raw_logs)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "invalid_vcf"
    assert "sensitive row data" not in response.text
    assert any(log.get("event") == "request_error" for log in logs)
    assert logs[-1]["status_code"] == 500
    assert logs[-1]["error_reason"] == "invalid_vcf"


def test_unexpected_error_is_not_exposed(
    client: TestClient,
    repository: VcfFileRepository,
) -> None:
    with (
        patch.object(repository, "list", side_effect=RuntimeError("private failure details")),
        TestClient(client.app, raise_server_exceptions=False) as safe_client,
    ):
        response = safe_client.get("/variants")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"
    assert "private failure details" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
