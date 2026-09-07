import pytest

from vcf_api.http.content_negotiation import (
    MediaType,
    NotAcceptableError,
    negotiate_content_type,
)
from vcf_api.http.etag import build_etag, etag_matches


@pytest.mark.parametrize("accept", [None, "", "*/*", "application/*"])
def test_content_negotiation_defaults_to_json(accept: str | None) -> None:
    assert negotiate_content_type(accept) is MediaType.JSON


def test_content_negotiation_honours_quality() -> None:
    accept = "application/xml;q=0.9, application/json;q=0.5"

    assert negotiate_content_type(accept) is MediaType.XML


def test_content_negotiation_rejects_unsupported_values() -> None:
    with pytest.raises(NotAcceptableError):
        negotiate_content_type("text/plain")


def test_etag_is_stable_and_matches_weak_or_list_headers() -> None:
    etag = build_etag({"page": 1}, "revision")

    assert etag == build_etag({"page": 1}, "revision")
    assert etag_matches(f'"something-else", W/{etag}', etag)
    assert not etag_matches('"something-else"', etag)


@pytest.mark.parametrize(
    ("accept", "expected"),
    [
        ("application/json;q=0, */*;q=1", MediaType.XML),
        ("application/json;q=0.1, application/*;q=0.9", MediaType.XML),
        ("application/xml;q=0, */*", MediaType.JSON),
        ("application/json;q=2, application/xml;q=0.5", MediaType.XML),
        ("application/json;q=NaN, application/xml;q=0.5", MediaType.XML),
    ],
)
def test_specific_ranges_override_wildcards(accept, expected):
    assert negotiate_content_type(accept) is expected
